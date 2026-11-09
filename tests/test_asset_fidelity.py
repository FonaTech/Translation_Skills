"""Owned fixtures for color polarity, transparency and source-relative gates."""
import argparse
import base64
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'skills/document-translation/scripts'))
import asset_fidelity as fidelity
import publishing
import translate as t
import vector_assets as v


class AssetFidelityTests(unittest.TestCase):
    def test_adjoining_native_text_exclusion_preserves_graphics_and_source(self):
        import fitz
        with fitz.open() as source:
            pg=source.new_page(width=200,height=200)
            pg.draw_rect(fitz.Rect(20,20,160,160),color=(0,0,1))
            pg.insert_text((25,45),'Neighbor caption',fontsize=10)
            pg.insert_text((25,120),'Figure label',fontsize=10)
            pixels=pg.get_pixmap().samples
            exclusions=[{'bbox':[20,30,170,50],'reason':'Inspected adjacent caption','evidence':'previews/p1.png'}]
            with v.source_crop_page(pg,exclusions) as reviewed:
                self.assertNotIn('Neighbor caption',reviewed.get_text())
                self.assertIn('Figure label',reviewed.get_text())
                self.assertEqual(len(pg.get_drawings()),len(reviewed.get_drawings()))
            self.assertIn('Neighbor caption',pg.get_text())
            self.assertEqual(pg.get_pixmap().samples,pixels)
            with self.assertRaises(ValueError):
                with v.source_crop_page(pg,[{'bbox':[20,30,170,50]}]):pass

    def test_pdf_comparison_uses_one_physical_grid(self):
        import fitz
        with tempfile.TemporaryDirectory() as folder, fitz.open() as source, fitz.open() as target:
            pg = source.new_page(width=160, height=120)
            crop = fitz.Rect(13.17, 17.39, 83.17, 87.39)
            for row in range(28):
                for col in range(28):
                    if (row * 13 + col * 7 + row * col) % 5 < 2:
                        pg.draw_rect(fitz.Rect(13.17+col*2.5, 17.39+row*2.5,
                                               15.67+col*2.5, 19.89+row*2.5),
                                     color=None, fill=(0, 0, 0))
            output = target.new_page(width=594.96, height=793.92)
            bbox = fitz.Rect(408.902, 490.277, 465.56, 546.935)
            output.show_pdf_page(bbox, source, 0, clip=crop, keep_proportion=False)
            expected, actual = [Path(folder) / n for n in ['expected.png', 'actual.png']]
            metrics = fidelity.compare_pdf_region(pg, crop, output, bbox, expected, actual)
            self.assertTrue(metrics['pass'], metrics)
            self.assertEqual(metrics['mean_absolute_rgb_error'], 0)
            self.assertEqual(metrics['comparison_method'], fidelity.PDF_COMPARISON_VERSION)
            output.draw_rect(bbox, color=None, fill=(0, 0, 0))
            self.assertFalse(fidelity.compare_pdf_region(pg, crop, output, bbox, expected, actual)['pass'])

    def test_pdf_comparison_rejects_invalid_regions(self):
        import fitz
        with tempfile.TemporaryDirectory() as folder, fitz.open() as source, fitz.open() as target:
            pg = source.new_page(width=100, height=100)
            output = target.new_page(width=100, height=100)
            with self.assertRaisesRegex(ValueError, 'source comparison'):
                fidelity.compare_pdf_region(pg, [-1,0,50,50], output, [0,0,50,50],
                                            Path(folder)/'a.png', Path(folder)/'b.png')
            with self.assertRaisesRegex(ValueError, 'output comparison'):
                fidelity.compare_pdf_region(pg, [0,0,50,50], output, [0,0,101,50],
                                            Path(folder)/'a.png', Path(folder)/'b.png')

    def make_pdf(self, mode='CMYK', color=None, decode=None):
        import fitz
        from PIL import Image, ImageDraw
        doc = fitz.open()
        page = doc.new_page(width=160, height=120)
        color = color or {'CMYK': (0, 0, 0, 0), 'RGB': (255, 255, 255), 'RGBA': (255, 0, 0, 120), 'L': 255}[mode]
        im = Image.new(mode, (120, 80), color)
        if mode == 'CMYK':
            ImageDraw.Draw(im).rectangle((20, 20, 40, 40), fill=(255, 0, 0, 0))
        stream = io.BytesIO()
        im.save(stream, format='JPEG' if mode == 'CMYK' else 'PNG')
        xref = page.insert_image(fitz.Rect(10, 10, 150, 110), stream=stream.getvalue())
        if decode:
            doc.xref_set_key(xref, 'Decode', decode)
        page.draw_line((15, 15), (145, 100), color=(0, 0, 1))
        return doc, page

    def test_cmyk_decoded_in_pdf_context(self):
        doc, page = self.make_pdf()
        with tempfile.TemporaryDirectory() as folder:
            result = v.export_crop(page, page.rect, Path(folder) / 'figure')
            meta = result['metadata']
            self.assertTrue(meta['color_normalization'])
            self.assertTrue(all(x['components'] in (1, 3) for x in meta['raster_colors']))
            self.assertGreater(meta['svg_paths'], 0)
            import fitz
            with fitz.open(result['vector']) as svg:
                rgb = svg[0].get_pixmap().pixel(110, 40)
            self.assertTrue(min(rgb[:3]) > 230, rgb)
        doc.close()

    def test_explicit_rgb_decode_preserves_original_darkness(self):
        doc, page = self.make_pdf('RGB', decode='[1 0 1 0 1 0]')
        with tempfile.TemporaryDirectory() as folder:
            result = v.export_crop(page, page.rect, Path(folder) / 'figure')
            self.assertEqual(result['metadata']['color_normalization'][0]['source_decode'], '[1 0 1 0 1 0]')
            import fitz
            with fitz.open(result['vector']) as svg:
                self.assertLess(max(svg[0].get_pixmap().pixel(110, 40)[:3]), 10)
        doc.close()

    def test_explicit_gray_decode(self):
        doc, page = self.make_pdf('L', decode='[1 0]')
        with tempfile.TemporaryDirectory() as folder:
            result = v.export_crop(page, page.rect, Path(folder) / 'figure')
            self.assertTrue(result['metadata']['color_normalization'])
            self.assertEqual(result['metadata']['color_normalization'][0]['source_decode'], '[1 0]')
        doc.close()

    def test_soft_mask_retained(self):
        doc, page = self.make_pdf('RGBA')
        with tempfile.TemporaryDirectory() as folder:
            result = v.export_crop(page, page.rect, Path(folder) / 'figure')
            self.assertTrue(result['metadata']['color_normalization'][0]['soft_mask_preserved'])
            self.assertIn('<mask', result['vector'].read_text())
            from PIL import Image
            with Image.open(result['fallback']) as im:
                pixel = im.convert('RGB').getpixel((275, 100))
                self.assertGreater(pixel[0], 230)
                self.assertTrue(100 < pixel[1] < 170, pixel)
        doc.close()

    def test_source_bytes_unchanged(self):
        import fitz
        doc, page = self.make_pdf()
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / 'original.pdf'
            doc.save(original)
            doc.close()
            digest = t.sha(original)
            with fitz.open(original) as source:
                before = source[0].get_pixmap().samples
                v.export_crop(source[0], source[0].rect, Path(folder) / 'figure')
                self.assertEqual(before, source[0].get_pixmap().samples)
            self.assertEqual(digest, t.sha(original))

    def test_white_to_black_is_failure_but_original_dark_is_valid(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            white, black = [Path(folder) / name for name in ['white.png', 'black.png']]
            Image.new('RGB', (300, 200), 'white').save(white)
            Image.new('RGB', (300, 200), 'black').save(black)
            self.assertFalse(fidelity.compare_images(white, black)['pass'])
            self.assertTrue(fidelity.compare_images(black, black)['pass'])
            self.assertEqual(fidelity.compare_images(black, black)['new_black_on_source_white_fraction'], 0)

    def test_color_inversion_is_failure(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / name for name in ['source.png', 'candidate.png']]
            Image.new('RGB', (300, 200), '#2a9aab').save(paths[0])
            Image.new('RGB', (300, 200), '#d56554').save(paths[1])
            self.assertFalse(fidelity.compare_images(*paths)['pass'])

    def test_transparency_is_composited_against_white(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            a, b = [Path(folder) / name for name in ['source.png', 'candidate.png']]
            Image.new('RGB', (300, 200), 'white').save(a)
            Image.new('RGBA', (300, 200), (0, 0, 0, 0)).save(b)
            self.assertTrue(fidelity.compare_images(a, b)['pass'])

    def test_unsafe_embedded_jpeg_blocked_by_publication(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            r = Path(folder)
            data = io.BytesIO()
            Image.new('CMYK', (30, 20), (0, 0, 0, 0)).save(data, 'JPEG')
            uri = 'data:image/jpeg;base64,' + base64.b64encode(data.getvalue()).decode()
            (r / 'unsafe.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="30" height="20"><image href="' + uri + '" width="30" height="20"/></svg>')
            block = {'id': 'F1', 'type': 'image', 'source': {'document_id': 'D1', 'page': 1}, 'units': [], 'asset': 'unsafe.svg'}
            with self.assertRaisesRegex(ValueError, 'Unsafe SVG raster colors'):
                publishing.block_html(r, block, 'zh-Hans', 'faithful', publishing.LABELS['zh'])

    def test_build_and_render_enter_fidelity_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            r = Path(folder) / 'project'
            with contextlib.redirect_stdout(io.StringIO()):
                t.init(argparse.Namespace(project=str(r), title='Fixture', languages='zh-Hans', style='editorial', page_size='A4', columns=1))
            _, m, c = t.project(r)
            source = r / 'sources/a.txt'
            source.write_text('A source sentence.')
            c['sources'] = [{'id':'D001','name':'a.txt','file':'sources/a.txt','sha256':t.sha(source)}]
            block = t.add_block(c, 'D001', 'paragraph', {'element':'1'}, ['A source sentence.'])
            block['units'][0]['translations'] = {'zh-Hans':{'faithful':'一个原文句子。','interpretive':'一条原文句子。'}}
            t.write(r / 'content.json', c)
            with patch('asset_fidelity.verify_project', side_effect=ValueError('figure gate blocked')) as gate:
                with self.assertRaisesRegex(ValueError, 'figure gate blocked'):
                    publishing.build(r)
                with self.assertRaisesRegex(ValueError, 'figure gate blocked'):
                    publishing.render(r)
                self.assertEqual(gate.call_count, 2)

    def test_unsafe_color_audit_error(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            r = Path(folder) / 'project'
            with contextlib.redirect_stdout(io.StringIO()):
                t.init(argparse.Namespace(project=str(r), title='Fixture', languages='zh-Hans', style='editorial', page_size='A4', columns=1))
            _, m, c = t.project(r)
            source = r / 'sources/a.txt'
            source.write_text('Figure fixture')
            c['sources'] = [{'id': 'D001', 'name': 'a.txt', 'file': 'sources/a.txt', 'sha256': t.sha(source)}]
            data = io.BytesIO()
            Image.new('CMYK', (30, 20), (0, 0, 0, 0)).save(data, 'JPEG')
            svg = r / 'assets/a.svg'
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/jpeg;base64,' + base64.b64encode(data.getvalue()).decode() + '"/></svg>')
            t.add_block(c, 'D001', 'image', {'element': 'figure'}, [], asset='assets/a.svg')
            self.assertIn('unsafe-svg-raster-colors', [x['code'] for x in t.audit_data(r, m, c)['errors']])
