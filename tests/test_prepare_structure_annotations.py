import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import prepare_structure_annotations as preparation


class SelectedPagePreparationTests(unittest.TestCase):
    def test_page_selection_preserves_source_page_numbers_and_document_profile(self):
        try:
            import fitz
        except ImportError:
            self.skipTest('PyMuPDF unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.pdf';pdf=fitz.open()
            for i in range(3):
                page=pdf.new_page();page.insert_text((40,50),f'Original source page {i+1} contains a complete paragraph.')
            pdf.save(source);pdf.close()
            output=root/'evidence'
            result=preparation.prepare([source],output,split='train',page_numbers=[2])
            data=json.loads(Path(result['annotations']).read_text())
            doc=data['documents'][0]
            self.assertEqual(result['pages'],1)
            self.assertEqual(doc['source_page_count'],3)
            self.assertEqual([page['page'] for page in doc['pages']],[2])
            self.assertEqual(len(list((output/'pages').glob('*.png'))),1)
            self.assertIn('body_fonts',doc['profile'])

    def test_page_spec_parses_lists_ranges_and_rejects_descending_range(self):
        self.assertEqual(preparation.parse_page_spec('1,4-6,9'),[1,4,5,6,9])
        with self.assertRaisesRegex(ValueError,'ascending positive'):
            preparation.parse_page_spec('5-3')


if __name__=='__main__':
    unittest.main()
