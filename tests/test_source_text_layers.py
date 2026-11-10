"""Owned visible/OCR overlays must keep source words and native line coverage."""
from collections import Counter
import copy
from pathlib import Path
import sys

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/document-translation/scripts'))
import source_structure as structure
import source_text_layers as layers


TEXT = 'Original paragraph wording stays exactly intact.'


def page_rows(hidden_text=TEXT, hidden_x=40, hidden_y=100, scan=False):
    document = fitz.open(); page = document.new_page(width=600, height=800)
    if not scan:
        page.insert_text((40, 100), TEXT, fontname='helv', fontsize=10)
    page.insert_text((hidden_x, hidden_y), hidden_text, fontname='helv', fontsize=10, render_mode=3)
    return document, page


def test_identical_source_layers_merge_and_preserve_every_native_id_and_pixels():
    document, page = page_rows()
    before = page.get_pixmap().samples
    raw = structure.raw_page(page)
    assert len(raw['native_lines']) == 2 and len(raw['lines']) == 1
    row = raw['lines'][0]
    assert row['text'] == TEXT
    assert len(row['duplicate_text_layers']) == 1
    assert Counter(row['native_line_ids']) == Counter(r['id'] for r in raw['native_lines'])
    assert raw['native_lines'][1]['text'] == TEXT
    assert page.get_pixmap().samples == before
    assert row['duplicate_text_layers'][0]['source_wording_changed'] is False
    result = structure.reconstruct(raw, structure.document_profile([raw]))
    assert result['coverage']['pass']
    document.close()


def test_conflicting_hidden_wording_is_archived_with_unchanged_visible_primary():
    hidden = TEXT.replace('exactly', 'partly')
    document, page = page_rows(hidden_text=hidden)
    before = page.get_pixmap().samples
    raw = structure.raw_page(page)
    assert len(raw['native_lines']) == 2 and len(raw['lines']) == 1
    primary = raw['lines'][0]
    assert primary['text'] == TEXT and raw['native_lines'][1]['text'] == hidden
    alternate = primary['alternate_text_layers'][0]
    assert alternate['text'] == hidden and alternate['visible_text'] == TEXT
    assert alternate['source_wording_changed'] is False
    assert alternate['conflict_resolved'] is False and alternate['review_required']
    assert Counter(primary['native_line_ids']) == Counter(r['id'] for r in raw['native_lines'])
    assert raw['text_layer_alternates'] and not raw['text_layer_deduplication']
    result = structure.reconstruct(raw, structure.document_profile([raw]))
    assert result['coverage']['pass']
    assert any(i['code'] == 'structure-competing-text-layers' for i in result['issues'])
    assert page.get_pixmap().samples == before
    document.close()


def test_different_columns_baselines_and_unrelated_hidden_wording_stay_separate():
    for options in [{'hidden_text': 'A completely unrelated source annotation is separate.'},
                    {'hidden_x': 330}, {'hidden_y': 115}]:
        document, page = page_rows(**options)
        raw = structure.raw_page(page)
        assert len(raw['native_lines']) == len(raw['lines']) == 2
        assert not raw['text_layer_deduplication']
        document.close()


def test_identical_short_caption_ends_headings_and_equation_numbers_keep_native_ids():
    for text in ['on genetic algorithm', 'IV. TEST BENCH', '(3)', '95']:
        document = fitz.open(); page = document.new_page(width=600, height=800)
        for mode in [0, 3]:
            page.insert_text((40, 100), text, fontsize=10, render_mode=mode)
        raw = structure.raw_page(page)
        assert len(raw['lines']) == 1 and raw['lines'][0]['text'] == text
        assert len(raw['lines'][0]['native_line_ids']) == 2
        assert not raw['text_layer_alternates']
        document.close()


def test_short_conflicting_identifiers_and_two_visible_versions_are_not_collapsed():
    for hidden in [True, False]:
        document = fitz.open(); page = document.new_page(width=600, height=800)
        page.insert_text((40, 100), 'ABCD', fontsize=10)
        page.insert_text((40, 100), 'ABCE', fontsize=10, render_mode=3 if hidden else 0)
        raw = structure.raw_page(page)
        assert len(raw['lines']) == 2
        assert not raw['text_layer_alternates'] and not raw['text_layer_deduplication']
        document.close()


def test_ocr_only_page_keeps_its_invisible_reading_text():
    document, page = page_rows(scan=True)
    raw = structure.raw_page(page)
    assert len(raw['lines']) == 1 and raw['lines'][0]['text'] == TEXT
    assert not raw['text_layer_deduplication']
    assert structure.source_text_present(raw['lines'][0])
    document.close()


def test_incomplete_source_unicode_does_not_validate_matching_ocr():
    document, page = page_rows()
    raw = structure.raw_page(page)
    rows = structure.physical_rows(raw['native_lines'])
    rows[0]['spans'] = copy.deepcopy(rows[0]['spans'])
    rows[0]['spans'][0]['chars'][0]['unicode_unresolved'] = True
    retained, evidence = layers.deduplicate(rows)
    assert len(retained) == 2 and not evidence
    document.close()


def test_unknown_source_math_stays_primary_and_hidden_conflict_stays_archived():
    document,page=page_rows();raw=structure.raw_page(page)
    rows=structure.physical_rows(raw['native_lines'])
    visible='The interval of [1, 2], here \x01\x02\x03\x04.'
    hidden='The interval of [l, 2], here Pr=2.'
    for row,text in zip(rows,[visible,hidden]):
        row['text']=text;span=row['spans'][0];span['text']=text
        span['chars']=[{'c':c,'source_visibility':'visible' if row is rows[0] else 'invisible'} for c in text]
    for char in rows[0]['spans'][0]['chars']:
        if ord(char['c'])<32:
            char.update(unicode_unresolved=True,native_glyph={'svg':'<svg><path/></svg>'})
    untouched=copy.deepcopy(rows)
    retained,evidence=layers.deduplicate(rows)
    assert len(retained)==1 and retained[0]['text']==visible
    assert evidence[0]['text']==hidden and not evidence[0]['conflict_resolved']
    assert evidence[0]['primary_known_source_fraction']>=.95
    assert evidence[0]['candidate_text_similarity']<.9
    assert retained[0]['spans']==untouched[0]['spans']
    # An absent outline cannot lend support to alternate-layer selection.
    for char in untouched[0]['spans'][0]['chars']:char.pop('native_glyph',None)
    retained,evidence=layers.deduplicate(untouched)
    assert len(retained)==2 and not evidence
    document.close()


def test_repeated_visible_rows_and_ambiguous_visible_owners_remain_separate():
    document, page = page_rows()
    raw = structure.raw_page(page)
    rows = structure.physical_rows(raw['native_lines'])
    extra = copy.deepcopy(rows[0]); extra['id'] = 'extra'; extra['native_line_ids'] = ['extra']
    retained, evidence = layers.deduplicate(rows+[extra])
    assert len(retained) == 3 and not evidence
    # Two visible text objects alone cannot validate an invisible-layer removal.
    retained, evidence = layers.deduplicate([rows[0], extra])
    assert len(retained) == 2 and not evidence
    document.close()
