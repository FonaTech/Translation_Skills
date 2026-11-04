"""Keep reader controls independent of document language and content."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'skills/document-translation/scripts'))
import reader_ui
import publishing


class ReaderUITests(unittest.TestCase):
    def test_complete_catalogs(self):
        catalogs = json.loads((reader_ui.ASSETS / 'reader-locales.json').read_text())
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
