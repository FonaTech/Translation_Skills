"""Original ruled topology fixtures; no private source data. MIT."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/document-translation/scripts'))
import structure_table_grid as grid
import structure_tables
import table_learning
from test_structure_regions import styled


def fixture(wrapped=False):
    rows=[]
    def add(lid,text,cx,y):
        r=styled(lid,text,0,y,size=8)
        width=r['bbox'][2];r['bbox'][0]=cx-width/2;r['bbox'][2]=cx+width/2
        r['spans'][0]['bbox']=r['bbox'][:];r['spans'][0]['origin'][0]=r['bbox'][0]
        rows.append(r)
    for c,x in enumerate([75,175,275]):add('h'+str(c),'Field' if c==0 else 'Value',x,55)
    for row,y in enumerate([80,110,140]):
        for c,x in enumerate([75,175,275]):
            add(f'r{row}c{c}',str(row+c),x,y)
            if wrapped:add(f'r{row}c{c}b','(Q = L, Qb = H)',x,y+10)
    page={'fraction_rules':[[25,50,325],[25,70,325],[25,165,325]]}
    return page,rows,[25,50,325,165]


def test_numerical_model_drives_wrapped_cell_membership():
    page,rows,box=fixture(True)
    with patch.object(table_learning,'predict',wraps=table_learning.predict) as inference:
        result=grid.ruled_grid(page,rows,box)
    assert result and inference.call_count==1
    assert len(result['cells'])==4 and len(result['column_widths'])==3
    assert result['cells'][1][1]['line_ids']==['r0c1','r0c1b']
    assert result['evidence']['cell_link_inference']['pairs']>0
    assert len(result['evidence']['cell_link_inference']['model_sha256'])==64
    # No model means no fabricated continuation decisions.
    with patch.object(table_learning,'predict',return_value=([],None)):
        assert grid.ruled_grid(page,rows,box) is None


def test_parent_header_spans_columns_without_merging_their_values():
    page,rows,box=fixture()
    rows=[r for r in rows if r['id'] not in {'h1','h2'}]
    parent=styled('parent','Combined',0,55,size=8);width=parent['bbox'][2]
    parent['bbox']=[225-width/2,55,225+width/2,63];rows.append(parent)
    result=grid.ruled_grid(page,rows,box)
    assert result and result['cells'][0][1]['colspan']==2
    assert result['cells'][0][2]['covered_by']==[0,1]
    assert result['cells'][1][1]['line_ids']==['r0c1']
    assert result['cells'][1][2]['line_ids']==['r0c2']


def test_partial_hierarchical_separators_require_artwork_not_weak_decoder():
    page,rows,box=fixture();page['fraction_rules'].append([125,100,325])
    assert grid.ruled_grid(page,rows,box) is None
    page.update(page=1,width=400,height=500,lines=rows,structure_regions=[box],table_regions=[])
    caption=styled('caption','Table 1. Original fixture.',25,30,size=8);page['lines'].append(caption)
    decisions={r['id']:{'assigned_role':'table'} for r in rows}
    decisions['caption']={'assigned_role':'caption'}
    assert structure_tables.groups(page,page['lines'],decisions)==[]
    retained=structure_tables.unresolved_groups(page,page['lines'],decisions,[])
    assert len(retained)==1 and retained[0]['representation']=='source-table-artwork'
    assert {r['id'] for r in retained[0]['members']}=={r['id'] for r in rows if r['id']!='caption'}
