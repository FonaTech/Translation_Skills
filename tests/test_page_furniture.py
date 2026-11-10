"""Page furniture is preserved in evidence, outside body translation. MIT."""
import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/document-translation/scripts'))
import source_furniture as furniture
import source_structure as structure
import translate
from test_structure_regions import styled


def test_repetition_requires_matching_margin_and_protects_footnotes():
    rows=[styled('h','Research journal 15:1234',40,25,size=8),
          styled('body','Research journal 15:1234',40,300,size=8),
          styled('paragraph','The actual body retains its original source words.',40,350,size=10)]
    page={'page':1,'width':600,'height':800,'lines':rows}
    other={'page':2,'width':600,'height':800,'lines':[styled('h2','Research journal 15:1234',40,25,size=8)]}
    profile=structure.document_profile([page,other]);decision={'assigned_role':'metadata','predicted_role':'body'}
    assert furniture.classify(rows[0],page,profile,decision)['kind']=='header'
    assert furniture.classify(rows[1],page,profile,decision) is None
    assert furniture.classify(rows[0],page,profile,{**decision,'semantic_role':'footnote'}) is None
    assert furniture.classify(rows[0],page,profile,{**decision,'assigned_role':'reference'}) is None


def test_ingest_archives_headers_footers_but_keeps_source_footnote(tmp_path):
    import fitz
    source=tmp_path/'source.pdf'
    with fitz.open() as pdf:
        for number in range(1,4):
            pg=pdf.new_page(width=600,height=800)
            pg.insert_text((40,30),'Article',fontsize=8)
            pg.insert_text((40,100),'The original body paragraph remains complete.',fontsize=11)
            pg.insert_text((40,760),'Example journal (2024) 15:1234',fontsize=8)
            pg.insert_text((550,760),str(number),fontsize=8)
            pg.insert_text((40,720),'1 Source footnote retains its stated condition.',fontsize=8)
        pdf.save(source)
    root=tmp_path/'project'
    with contextlib.redirect_stdout(io.StringIO()):
        translate.init(argparse.Namespace(project=str(root),title='Fixture',languages='zh-Hans',style='source',page_size='A4',columns=1))
        translate.ingest(argparse.Namespace(project=str(root),files=[str(source)],pages=None,password=None,order='auto',tables=False,structure='ml',structure_model=None))
    content=json.loads((root/'content.json').read_text())
    text=' '.join(u['source'] for b in content['blocks'] for u in b.get('units',[]))
    assert 'Article' not in text and 'Example journal' not in text
    assert 'body paragraph' in text and 'Source footnote' in text
    archive=json.loads((root/'reports/page-furniture/D001.json').read_text())
    assert len(archive['regions'])==9
    assert all(x['source']['native_line_ids'] and x['line_decisions'] for x in archive['regions'])
