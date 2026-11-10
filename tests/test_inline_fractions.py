"""Original spatial fixtures; no private source documents or model translations."""
import copy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/document-translation/scripts'))
import source_structure as structure
import math_protection as math


def span(text,box,size,baseline,font='CMMI7'):
    step=(box[2]-box[0])/max(1,len(text))
    return {'text':text,'bbox':box,'size':size,'font':font,'flags':0,
            'origin':[box[0],baseline],
            'chars':[{'c':c,'bbox':[box[0]+i*step,box[1],box[0]+(i+1)*step,box[3]]}
                     for i,c in enumerate(text)]}


def row(key,spans,size=10,block=0):
    return {'id':key,'native_block':block,'native_line':0,'native_line_ids':[key],
            'text':''.join(s['text'] for s in spans),'spans':spans,'size':size,
            'font':max(spans,key=lambda s:len(s['text']))['font'],'flags':0,
            'bbox':structure.union([s['bbox'] for s in spans]),'direction':[1,0]}


def fixture():
    top=row('numerator',[span('A',[85,95,92,102],7,100),span('k',[92,98,96,103],5,101)],7)
    prose=row('prose',[
        span('The normalized measure uses ',[20,97,80,107],10,105,'Times-Roman'),
        span('A',[81,104,88,111],7,109),
        span('max',[88,107,101,112],5,110,'Times-Roman'),
        span(' within the specified range.',[103,97,250,107],10,105,'Times-Roman')])
    return [top,prose],[(80,103,102)]


@pytest.mark.parametrize('mode',['valid','no-rule','other-column','other-block','ambiguous-owner'])
def test_wholly_detached_inline_fraction_is_protected_inside_prose_gap(mode):
    owner=row('owner',[
        span('The measured capacitance C = ',[20,97,80,107],10,105,'Times-Roman'),
        span('the specified permittivity value.',[115,97,250,107],10,105,'Times-Roman')])
    numerator=row('top',[span('ε0ε',[87,93,108,102],9,100)],9)
    denominator=row('bottom',[span('d',[95,105,101,115],9,113)],9)
    rows=[owner,numerator,denominator];rules=[(85,103,110)]
    if mode=='no-rule':rules=[]
    if mode=='other-column':rules=[(305,103,330)]
    if mode=='other-block':numerator['native_block']=3
    if mode=='ambiguous-owner':
        other=copy.deepcopy(owner);other['id']='other';rows.append(other)
    before=copy.deepcopy(rows)
    result=structure.attach_detached_inline_fractions(rows,rules)
    if mode!='valid':assert result==before
    else:
        assert len(result)==1
        text,candidates=math.line_candidates(result[0])
        matched=next(c for c in candidates if c.get('serialization')=='spatial-glyph-transcript')
        assert matched['text']=='ε0εd' and text[matched['start']:matched['end']]=='ε0εd'
        assert 'the specified permittivity value.' in text
        assert set(result[0]['native_line_ids'])=={'owner','top','bottom'}
        from collections import Counter
        assert Counter(c for r in before for c in r['text'] if not c.isspace())==Counter(c for c in text if not c.isspace())


@pytest.mark.parametrize('mode',['valid','next-line','other-block','ambiguous-owner'])
def test_detached_accent_stays_with_the_measured_repeated_identifier(mode):
    owner=row('owner',[
        span('The measured ',[20,97,80,107],10,105,'Times-Roman'),
        span('CLK',[82,97,100,107],10,105,'Times-Roman'),
        span(' value follows another CLK reference.',[102,97,250,107],10,105,'Times-Roman')])
    mark=row('accent',[span('¯',[88,95,91,105],10,103)],10)
    rows=[owner,mark]
    if mode=='next-line':mark['spans'][0]['origin'][1]-=15
    if mode=='other-block':mark['native_block']=1
    if mode=='ambiguous-owner':
        other=copy.deepcopy(owner);other['id']='other';rows.append(other)
    before=copy.deepcopy(rows);result=structure.attach_inline_accents(rows)
    if mode!='valid':assert result==before
    else:
        assert len(result)==1 and result[0]['text'].count('CLK¯')==1
        text,candidates=math.line_candidates(result[0])
        assert any(c['text']=='CLK¯' for c in candidates)
        assert 'another CLK reference.' in text
        assert set(result[0]['native_line_ids'])=={'owner','accent'}


@pytest.mark.parametrize('mode',['same-baseline','following-line','different-column','ambiguous-owner'])
def test_separate_native_inline_sum_tail_has_one_geometric_prose_owner(mode):
    parent=row('prose',[span('The measured output is defined as y = ∑P',[20,97,180,107],10,105,'Times-Roman')])
    tail=row('tail',[span('i=1',[176,101,187,108],7,106),span(' wixi.',[188,97,216,107],10,105)],7,block=9)
    rows=[parent,tail]
    if mode=='following-line':
        for s in tail['spans']:s['origin'][1]+=20
    if mode=='different-column':tail['bbox']=[300,97,340,108]
    if mode=='ambiguous-owner':
        other=copy.deepcopy(parent);other['id']='another';rows.insert(1,other)
    before=copy.deepcopy(rows)
    result=structure.attach_inline_operator_tails(rows)
    if mode!='same-baseline':assert result==before
    else:
        assert len(result)==1
        assert result[0]['text']=='The measured output is defined as y = ∑P i=1 wixi.'
        assert set(result[0]['native_line_ids'])=={'prose','tail'}
        assert [p['native_line_id'] for p in result[0]['row_fragments']]==['prose','tail']
        assert not result[0]['inline_operator_tail_evidence']['generated_nonspace_characters']


def test_complete_fraction_owns_all_source_glyphs_and_rule():
    rows,rules=fixture();original=copy.deepcopy(rows)
    merged=structure.attach_inline_fractions(rows,rules)
    assert len(merged)==1
    record=merged[0]['inline_spatial_groups'][0]
    assert record['text']=='AkAmax'
    assert record['bbox']==[80,95,102,112]
    assert set(merged[0]['native_line_ids'])=={'prose','numerator'}
    assert original[1]['spans']!=merged[0]['spans']
    assert len(original[1]['spans'])==4
    text,candidates=math.line_candidates(merged[0])
    fraction=next(c for c in candidates if c.get('serialization')=='spatial-glyph-transcript')
    assert fraction['text']=='AkAmax' and fraction['bbox']==record['bbox']
    assert len(candidates)==1
    unit={'id':'source-bound','source':text};math.attach(unit,candidates)
    assert math.literal(unit['source_template'],unit['protected_math'])==text
    assert 'within the specified range.' in unit['source_template']


@pytest.mark.parametrize('change',['no-rule','wrong-column','different-block','display-size','repeated-text','long-rule','rule-below-denominator'])
def test_ambiguous_or_unrelated_math_is_not_joined(change):
    rows,rules=fixture()
    if change=='no-rule':rules=[]
    if change=='wrong-column':rules=[(180,103,202)]
    if change=='different-block':rows[0]['native_block']=1
    if change=='display-size':rows[0]['size']=10
    if change=='repeated-text':rows[1]['text']+=' Amax'
    if change=='long-rule':rules=[(20,103,250)]
    if change=='rule-below-denominator':rules=[(80,114,102)]
    snapshot=copy.deepcopy(rows)
    assert structure.attach_inline_fractions(rows,rules)==snapshot


def test_spatial_transcript_mismatch_is_rejected():
    rows,rules=fixture();merged=structure.attach_inline_fractions(rows,rules)[0]
    merged['inline_spatial_groups'][0]['source_start']+=1
    with pytest.raises(ValueError,match='transcript mismatch'):
        math.line_candidates(merged)


def test_multiple_fraction_offsets_follow_later_insertions():
    rows,rules=fixture();parent=rows[1]
    parent['text']='The normalized measure uses Bmax and Amax within the specified range.'
    parent['spans']=[
        span('The normalized measure uses ',[20,97,45,107],10,105,'Times-Roman'),
        span('B',[50,104,57,111],7,109),span('max',[57,107,70,112],5,110,'Times-Roman'),
        span(' and ',[72,97,79,107],10,105,'Times-Roman'),
        *parent['spans'][1:]]
    parent['bbox']=structure.union([s['bbox'] for s in parent['spans']])
    extra=row('other-numerator',[span('B',[54,95,61,102],7,100),span('j',[61,98,65,103],5,101)],7)
    rows.insert(1,extra);rules.append((49,103,71))
    merged=structure.attach_inline_fractions(rows,rules)
    assert len(merged)==1
    text,candidates=math.line_candidates(merged[0])
    assert [c['text'] for c in candidates]==['BjBmax','AkAmax']
    assert all(text[c['start']:c['end']]==c['text'] for c in candidates)
    assert set(merged[0]['native_line_ids'])=={'prose','numerator','other-numerator'}
