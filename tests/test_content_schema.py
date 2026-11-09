import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ContentSchemaTests(unittest.TestCase):
    def test_packaged_schema_matches_installed_skill_copy(self):
        relative = Path('schemas/content.schema.json')
        self.assertEqual(json.loads((ROOT / relative).read_text()),
                         json.loads((ROOT / 'skills/document-translation/references' / relative).read_text()))

    def test_public_examples_use_supported_types_and_label_policies(self):
        schema = json.loads((ROOT / 'schemas/content.schema.json').read_text())
        fields = schema['properties']['blocks']['items']['properties']
        types = set(fields['type']['enum'])
        policies = set(fields['label_policy']['enum'])
        self.assertIn('reference', types)
        self.assertIn('retained-original', policies)
        for path in (ROOT / 'skills/document-translation/examples').rglob('content.json'):
            for block in json.loads(path.read_text())['blocks']:
                self.assertIn(block['type'], types, str(path))
                if 'label_policy' in block:
                    self.assertIn(block['label_policy'], policies, str(path))
