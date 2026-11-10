"""Outlined table ownership must preserve source artwork without an OCR service."""
from pathlib import Path
import sys
from unittest.mock import patch
import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/document-translation/scripts'))
import region_ocr
from translate import add_block

def source_page(native_text=False):
    document = fitz.open()
    page = document.new_page(width=400, height=500)
    for y in [150, 180, 210, 240]:
        page.draw_line((60, y), (340, y), color=(0, 0, 0))
    for x in [60, 150, 245, 340]:
        page.draw_line((x, 150), (x, 240), color=(0, 0, 0))
    if native_text:
        page.insert_text((65, 170), 'Column title and native cells')
    return document, page

def content():
    value = {'sources': [{'id': 'D001'}], 'blocks': [], 'issues': []}
    caption = add_block(value, 'D001', 'paragraph', {'page': 1, 'bbox': [60, 115, 340, 140]},
                        ['Table 1. Measured values.'], presentation={'role': 'caption'})
    return value, caption

def test_outline_grid_detected_but_native_text_not_reocrd():
    document, page = source_page()
    regions = region_ocr.outlined_table_candidates(page)
    assert len(regions) == 1
    assert regions[0]['horizontal_tracks'] == 4
    assert regions[0]['vertical_tracks'] == 4
    document.close()
    document, page = source_page(native_text=True)
    assert region_ocr.outlined_table_candidates(page) == []
    document.close()

def test_graph_with_no_grid_does_not_become_table():
    document = fitz.open(); page = document.new_page(width=400, height=500)
    page.draw_rect(fitz.Rect(60, 150, 340, 240), color=(0, 0, 0))
    for i in range(5):
        page.draw_line((70+i*45, 220), (100+i*45, 170), color=(0, 0, 0))
    assert region_ocr.outlined_table_candidates(page) == []
    document.close()

def test_no_ocr_preserves_complete_artwork_and_caption(tmp_path):
    document, page = source_page(); value, caption = content()
    with patch.object(region_ocr, 'recognize', side_effect=AssertionError('PDF must never invoke OCR')):
        boxes, records = region_ocr.recover_tables(tmp_path, value, 'D001', page, add_block)
    table = next(b for b in value['blocks'] if b.get('source_table_fallback'))
    assert table['structure']['semantic_role'] == 'table'
    assert table['structure']['representation'] == 'source-table-artwork'
    assert table['caption_block_ids'] == [caption['id']]
    assert table['units'] == []
    assert len(boxes) == 1 and len(records) == 1
    assert value['blocks'].index(table) < value['blocks'].index(caption)
    assert (tmp_path / table['asset']).is_file()
    assert (tmp_path / table['asset_fallback']).is_file()
    assert records[0]['source_kind'] == 'outlined-vector-table'
    assert records[0]['disposition'] == 'source-table-artwork-retained'
    assert records[0]['engine'] == 'disabled-for-pdf'
    assert records[0]['ocr_calls'] == 0
    # Repeated recovery cannot duplicate this caption-bound table.
    with patch.object(region_ocr, 'recognize', side_effect=AssertionError('Duplicated source table')):
        region_ocr.recover_tables(tmp_path, value, 'D001', page, add_block)
    assert sum(bool(b.get('source_table_fallback')) for b in value['blocks']) == 1
    document.close()

def test_unbound_and_obstructed_artwork_stays_outside_prose(tmp_path):
    document, page = source_page(); value, caption = content()
    with patch.object(region_ocr, 'recognize', side_effect=AssertionError('Unbound table OCR')):
        assert region_ocr.recover_tables(tmp_path, {'blocks': [], 'issues': []}, 'D001', page, add_block) == ([], [])
        caption['source']['bbox'] = [60, 60, 340, 80]
        add_block(value, 'D001', 'paragraph', {'page': 1, 'bbox': [60, 100, 340, 120]},
                  ['An intervening independent paragraph.'])
        assert region_ocr.recover_tables(tmp_path, value, 'D001', page, add_block) == ([], [])
    document.close()
