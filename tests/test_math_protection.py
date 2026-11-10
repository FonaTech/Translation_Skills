"""Formula evidence is reversible, immutable and excluded from translation."""
import copy
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import math_protection as m
import alignment

def test_complete_chemical_compounds_and_no_acronym_false_positives():
 text='The Al₂O₃ and HfO₂ layers are different.'
 found=m.ranges(text)
 assert [text[r['start']:r['end']] for r in found]==['Al₂O₃','HfO₂']
 assert all(r['kind']=='formula' for r in found)
 text='Deposit Al2O3 and HfO2, then read CMOS and 3D.'
 attrs=[{} for _ in text]
 for start,end in [(text.index('Al2O3'),text.index('Al2O3')+5),(text.index('HfO2'),text.index('HfO2')+4)]:
  for i in range(start,end):
   if text[i].isdigit():attrs[i]={'subscript':True,'script':True}
 found=m.ranges(text,attrs)
 assert [text[r['start']:r['end']] for r in found]==['Al2O3','HfO2']
 assert all(r['kind']=='formula' for r in found)
 assert m.ranges('CMOS, CNT, Si and Fig. 3 are ordinary identifiers.')==[]

def test_chemical_formula_is_reversible_and_disjoint_from_footnotes():
 text='Al₂O₃ is used here¹.';u={'id':'chemistry','source':text};m.attach(u)
 assert m.literal(u['source_template'],u['protected_math'])==text
 assert [r['kind'] for r in u['protected_math']]==['formula','marker']

@pytest.mark.parametrize('source',['Contact E-mail:{name, address,','The 1st layer and 2nd layer.','B. An italic section heading','def f(x): return x + 1','https://example.test/?x=2','A price of $25 per item.'])
def test_negative_examples(source):
 assert m.ranges(source)==[]

@pytest.mark.parametrize('source',['For x = 2 and y = 3, proceed.','The rate is α = 2β + γ.',r'Keep \(x+y\) unchanged.'])
def test_exact_source_roundtrip(source):
 unit={'id':'U001','source':source};m.attach(unit)
 assert unit.get('protected_math')
 assert m.literal(unit['source_template'],unit['protected_math'])==source
 m.validate(unit,unit['source_template'])
 rendered=m.source_render(unit)
 assert 'data-math-token=' in rendered and 'contenteditable="false"' in rendered

@pytest.mark.parametrize('bad',['missing','duplicate','reorder','mutate'])
def test_token_corruption_rejected(bad):
 u={'id':'U1','source':'Use x = 2 and y = 3.'};m.attach(u);a,b=[r['token'] for r in u['protected_math']];text=u['source_template']
 target={'missing':text.replace(a,''),'duplicate':text+a,'reorder':text.replace(a,'TEMP').replace(b,a).replace('TEMP',b),'mutate':text.replace(a,a[:-2]+'z⟧')}[bad]
 with pytest.raises(ValueError):m.validate(u,target)

def test_repeated_formula_belongs_to_correct_alignment_group():
 u={'id':'U1','source':'First x = 2. Again x = 2.'};m.attach(u);a,b=[r['token'] for r in u['protected_math']]
 u['alignment']={'zh-Hans':[{'id':'G1','source':'First x = 2.','source_sentence_ids':['S1'],'faithful':'首先'+a+'。','interpretive':'首先'+a+'。'},
 {'id':'G2','source':'Again x = 2.','source_sentence_ids':['S2'],'faithful':'再次'+b+'。','interpretive':'再次'+b+'。'}]}
 rows=alignment.rows(u,'zh-Hans')
 assert [r['protected_math'][0]['token'] for r in rows]==[a,b]
 assert all(len(r['protected_math'])==1 for r in rows)
 assert rows[1]['source_template']=='Again '+b+'.'

def test_typography_math_and_markers_remain_distinct():
 text='Use Eg > 0.8, then note¹.';attrs=[{} for _ in text]
 for i in range(4,6):attrs[i]={'font':'CMMI10'}
 for i in range(0,len(text)):
  if text[i]=='¹':attrs[i]={'script':True}
 found=m.ranges(text,attrs)
 assert text[found[0]['start']:found[0]['end']]=='Eg > 0.8'
 assert found[-1]['kind']=='marker'

def test_engineering_relations_keep_complete_identifiers_and_units():
 text='At VDS=1V with |Vdata| = 0.5V, continue.'
 assert [text[r['start']:r['end']] for r in m.ranges(text)]==['VDS=1V','|Vdata| = 0.5V']

def test_leading_footnote_marker_does_not_swallow_article():
 text='¹ A complex phase is ruled out.'
 assert [(text[r['start']:r['end']],r['kind']) for r in m.ranges(text)]==[('¹','marker')]

def test_leading_affiliation_marker_does_not_swallow_acronym():
 text='²MIT, MA, USA'
 assert [(text[r['start']:r['end']],r['kind']) for r in m.ranges(text)]==[('²','marker')]

def test_control_glyph_in_math_font_is_not_trimmed_as_whitespace():
 text='Use ei'+chr(29)+' unless '+chr(29)+' = 0.'
 attrs=[{} for _ in text]
 for i,char in enumerate(text):
  if char==chr(29):attrs[i]={'font':'R1-tii'}
 attrs[5]={'script':True}
 found=m.ranges(text,attrs)
 assert [text[r['start']:r['end']] for r in found]==['ei'+chr(29),chr(29)+' = 0']

def test_shell_prompt_with_nested_path_is_not_math():
 assert m.ranges('legacy_tool:/libraries/slow/cells/NAND4X1> ls -l -a Y')==[]

def test_math_font_symbol_keeps_measured_subscript():
 text=chr(24)+'sd is a measured quantity.';attrs=[{} for _ in text]
 attrs[0]={'font':'MTMI'}
 for i in [1,2]:attrs[i]={'font':'Times-Roman','script':True,'subscript':True}
 found=m.ranges(text,attrs)
 assert [text[r['start']:r['end']] for r in found]==[chr(24)+'sd']


@pytest.mark.parametrize('failure',[None,'asset','transcript','distorted','page'])
def test_table_formula_pdf_uses_source_operators_and_rejects_changed_evidence(tmp_path,failure):
 import hashlib
 import fitz
 from unittest.mock import patch
 import translate
 from vector_assets import export_crop
 from asset_fidelity import compare_pdf_region
 source=tmp_path/'source.pdf';target=tmp_path/'output.pdf'
 with fitz.open() as pdf:
  page=pdf.new_page(width=240,height=160)
  page.insert_text((30.13,55.47),'z0z1',fontsize=7)
  page.draw_line((29.5,45.4),(53.8,45.4),width=.3)
  page.insert_text((30,100),'Unrelated body text',fontsize=10)
  pdf.save(source)
 crop=[29,44,54,58];destination=[88.25,79.5,123.25,99.1]
 with fitz.open(source) as pdf:
  exported=export_crop(pdf[0],crop,tmp_path/'formula')
 unit={'id':'table-cell','source':'z0z1'};m.attach(unit,[{'start':0,'end':4,'kind':'formula'}])
 record=unit['protected_math'][0];record.update(page=1,bbox=crop,asset='formula.svg',
  asset_sha256=hashlib.sha256(exported['vector'].read_bytes()).hexdigest())
 content={'sources':[{'id':'D','file':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}],
  'blocks':[{'id':'B','source':{'document_id':'D'},'units':[unit]}]}
 with fitz.open() as pdf:pdf.new_page(width=240,height=160);pdf.save(target)
 before=target.read_bytes();source_before=source.read_bytes()
 geometry=[{'kind':'source-asset','page':1,'token':record['token'],
  'asset_sha256':record['asset_sha256'],'pdf_bbox':destination}]
 if failure=='asset':geometry[0]['asset_sha256']='0'*64
 if failure=='transcript':record['source']='invented notation'
 if failure=='distorted':geometry[0]['pdf_bbox']=[88.25,79.5,123.25,129.5]
 if failure=='page':geometry[0]['page']=0
 with patch.object(translate,'project',return_value=(tmp_path,{},content)):
  if failure:
   with pytest.raises(ValueError):m.overlay_native_pdf(tmp_path,target,geometry,'faithful')
   assert target.read_bytes()==before
  else:
   report=m.overlay_native_pdf(tmp_path,target,geometry,'faithful')
   assert report['placements'][0]['kind']=='source-asset'
   with fitz.open(source) as original,fitz.open(target) as output:
    metrics=compare_pdf_region(original[0],crop,output[0],destination,tmp_path/'expected.png',tmp_path/'actual.png')
    assert metrics['mean_absolute_rgb_error']==0,metrics
    assert 'z0z1' in output[0].get_text()
    assert 'Unrelated' not in output[0].get_text()
 assert source.read_bytes()==source_before
