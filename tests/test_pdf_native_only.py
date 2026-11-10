"""PDF OCR prohibition holds with engines installed and across host choices."""
import argparse
import contextlib
import hashlib
import io
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import fitz
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/document-translation/scripts'))
import region_ocr
import source_review
import translate as t
from test_outlined_tables import source_page,content


@pytest.mark.parametrize('platform',['darwin','linux','win32'])
def test_pdf_table_never_recognizes_even_with_installed_ocr(tmp_path,platform):
    document,page=source_page();value,caption=content()
    original=page.get_pixmap().samples
    with patch.object(sys,'platform',platform), \
         patch.object(region_ocr.shutil,'which',return_value='/installed/engine'), \
         patch.object(region_ocr,'recognize',side_effect=AssertionError('Forbidden PDF OCR')), \
         patch.object(subprocess,'run',side_effect=AssertionError('Forbidden subprocess')):
        boxes,records=region_ocr.retain_pdf_tables(tmp_path,value,'D001',page,t.add_block)
    assert len(boxes)==len(records)==1
    assert records[0]['engine']=='disabled-for-pdf' and records[0]['ocr_calls']==0
    assert all(not b.get('units') for b in value['blocks'] if b is not caption)
    assert value['issues'][0]['code']=='source-table-text-unavailable'
    assert page.get_pixmap().samples==original
    document.close()


def init(root):
    with contextlib.redirect_stdout(io.StringIO()):
        t.init(argparse.Namespace(project=str(root),title='Native PDF fixture',languages='zh-Hans',
                                style='source',page_size='A4',columns=1))


def test_scan_is_archived_and_flagged_without_ocr_or_generated_units(tmp_path):
    from PIL import Image
    image=tmp_path/'scan.png';Image.new('RGB',(120,160),'#e0d5bc').save(image)
    source=tmp_path/'scan.pdf'
    with fitz.open() as document:
        page=document.new_page(width=240,height=320)
        page.insert_image(page.rect,filename=str(image));document.save(source)
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    root=tmp_path/'project';init(root)
    with patch.object(region_ocr,'recognize',side_effect=AssertionError('Forbidden PDF OCR')), \
         patch.object(subprocess,'run',side_effect=AssertionError('Forbidden subprocess')), \
         contextlib.redirect_stdout(io.StringIO()):
        t.ingest(argparse.Namespace(project=str(root),files=[str(source)],pages=None,password=None,
                                  order='auto',tables=False,structure='ml',structure_model=None))
    _,_,value=t.project(root)
    assert value['sources'][0]['extraction_policy']['pdf_ocr'] is False
    assert not list(t.units(value))
    assert any(b.get('source_page_fallback') and (root/b['asset']).is_file() for b in value['blocks'])
    assert any(x['code']=='native-text-unavailable' and x['status']=='open' for x in value['issues'])
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    assert t.sha(root/value['sources'][0]['file'])==before
    assert not (root/'reports/ocr.json').exists()
    with patch.object(subprocess,'run',side_effect=AssertionError('Forbidden PDF OCR')):
        for engine in ['vision','tesseract']:
            with pytest.raises(ValueError,match='PDF OCR is disabled'):
                t.ocr(argparse.Namespace(project=str(root),document='D001',pages='1',engine=engine,
                                        languages='eng',allow_native=True))


def test_pdf_table_transcription_cannot_bypass_native_policy(tmp_path):
    root=tmp_path/'project';init(root)
    document,page=source_page();source=root/'sources/source.pdf';document.save(source);document.close()
    _,manifest,value=t.project(root)
    value['sources']=[{'id':'D001','file':'sources/source.pdf','sha256':t.sha(source),'page_count':1}]
    caption=t.add_block(value,'D001','paragraph',{'page':1},['Table 1. Original caption.'])
    t.write(root/'content.json',value)
    evidence='reports/region-artwork/table.json'
    t.write(root/evidence,{'kind':'raster-table','caption_block_id':caption['id'],
                          'source_page':1,'bbox':[60,150,340,240]})
    packet={'source_hash':t.source_snap(manifest,value),'reviewer':'fixture agent','evidence':[evidence],
            'operations':[{'op':'transcribe-table','evidence_file':evidence,'rows':[['A','B']],
                           'observation':'A PDF table must retain its original artwork.'}]}
    checked=root/'tasks/checked.json';t.write(checked,packet)
    with pytest.raises(ValueError,match='PDF OCR/transcription is disabled'):
        source_review.apply(root,checked)
    assert t.read(root/'content.json')==value
