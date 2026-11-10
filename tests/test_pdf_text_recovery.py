"""Font evidence restores characters without inventing a missing source word."""
import sys
import pytest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/document-translation/scripts'))
import pdf_text_recovery as recovery
import math_protection as math


def test_source_outline_bounds_use_bezier_extrema_and_affine_transform():
 # The control points lie outside the actual curve; a control-box union is wrong.
 bounds=recovery.outline_ink_bounds('M0 0C0 2 2 2 2 0',(10,0,0,-10,5,30))
 assert bounds==pytest.approx((5,15,25,30))
 assert recovery.outline_ink_bounds('',(10,0,0,-10,5,30)) is None


def test_extended_math_geometry_retains_native_box_and_requires_source_ink():
 import copy
 row={'bbox':[10,10,15,20],'direction':[1,0],'size':10,'spans':[
  {'text':chr(4),'size':10,'font':'CMEX10','bbox':[10,10,15,20],
   'chars':[{'c':chr(4),'bbox':[10,10,15,20],'origin':[10,18],
             'native_glyph':{'ink_bbox':[10,18,15,48],'sha256':'outline'}}]}]}
 before=copy.deepcopy(row);geometry=recovery.math_ink_geometry(row)
 assert geometry['bbox']==[10,18,15,48]
 assert geometry['axis_baseline_estimate']==35.5
 assert geometry['axis_is_estimate'] and geometry['native_bbox_unchanged']
 assert row==before
 row['spans'][0]['font']='Times-Roman'
 assert recovery.math_ink_geometry(row) is None
 row['spans'][0]['font']='CMEX10';row['direction']=[0,1]
 assert recovery.math_ink_geometry(row) is None
 row['direction']=[1,0];del row['spans'][0]['chars'][0]['native_glyph']
 assert recovery.math_ink_geometry(row) is None

def test_family_keys_preserve_style():
 assert recovery.key('ABCDEF+TimesNewRomanPSMT')==recovery.key('Times New Roman')
 assert recovery.key('Times New Roman Bold')!=recovery.key('Times New Roman')

def test_font_scoped_positions_and_unresolved_evidence(tmp_path):
 source=tmp_path/'source.pdf';source.write_bytes(b'unchanged source')
 class Parent:
  name=str(source)
  def xref_get_key(self,xref,key):return ('null','null') if xref==1 else ('xref','8 0 R')
 class Page:
  parent=Parent()
  def get_fonts(self,full=True):return [(1,'ttf','Type0','ABCDEF+Broken','F1','Identity-H'),(2,'ttf','Type0','Good','F2','Identity-H')]
  def get_texttrace(self):return [{'font':'Broken','chars':[(65533,38,(10,20),[]) , (65533,80,(20,20),[])]},{'font':'Good','chars':[(71,71,(10,20),[])]}]
 def span(font,chars):return {'font':font,'text':''.join(c for c,x in chars),'chars':[{'c':c,'origin':[x,20],'bbox':[x,10,x+4,20]} for c,x in chars]}
 lines=[{'text':'&P','spans':[span('Broken',[('&',10),('P',20)])]},{'text':'G','spans':[span('Good',[('G',10)])]}]
 with patch.object(recovery,'document_maps',return_value=({1:{38:'C'}},[])):
  report=recovery.recover_lines(Page(),lines)
 assert lines[0]['text']=='CP' and lines[1]['text']=='G'
 assert lines[0]['spans'][0]['chars'][1]['unicode_unresolved']
 assert report[0]['unresolved_characters']==1 and source.read_bytes()==b'unchanged source'

def test_valid_native_unicode_does_not_inherit_missing_map_of_same_family(tmp_path):
 source=tmp_path/'source.pdf';source.write_bytes(b'original')
 class Parent:
  name=str(source)
  def xref_get_key(self,xref,key):return ('null','null')
 class Page:
  parent=Parent()
  def get_fonts(self,full=True):return [(1,'ttf','Type0','Broken','C0','Identity-H'),(2,'ttf','TrueType','Broken','T0','WinAnsiEncoding')]
  def get_texttrace(self):return [{'font':'Broken','chars':[(83,54,(0,20),[]),(65533,80,(5,20),[])]}]
 line=measured_line('SP');line['spans'][0]['font']='Broken'
 with patch.object(recovery,'document_maps',return_value=({1:{54:'X'}},[])):
  report=recovery.recover_lines(Page(),[line])
 assert line['text']=='SP'
 assert not line['spans'][0]['chars'][0].get('unicode_unresolved')
 assert line['spans'][0]['chars'][1]['unicode_unresolved']
 assert report[0]['unresolved_characters']==1

def measured_line(text,unresolved_index=None):
 chars=[{'c':c,'bbox':[i*5,10,(i+1)*5,20],'origin':[i*5,20],**({'unicode_unresolved':True} if i==unresolved_index else {})} for i,c in enumerate(text)]
 return {'id':'L1','text':text,'bbox':[0,10,len(text)*5,20],'size':10,'spans':[{'font':'Times','text':text,'size':10,'origin':[0,20],'flags':0,'chars':chars}]}

def test_unresolved_glyph_isolated_as_source_artwork_candidate():
 line=measured_line('Author 瀗 name',7);text,found=math.line_candidates(line)
 assert any(x['kind']=='source-glyph' and x['text']=='瀗' and x['bbox'] for x in found)

def test_line_end_dehyphenation_does_not_lose_formula_geometry():
 line=measured_line('A value x = 2 is inter-')
 region={'text':'A value x = 2 is international.','line_ids':['L1']}
 found=math.region_candidates(region,{'lines':[line]})
 assert any(x['text']=='x = 2' and x['bbox'] for x in found)
 assert all(region['text'][x['start']:x['end']]==x['text'] for x in found)


def glyph_page(wrapper='',duplicate=False):
 class Page:
  rotation=0
  def get_texttrace(self):
   return [{'font':'ABCDEF+Times','chars':[(65533,7,(10,20),[])], 'opacity':1, 'type':0}]
  def get_svg_image(self,text_as_path=True):
   use='<use href="#font_1_7" transform="matrix(10,0,0,-10,10,20)"/>'
   return '<svg xmlns="http://www.w3.org/2000/svg"><defs><path id="font_1_7" d="M0 0L.4 1L.8 0Z"/></defs><g '+wrapper+'>'+use+(use if duplicate else '')+'</g></svg>'
 return Page()


def test_adjacent_unknown_outlines_share_a_run_without_crossing_readable_text():
 line=measured_line(''+chr(4)+chr(4)+' A '+chr(4)+chr(4))
 # Original source fixtures use one shared origin; assign actual neighbouring
 # character positions before obtaining each exact native source outline.
 for i,c in enumerate(line['spans'][0]['chars']):
  c['origin']=[10+i*5,20];c['bbox']=[10+i*5,12,15+i*5,22]
  if c['c']==chr(4):
   svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="'+str(10+i*5)+' 12 5 10"><path d="M'+str(10+i*5)+' 12v10"/></svg>'
   import hashlib
   c.update(unicode_unresolved=True,native_glyph={'svg':svg,'sha256':hashlib.sha256(svg.encode()).hexdigest(),
        'bbox':c['bbox'],'origin':c['origin']})
 text,candidates=math.line_candidates(line)
 runs=[c for c in candidates if c['kind']=='source-glyph']
 assert [c['text'] for c in runs]==[chr(4)*2,chr(4)*2]
 unit={'id':'two-runs','source':text};math.attach(unit,candidates)
 assert math.literal(unit['source_template'],unit['protected_math'])==text
 assert ' A ' in unit['source_template']
 assert all(math.source_composition_html(r) is not None for r in unit['protected_math'])


@pytest.mark.parametrize('control',[4,127,129,159])
def test_unresolved_control_retains_exact_source_outline_and_roundtrip(control):
 line=measured_line('A '+chr(control)+' symbol')
 before=line['text']
 assert recovery.source_glyph_outlines(glyph_page('fill="#234567"'),[line])==1
 glyph=line['spans'][0]['chars'][2]['native_glyph']
 assert not glyph['unicode_inferred'] and 'fill="#234567"' in glyph['svg']
 text,found=math.line_candidates(line)
 unit={'id':'glyph','source':text};math.attach(unit,found)
 assert line['text']==before and math.literal(unit['source_template'],unit['protected_math'])==before
 assert not math.unresolved_glyphs(unit)
 rendered=math.source_render(unit)
 assert rendered.count('data-source-glyph-sha256')==1 and chr(control) not in rendered
 assert '<path ' in rendered and '<img' not in rendered
 glyph['svg']=glyph['svg'].replace('.4 1','.5 1')
 assert math.unresolved_glyphs(unit)
 with pytest.raises(ValueError,match='outline changed'):math.source_render(unit)


@pytest.mark.parametrize('wrapper,duplicate',[('clip-path="url(#clip)"',False),('transform="translate(1,0)"',False),('',True)])
def test_ambiguous_or_clipped_source_outline_stays_unresolved(wrapper,duplicate):
 line=measured_line('A '+chr(4)+' symbol')
 assert recovery.source_glyph_outlines(glyph_page(wrapper,duplicate),[line])==0
 assert line['spans'][0]['chars'][2]['unicode_unresolved']
 text,found=math.line_candidates(line);unit={'id':'unknown','source':text};math.attach(unit,found)
 assert math.unresolved_glyphs(unit)


def test_source_svg_serialization_can_straddle_a_rounding_bin():
 class Page:
  rotation=0
  def get_texttrace(self):
   return [{'font':'Times','chars':[(65533,7,(10.005002,20),[])], 'opacity':1,'type':0}]
  def get_svg_image(self,text_as_path=True):
   return '<svg xmlns="http://www.w3.org/2000/svg"><defs><path id="font_1_7" d="M0 0L.4 1L.8 0Z"/></defs><use href="#font_1_7" transform="matrix(10,0,0,-10,10.005,20)"/></svg>'
 line=measured_line(chr(4));char=line['spans'][0]['chars'][0]
 char.update(origin=[10.005002,20],bbox=[10.005002,10,15.005002,20])
 assert recovery.source_glyph_outlines(Page(),[line])==1
 assert not char['native_glyph']['unicode_inferred']
 # A nearby glyph outside serialization error is not a valid substitute.
 char.pop('native_glyph');char['origin'][0]=10.006
 assert recovery.source_glyph_outlines(Page(),[line])==0


def test_native_outline_matches_real_pdf_pixels_without_cropping(tmp_path):
 import fitz
 import source_structure as structure
 document=fitz.open();page=document.new_page(width=300,height=180)
 page.insert_text((40,80),'A B',fontsize=24,color=(.2,.3,.4))
 page.wrap_contents()
 line=structure.raw_page(page)['lines'][0]
 char=line['spans'][0]['chars'][0];char['unicode_unresolved']=True
 source_before=page.get_pixmap().samples
 assert recovery.source_glyph_outlines(page,[line])==1
 glyph=char['native_glyph'];box=fitz.Rect(glyph['bbox'])
 svg=fitz.open(stream=glyph['svg'].encode(),filetype='svg')
 rendered=fitz.open('pdf',svg.convert_to_pdf())
 expected=page.get_pixmap(matrix=fitz.Matrix(3,3),clip=box,alpha=False)
 # Compare at equal pixel dimensions to avoid PDF clip-origin rounding.
 actual=rendered[0].get_pixmap(matrix=fitz.Matrix(expected.width/rendered[0].rect.width,expected.height/rendered[0].rect.height),alpha=False)
 assert abs(expected.width-actual.width)<=1 and abs(expected.height-actual.height)<=1
 from PIL import Image,ImageChops,ImageStat
 left=Image.frombytes('RGB',[expected.width,expected.height],expected.samples)
 right=Image.frombytes('RGB',[actual.width,actual.height],actual.samples).resize(left.size)
 assert sum(ImageStat.Stat(ImageChops.difference(left,right)).mean)/3 < 12
 assert page.get_pixmap().samples==source_before
 document.close();svg.close();rendered.close()


@pytest.mark.parametrize('mode',['faithful','alignment','missing','changed','duplicated'])
def test_native_glyph_pdf_gate_tracks_identity_and_expected_occurrences(tmp_path,mode):
 import fitz
 import hashlib
 import translate
 source=tmp_path/'original.pdf';output=tmp_path/'output.pdf'
 with fitz.open() as pdf:
  page=pdf.new_page(width=200,height=180);page.insert_text((40,80),'A',fontsize=24)
  pdf.save(source)
 output.write_bytes(source.read_bytes())
 with fitz.open(source) as pdf:
  box=list(pdf[0].get_text('rawdict')['blocks'][0]['lines'][0]['spans'][0]['chars'][0]['bbox'])
 unit={'id':'U','source':chr(4)}
 svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 8"><path d="M0 0L4 8"/></svg>'
 glyph={'svg':svg,'sha256':hashlib.sha256(svg.encode()).hexdigest(),'bbox':box,'origin':[40,80]}
 math.attach(unit,[{'start':0,'end':1,'kind':'source-glyph','character_styles':[{'native_glyph':glyph}]}])
 record=unit['protected_math'][0];record['page']=1
 block={'id':'B','source':{'document_id':'D'},'units':[unit]}
 content={'sources':[{'id':'D','file':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}],'blocks':[block]}
 item={'key':record['token']+':0','sha256':glyph['sha256'],'x':box[0]/.75,'y':box[1]/.75,'w':(box[2]-box[0])/.75,'h':(box[3]-box[1])/.75}
 items=[item]*(2 if mode in {'alignment','duplicated'} else 1)
 if mode=='missing':items=[]
 if mode=='changed':items=[{**item,'sha256':'changed'}]
 class Browser:
  def emulate_media(self,media):assert media=='print'
  def evaluate(self,script,selector):return [{'page':1,'images':[],'glyphs':items}]
 edition='zh-Hans-alignment' if mode=='alignment' else 'zh-Hans-faithful'
 with patch.object(translate,'project',return_value=(tmp_path,{'editions':['faithful']},content)):
  report=math.verify_pdf(tmp_path,Browser(),output,edition)
 assert report['pass']==(mode in {'faithful','alignment'})
 assert len(report['native_glyph_checks'])==len(items)
 assert report['checks']==[]


def test_explicit_empty_source_outline_preserves_advance_without_invented_unicode():
 class EmptyPage:
  rotation=0
  def get_texttrace(self):return [{'font':'Times','chars':[(65533,3,(10,20),[])], 'opacity':1, 'type':0}]
  def get_svg_image(self,text_as_path=True):
   return '<svg xmlns="http://www.w3.org/2000/svg"><defs><path id="font_1_3" d=""/></defs><use href="#font_1_3" transform="matrix(10,0,0,-10,10,20)"/></svg>'
 line=measured_line('A '+chr(3)+' symbol');before=line['text']
 assert recovery.source_glyph_outlines(EmptyPage(),[line])==1
 glyph=line['spans'][0]['chars'][2]['native_glyph']
 assert glyph['empty_outline'] and not glyph['unicode_inferred']
 text,found=math.line_candidates(line);unit={'id':'empty-source','source':text};math.attach(unit,found)
 assert not math.unresolved_glyphs(unit)
 assert math.literal(unit['source_template'],unit['protected_math'])==before
 assert 'data-source-glyph-sha256' in math.source_render(unit)


def test_unmapped_trace_keeps_source_appearance_even_if_rawdict_looks_like_valid_unicode():
 line=measured_line('A Q symbol')
 assert recovery.source_glyph_outlines(glyph_page(),[line])==1
 char=line['spans'][0]['chars'][2]
 assert char['c']=='Q' and char['unicode_unresolved'] and char['native_glyph']
 assert not char['native_glyph']['unicode_inferred']


def test_overlapping_source_glyphs_render_together_at_measured_positions(tmp_path):
 import fitz
 import source_structure as structure
 from PIL import Image,ImageChops,ImageStat
 doc=fitz.open();page=doc.new_page(width=240,height=160)
 page.insert_text((40,80),'X',fontsize=24)
 page.insert_text((40,72),'-',fontsize=24)
 before=page.get_pixmap().samples
 raw=structure.raw_page(page);lines=raw['native_lines']
 assert recovery.source_glyph_outlines(page,lines,preserve_all=True)==2
 chars=[c for row in lines for span in row['spans'] for c in span['chars']]
 styles=[{'native_glyph':c['native_glyph'],'source_size_pt':24,
          'baseline_shift_em':(c['origin'][1]-80)/24} for c in chars]
 record={'source':''.join(c['c'] for c in chars),'character_styles':styles,'body_size_pt':24}
 markup=math.source_composition_html(record)
 assert markup.count('data-source-glyph-sha256')==2
 box=fitz.Rect(recovery.box_union([c['bbox'] for c in chars])) if hasattr(recovery,'box_union') else fitz.Rect([min(c['bbox'][0] for c in chars),min(c['bbox'][1] for c in chars),max(c['bbox'][2] for c in chars),max(c['bbox'][3] for c in chars)])
 with fitz.open(stream=markup.encode(),filetype='svg') as svg,fitz.open('pdf',svg.convert_to_pdf()) as rendered:
  expected=page.get_pixmap(matrix=fitz.Matrix(4,4),clip=box,alpha=False)
  actual=rendered[0].get_pixmap(matrix=fitz.Matrix(expected.width/rendered[0].rect.width,expected.height/rendered[0].rect.height),alpha=False)
  left=Image.frombytes('RGB',[expected.width,expected.height],expected.samples)
  right=Image.frombytes('RGB',[actual.width,actual.height],actual.samples).resize(left.size)
  assert sum(ImageStat.Stat(ImageChops.difference(left,right)).mean)/3<12
 assert page.get_pixmap().samples==before
 doc.close()


@pytest.mark.parametrize('mode',['valid','repeated','changed-source-viewport','unknown-token'])
def test_native_pdf_reuses_source_operators_and_rejects_changed_identity(tmp_path,mode):
 import fitz,hashlib
 import source_structure as structure
 import translate
 from asset_fidelity import compare_pdf_region
 source=tmp_path/'source.pdf';output=tmp_path/'output.pdf'
 with fitz.open() as pdf:
  pg=pdf.new_page(width=240,height=160);pg.insert_text((40,80),'X',fontsize=24);pg.insert_text((40,140),'Outside excerpt',fontsize=10);pdf.save(source)
 with fitz.open() as pdf:
  pdf.new_page(width=240,height=160);pdf.save(output)
 original_hash=hashlib.sha256(source.read_bytes()).hexdigest()
 with fitz.open(source) as pdf:
  raw=structure.raw_page(pdf[0]);recovery.source_glyph_outlines(pdf[0],raw['native_lines'],preserve_all=True)
 glyph=raw['native_lines'][0]['spans'][0]['chars'][0]['native_glyph']
 unit={'id':'U','source':'X'}
 math.attach(unit,[{'start':0,'end':1,'kind':'source-glyph','character_styles':[{'native_glyph':glyph}]}])
 record=unit['protected_math'][0];record['page']=1;record['body_size_pt']=24
 block={'id':'B','source':{'document_id':'D'},'units':[unit]}
 content={'sources':[{'id':'D','file':source.name,'sha256':original_hash}],'blocks':[block]}
 box=glyph['bbox'];target=[box[0]+60,box[1]+10,box[2]+60,box[3]+10]
 geometry=[{'page':1,'token':record['token'],'source_sha256':record['source_sha256'],
            'source_bbox':box[:],'pdf_bbox':target}]
 if mode=='repeated':
  geometry += [{**geometry[0],'pdf_bbox':[target[0]+dx,target[1],target[2]+dx,target[3]]} for dx in [40,80]]
 if mode=='changed-source-viewport':geometry[0]['source_bbox'][0]+=1
 if mode=='unknown-token':geometry[0]['token']='unknown'
 before=output.read_bytes()
 with patch.object(translate,'project',return_value=(tmp_path,{},content)):
  if mode not in {'valid','repeated'}:
   with pytest.raises(ValueError):math.overlay_native_pdf(tmp_path,output,geometry,'faithful')
   assert output.read_bytes()==before
  else:
   text_calls=[];get_text=fitz.Page.get_text
   def measured_text(page,*args,**kwargs):
    if args and args[0]=='rawdict':text_calls.append(kwargs.get('flags',0))
    return get_text(page,*args,**kwargs)
   with patch.object(fitz.Page,'get_text',measured_text):
    report=math.overlay_native_pdf(tmp_path,output,geometry,'faithful')
   assert len(text_calls)==1 and all(not flags & fitz.TEXT_PRESERVE_IMAGES for flags in text_calls)
   assert len(report['placements'])==len(geometry) and not report['unicode_inferred']
   with fitz.open(source) as source_pdf,fitz.open(output) as output_pdf:
    measured=compare_pdf_region(source_pdf[0],box,output_pdf[0],target,tmp_path/'reference.png',tmp_path/'actual.png')
    assert measured['pass'],measured
    assert 'X' in output_pdf[0].get_text()
    assert 'Outside excerpt' not in output_pdf[0].get_text()
    assert output_pdf[0].get_text().count('X')==len(geometry)
 assert hashlib.sha256(source.read_bytes()).hexdigest()==original_hash


def test_native_pdf_excludes_only_separate_unowned_text_in_temporary_source_copy(tmp_path):
 import fitz,hashlib
 import source_structure as structure
 import translate
 source=tmp_path/'original.pdf';output=tmp_path/'translated.pdf'
 with fitz.open() as pdf:
  pg=pdf.new_page(width=260,height=180)
  for text,x in [('X',40),('Y',80),('X',120)]:pg.insert_text((x,80),text,fontsize=24)
  pdf.save(source)
 with fitz.open() as pdf:pdf.new_page(width=260,height=180);pdf.save(output)
 source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
 with fitz.open(source) as pdf:
  raw=structure.raw_page(pdf[0]);recovery.source_glyph_outlines(pdf[0],raw['native_lines'],preserve_all=True)
 glyphs=[c['native_glyph'] for row in raw['native_lines'] for sp in row['spans'] for c in sp['chars'] if c['c']=='X']
 unit={'id':'U','source':'XX'}
 math.attach(unit,[{'start':0,'end':2,'kind':'source-glyph','character_styles':[{'native_glyph':g} for g in glyphs]}])
 record=unit['protected_math'][0];record.update(page=1,body_size_pt=24)
 box=[min(g['bbox'][0] for g in glyphs),min(g['bbox'][1] for g in glyphs),max(g['bbox'][2] for g in glyphs),max(g['bbox'][3] for g in glyphs)]
 content={'sources':[{'id':'D','file':source.name,'sha256':source_hash}],
          'blocks':[{'id':'B','source':{'document_id':'D'},'units':[unit]}]}
 geometry=[{'page':1,'token':record['token'],'source_sha256':record['source_sha256'],'source_bbox':box,'pdf_bbox':box}]
 with patch.object(translate,'project',return_value=(tmp_path,{},content)):
  report=math.overlay_native_pdf(tmp_path,output,geometry,'faithful')
 assert report['placements'][0]['native_text_exclusions']==1
 with fitz.open(output) as pdf:
  assert pdf[0].get_text().count('X')==2 and 'Y' not in pdf[0].get_text()
  from asset_fidelity import compare_pdf_region
  exclusions=report['placements'][0]['native_text_exclusion_evidence']
  with fitz.open(source) as original:
   metrics=compare_pdf_region(original[0],glyphs[1]['bbox'],pdf[0],glyphs[1]['bbox'],
       tmp_path/'context-reference.png',tmp_path/'context-actual.png',
       native_text_exclusions=exclusions,source_frame=box,output_frame=box)
   assert metrics['pass'],metrics
  # A shared coordinate frame must still detect an actually removed symbol.
  pdf[0].add_redact_annot(fitz.Rect(glyphs[1]['bbox']),fill=(1,1,1));pdf[0].apply_redactions()
  pdf.save(tmp_path/'missing-symbol.pdf')
 with fitz.open(source) as original,fitz.open(tmp_path/'missing-symbol.pdf') as damaged:
  metrics=compare_pdf_region(original[0],glyphs[1]['bbox'],damaged[0],glyphs[1]['bbox'],
       tmp_path/'damaged-reference.png',tmp_path/'damaged-actual.png',
       native_text_exclusions=exclusions,source_frame=box,output_frame=box)
  assert not metrics['pass']
 with fitz.open(source) as pdf:assert 'Y' in pdf[0].get_text()
 assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
