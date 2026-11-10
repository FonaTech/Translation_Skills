"""Original geometry fixtures for complete native table ownership. MIT."""
import copy
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/document-translation/scripts'))
import source_structure as s
import structure_tables as tables
from test_structure_regions import styled


def fixture():
    rows=[styled('caption','Table 3. Recorded relationships.',40,45,size=10)]
    for i,(a,b,y) in enumerate([('Key','Definition',70),('0','x + y',90),('1','z',110),('2','if x > y',135)]):
        rows.extend([styled('a'+str(i),a,45,y,size=8),styled('b'+str(i),b,100,y,size=8,font='CambriaMath' if i else 'Times-Roman')])
    rows.extend([styled('radical','√',92,88,size=8,font='Symbol'),
                 styled('script','2',109,108,size=5,font='CambriaMath'),
                 styled('continuation','else y',100,146,size=8)])
    # A radical uses a font origin near the top of its glyph, unlike prose.
    rows[-3]['spans'][0]['origin'][1]=88.5
    page={'page':1,'width':400,'height':500,'lines':rows,'structure_regions':[[40,65,240,160]],'table_regions':[]}
    decisions={r['id']:{'assigned_role':'caption' if r['id']=='caption' else 'table'} for r in rows}
    return page,decisions


def test_table_keeps_radical_scripts_and_multiline_cell_in_same_row():
    page,d=fixture();before=copy.deepcopy(page);groups=tables.groups(page,page['lines'],d)
    assert len(groups)==1
    grid=groups[0]['cells']
    assert len(grid)==4 and all(len(row)==2 for row in grid)
    assert set(grid[1][1]['line_ids'])=={'b1','radical'}
    assert set(grid[2][1]['line_ids'])=={'b2','script'}
    assert set(grid[3][1]['line_ids'])=={'b3','continuation'}
    members=[r['id'] for r in groups[0]['members']]
    assert sorted(members)==sorted(lid for row in grid for c in row for lid in c['line_ids'])
    assert page==before


def test_table_requires_learned_table_classification_and_source_caption():
    page,d=fixture()
    assert tables.groups(page,page['lines'],{r['id']:{'assigned_role':'body'} for r in page['lines']})==[]
    page['lines'][0]['text']='An unrelated source observation.'
    assert tables.groups(page,page['lines'],d)==[]


def test_crossing_text_vetoes_a_false_cell_gutter():
    page,d=fixture();row=styled('bridge','An uninterrupted source paragraph crosses the proposed table gutter.',45,155,size=8)
    page['lines'].append(row);d[row['id']]={'assigned_role':'table'}
    assert tables.groups(page,page['lines'],d)==[]


def test_double_line_stub_is_ambiguous_and_not_fabricated():
    page,d=fixture();row=styled('stubwrap','part',45,96,size=8)
    page['lines'].append(row);d[row['id']]={'assigned_role':'table'}
    assert tables.groups(page,page['lines'],d)==[]
