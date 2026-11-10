"""Inline math uses native text; display equations retain learned detection."""
from pathlib import Path
import sys
from html.parser import HTMLParser
from unittest.mock import patch
import fitz

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import math_protection as math
import publishing
import region_ocr
import source_structure as structure
from structure_layout import write_map
from translate import add_block


def span(text,box,size,baseline,font='CMMI10'):
    step=(box[2]-box[0])/max(1,len(text))
    return {'text':text,'bbox':box,'size':size,'font':font,'flags':2,
        'origin':[box[0],baseline],
        'chars':[{'c':c,'bbox':[box[0]+i*step,box[1],box[0]+(i+1)*step,box[3]]} for i,c in enumerate(text)]}


def row(key,spans):
    return {'id':key,'text':''.join(s['text'] for s in spans),'spans':spans,
        'size':10,'font':'Times-Roman','bbox':structure.union([s['bbox'] for s in spans]),
        'native_block':0,'native_line':0,'direction':[1,0],'flags':0,'native_line_ids':[key]}


def test_inline_native_subscripts_and_superscripts_create_no_images(tmp_path):
    line=row('L1',[span('Use ',[20,90,40,102],10,100,'Times-Roman'),
        span('ED',[40,90,53,102],10,100),span('k',[53,97,57,104],7,102),
        span(' with 3',[58,90,96,102],10,100,'Times-Roman'),
        span('2',[96,86,100,94],7,96,'Times-Roman'),span('N',[100,86,105,94],7,96),
        span(' stable.',[107,90,145,102],10,100,'Times-Roman')])
    text,_=structure.typography_text(line)
    block={'units':[{'id':'U1','source':text}],'typography':{'dominant_size_pt':10}}
    math.attach_block(block,{'text':text,'line_ids':['L1']},{'page':1,'lines':[line]},tmp_path,tmp_path/'does-not-need-a-crop.pdf')
    unit=block['units'][0];records=unit['protected_math']
    assert records and all(r['representation']=='native-inline-text' for r in records)
    assert all(not r.get('asset') for r in records)
    assert not list(tmp_path.rglob('*'))
    rendered=math.source_render(unit,tmp_path)
    assert '<img' not in rendered and '<sub ' in rendered and '<sup ' in rendered
    assert math.literal(unit['source_template'],records)==text
    assert 'stable.' in unit['source_template']


def test_inline_fraction_uses_measured_text_and_rule(tmp_path):
    from test_inline_fractions import fixture
    lines,rules=fixture();line=structure.attach_inline_fractions(lines,rules)[0]
    text,candidates=math.line_candidates(line)
    block={'units':[{'id':'fraction','source':text}],'typography':{'dominant_size_pt':10}}
    math.attach_block(block,{'text':text,'line_ids':[line['id']]},{'page':1,'lines':[line]},tmp_path,'unused.pdf')
    record=block['units'][0]['protected_math'][0]
    assert len(record['text_runs'])==4
    assert record['fraction_rule']==[80,103,102]
    html=math.source_render(block['units'][0],tmp_path)
    assert 'inline-math-composed' in html and 'border-top:' in html
    assert 'max' in html and '<img' not in html
    assert not list(tmp_path.rglob('*'))


def test_span_leading_space_cannot_move_the_prose_baseline():
    spans=[span('Exact',[20,90,50,102],10,100),span('outk',[50,97,66,104],7,101.5),
        span(' denotes the exact value.',[66,90,210,104],10,101.5,'Times-Roman')]
    for item in spans:
        for char in item['chars']:char['origin']=[char['bbox'][0],item['origin'][1]]
    # Only the leading space is lowered; the actual prose shares the base.
    for char in spans[-1]['chars'][1:]:char['origin'][1]=100
    line=row('subscript-whitespace',spans);text,candidates=math.line_candidates(line)
    record=next(r for r in candidates if r['text']=='Exactoutk')
    unit={'id':'U','source':text};math.attach(unit,[record])
    result=math.source_render(unit)
    assert '<sub ' in result and '>outk</sub>' in result


def test_source_column_count_reaches_equation_publisher(tmp_path):
    (tmp_path/'sources').mkdir();file=tmp_path/'sources/source.pdf'
    pdf=fitz.open();pdf.new_page(width=600,height=800);pdf.save(file);pdf.close()
    content={'sources':[{'id':'D1','name':'source.pdf','file':'sources/source.pdf',
        'sha256':__import__('hashlib').sha256(file.read_bytes()).hexdigest(),
        'selection_scope':{'pages':[1]}}],'blocks':[],'issues':[]}
    for x in [40,320]:
        for y in [90,200]:
            add_block(content,'D1','paragraph',{'page':1,'bbox':[x,y,x+230,y+80]},
                ['An original narrative paragraph with sufficient length to establish its source column. '+('Text '*20)],presentation={'role':'body'})
    eq=add_block(content,'D1','equation',{'page':1,'bbox':[90,300,270,340]},[])
    source=content['sources'][0]
    write_map(tmp_path,content,source)
    assert eq['layout_hint']['columns']==2
    assert 'data-span="column"' in publishing.block_attrs(eq)
    eq['presentation']={'span':'all'}
    assert 'data-span="all"' in publishing.block_attrs(eq)


def test_ocr_confidence_does_not_certify_merged_cells():
    item={'text':'A','confidence':1,'bbox':[0,0,10,10]}
    rows=[[{'text':'A','evidence':[item]},{'text':'B','evidence':[item]}],
          [{'text':'','evidence':[]},{'text':'2','evidence':[item]}]]
    result=region_ocr.grid_validation(rows,[item])
    assert not result['pass']
    assert 'empty-cell-or-merged-cell-ownership-unresolved' in result['reasons']


def test_ambiguous_ocr_cells_never_enter_translation_units(tmp_path):
    from test_outlined_tables import source_page,content
    document,page=source_page();value,caption=content()
    # First column labels straddle rows; 100% OCR recognition is insufficient.
    items=[{'text':text,'confidence':1,'bbox':box} for text,box in [
        ('Head A',[.02,.8,.35,.1]),('Head B',[.6,.8,.35,.1]),
        ('Merged label',[.02,.3,.35,.1]),('1',[.6,.4,.2,.1]),('2',[.6,.1,.2,.1])]]
    with patch.object(region_ocr,'recognize',return_value={'engine':'fixture','items':items}):
        boxes,records=region_ocr.recover_tables(tmp_path,value,'D001',page,add_block)
    assert boxes and not records[0]['grid_validation']['pass']
    assert not any(b['type']=='table' for b in value['blocks'])
    assert next(b for b in value['blocks'] if b.get('source_table_fallback'))['units']==[]
    document.close()
