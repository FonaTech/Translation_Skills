"""Keep reader controls independent of document language and content."""
import json
from html import unescape
import re
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'skills/document-translation/scripts'))
import reader_ui
import publishing


class ReaderUITests(unittest.TestCase):
    def test_interior_excerpt_uses_compact_mast_without_invented_title(self):
        source = {'id': 'D001', 'name': 'Long_source_filename.pdf', 'selection_scope': {'pages': [5]}}
        design = {'family': 'source', 'id': 'source-D001', 'columns': 2}
        output = publishing.wrap_document(source, {'design': design, 'route': 'source'}, '<p>Interior content.</p>', 'zh-Hans', 'faithful', publishing.LABELS['zh'])
        self.assertIn('excerpt-mast', output)
        self.assertNotIn('<h1>', output)
        self.assertIn('Interior content.', output)
        complete = dict(source)
        complete.pop('selection_scope')
        output = publishing.wrap_document(complete, {'design': design, 'route': 'source'}, '<p>Full content.</p>', 'zh-Hans', 'faithful', publishing.LABELS['zh'])
        self.assertIn('<h1>Long_source_filename.pdf</h1>', output)

    def test_painted_layout_persists_for_direct_disk_import(self):
        original = {'design': {'size': 9.5}, 'title': 'Original'}
        chosen = {'design': {'size': 10.5}, 'sourceDesign': {'size': 9.5}, 'title': 'Title "quoted" <text>'}
        opening = '<section class="layout-document" data-layout-doc="D001" data-studio-layout="' + publishing.h(json.dumps(original)) + '">'
        body = '<p data-uid="u1">Keep text &amp; symbols.</p>'
        html = opening + body + '</section>'
        result = publishing.persist_layout_metadata(html, [chosen])
        stored = json.loads(unescape(re.search(r'data-studio-layout="([^"]+)"', result).group(1)))
        self.assertEqual(stored, chosen)
        self.assertIn(body, result)
        with self.assertRaises(ValueError):
            publishing.persist_layout_metadata(html, [])
        with self.assertRaises(ValueError):
            publishing.persist_layout_metadata(html, [chosen, chosen])

    def test_static_layout_metadata_matches_runtime_without_executing_script(self):
        m = {'title': 'Fixture', 'editions': ['faithful', 'interpretive'], 'author_credit': 'Credit'}
        source = {'id': 'D001', 'name': 'input.pdf', 'display_title': 'Visible title', 'running_title': 'Running title'}
        design = {'family': 'source', 'id': 'source-D001', 'page_mm': [216, 279], 'margin_x_mm': 15, 'margin_y_mm': 17, 'columns': 2, 'body_pt': 10, 'line_height': 1.5, 'paragraph_gap_mm': 1.8, 'heading_gap_mm': 3, 'accent': '#123456'}
        for edition in ['faithful', 'interpretive', 'alignment']:
            settings = publishing.document_section(m, source, design, 'zh-Hans', edition, publishing.LABELS['zh'])
            output = publishing.wrap_document(source, {'design': design, 'route': 'source'}, '<p>Visible source only.</p>', 'zh-Hans', edition, publishing.LABELS['zh'], settings=settings)
            stored = json.loads(unescape(re.search(r'data-studio-layout="([^"]+)"', output).group(1)))
            self.assertEqual(stored['design'], settings['design'])
            self.assertEqual(stored['sourceDesign'], settings['design'])
            self.assertEqual(stored['alignmentLabels'], settings['alignmentLabels'])
            self.assertEqual(stored['header'], 'Running title')
            self.assertEqual(stored['footer'], 'Credit')
            self.assertEqual(stored['title'], 'Visible title')
            self.assertEqual(stored['design']['cols'], 1 if edition == 'alignment' else 2)
            self.assertNotIn('<script', output)

    def test_complete_catalogs(self):
        catalogs = json.loads((reader_ui.ASSETS / 'reader-locales.json').read_text( encoding='utf-8'))
        self.assertEqual(len(catalogs), 16)
        for labels in catalogs.values():
            self.assertEqual(set(labels), set(catalogs['en']))
            self.assertTrue(all(isinstance(x, str) and x.strip() for x in labels.values()))

    def test_toolbar_escapes_title_and_defaults_to_english(self):
        output = reader_ui.toolbar('<script>source & title</script>', 'faithful')
        self.assertNotIn('<script>', output)
        self.assertIn('&lt;script&gt;source &amp; title&lt;/script&gt;', output)
        self.assertIn('Faithful complete edition', output)
        self.assertIn('Print / Save PDF', output)
        for action in ['view', 'editor', 'print']:
            self.assertIn('data-reader-action="' + action + '"', output)

    def test_generator_embeds_reader_without_changing_body_language(self):
        m = {'title': '原文标题', 'direction': {'zh-Hans': 'ltr'}}
        body = '<p data-uid="u1">数值 12.5 V；不得补全。</p>'
        output = publishing.make_document(m, {'sources': []}, 'zh-Hans', 'faithful', body, {'documents': []})
        self.assertIn('<html lang="zh-Hans" dir="ltr">', output)
        self.assertIn(body, output)
        self.assertIn('window.TranslationReader=', output)
        self.assertIn('data-reader-toolbar', output)
        self.assertIn('window.TranslationReader.t(\'popup\')', output)
        self.assertIn('lang="en" dir="ltr"', output)

    def test_runtime_is_self_contained_valid_script_text(self):
        script = reader_ui.runtime()
        self.assertIn(';\n/* Original', script)
        self.assertNotIn('</script', script.lower())
        self.assertNotIn('fetch(', script)
        self.assertIn("'languagechange'", script)
        self.assertIn("'en'", script)

    def test_print_only_legacy_toolbar_has_only_supported_actions(self):
        output = reader_ui.toolbar('Legacy document', 'alignment', full=False)
        self.assertIn('data-reader-action="print"', output)
        self.assertNotIn('data-reader-action="view"', output)
        self.assertNotIn('data-reader-action="editor"', output)
