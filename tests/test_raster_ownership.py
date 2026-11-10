"""Owned mixed-artwork fixtures; no private PDFs or source coordinates."""
import copy
import io
from pathlib import Path
import sys

import fitz
from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/document-translation/scripts'))
import figure_regions as figures
import vector_assets as vectors
import asset_fidelity as fidelity


def raster(page, bbox, color):
    stream = io.BytesIO()
    Image.new('RGB', (40, 30), color).save(stream, format='PNG')
    return page.insert_image(fitz.Rect(bbox), stream=stream.getvalue(), keep_proportion=False)


def caption(identifier, bbox, text):
    return {'id': identifier, 'type': 'paragraph', 'source': {'bbox': bbox},
            'units': [{'source': text}], 'presentation': {'role': 'caption'}}


def test_coincident_conflicting_caption_layers_share_all_artwork_without_changing_words():
    with fitz.open() as document:
        page = document.new_page(width=400, height=500)
        owned = [raster(page, box, color) for box, color in [
            ([40, 100, 115, 175], 'blue'), ([200, 95, 280, 230], 'green'),
            ([55, 200, 125, 230], 'red'), ([70, 185, 90, 193], 'orange')]]
        blocks = [caption('visible', [40, 250, 290, 273], 'Figure 4. A 10 by 10 panel.'),
                  caption('hidden', [42, 250.2, 288, 260], 'Figure 4. A lO by lO panel.')]
        before = copy.deepcopy(blocks)
        proposals = figures.propose(page, blocks)
        assert len(proposals) == 1
        assert proposals[0]['caption_block_ids'] == ['visible', 'hidden']
        assert set(proposals[0]['raster_xrefs']) == set(owned)
        assert blocks == before


def test_repeated_numbers_different_positions_and_different_numbers_are_distinct():
    a = caption('a', [40, 250, 290, 273], 'Figure 4. First source caption.')
    b = caption('b', [40, 350, 290, 373], 'Figure 4. Repeated elsewhere.')
    c = caption('c', [40, 250, 290, 273], 'Figure 5. Conflicting physical label.')
    assert len(figures.caption_anchors([a, b, c])) == 3


def test_filtered_crop_cannot_omit_an_enclosed_source_image(tmp_path):
    with fitz.open() as document:
        page = document.new_page(width=300, height=300)
        kept = raster(page, [30, 50, 90, 130], 'blue')
        missing = raster(page, [120, 60, 160, 110], 'red')
        crop = fitz.Rect(20, 40, 180, 150)
        for call in [lambda: vectors.check_raster_completeness(page, crop, [kept]),
                     lambda: vectors.export_crop(page, crop, tmp_path/'vector', raster_xrefs=[kept]),
                     lambda: figures.export_region(page, crop, tmp_path/'png', tmp_path,
                                                   mode='png', raster_xrefs=[kept])]:
            with pytest.raises(ValueError, match='Incomplete source raster ownership') as error:
                call()
            assert str(missing) in str(error.value)
        assert not list(tmp_path.iterdir())
        report = vectors.check_raster_completeness(page, crop, [kept, missing])
        assert report['pass'] and not report['fully_contained_unselected']
        assert report['figure_boundary_verified'] is False


def test_pixel_match_to_an_incomplete_reference_cannot_pass(tmp_path):
    with fitz.open() as source, fitz.open() as output:
        page = source.new_page(width=300, height=300)
        kept = raster(page, [30, 50, 90, 130], 'blue')
        raster(page, [120, 60, 160, 110], 'red')
        crop = fitz.Rect(20, 40, 180, 150)
        target = output.new_page(width=300, height=300)
        # Deliberately reproduce the old circular reference bug. The guard
        # must reject missing source ownership before comparing these pixels.
        with vectors.source_crop_page(page, raster_xrefs=[kept]) as filtered:
            target.show_pdf_page(crop, filtered.parent, filtered.number, clip=crop)
        with pytest.raises(ValueError, match='Incomplete source raster ownership'):
            fidelity.compare_pdf_region(page, crop, target, crop,
                                        tmp_path/'a.png', tmp_path/'b.png', raster_xrefs=[kept])


def test_partial_neighbor_is_recorded_and_unfiltered_artwork_is_kept():
    with fitz.open() as document:
        page = document.new_page(width=300, height=300)
        kept = raster(page, [30, 50, 90, 130], 'blue')
        neighbor = raster(page, [170, 60, 220, 110], 'red')
        crop = fitz.Rect(20, 40, 180, 150)
        report = vectors.check_raster_completeness(page, crop, [kept])
        assert report['pass']
        assert report['partially_intersecting_unselected'][0]['xref'] == neighbor
        assert vectors.check_raster_completeness(page, crop)['method'] == 'unfiltered-source-artwork'
