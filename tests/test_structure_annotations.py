"""Source-only annotation lifecycle, using original private temporary PDFs. MIT."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'skills/document-translation/scripts')]
import prepare_structure_annotations as preparation
import freeze_structure_annotations as freezing
import source_structure as structure


class AnnotationEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'original.pdf'
        import fitz
        with fitz.open() as pdf:
            for number in range(1,3):
                page=pdf.new_page()
                page.insert_text((60,70),f'Original page {number}. All words must be retained.')
                page.insert_text((60,90),'A separate original paragraph supplies layout evidence.')
                page.insert_text((60,115),'A second font size exercises serialized numeric profile keys.',fontsize=9)
                page.insert_text((60,145),'A third font size remains immutable source evidence.',fontsize=12)
            pdf.save(self.source)

    def prepare_labeled(self):
        # No learned model or model-generated role may enter a blank label set.
        with patch.object(structure,'load_model',side_effect=AssertionError('Prediction leaked into preparation')):
            result=preparation.prepare([self.source],self.root/'evidence')
        path=Path(result['annotations']);data=json.loads(path.read_text())
        document=data['documents'][0]
        document['label_source']='Original fixture authored by this test; each printed line is a separate prose paragraph.'
        for page in document['pages']:
            page['_order_regions']=[[row['id']] for row in page['lines'] if row['text'].strip()]
            for row in page['lines']:
                row.update(_role='body',_group=row['id'])
        path=self.root/'labels.json'
        path.write_text(json.dumps(data));return path,data

    def test_source_only_preparation_preserves_all_pages_rows_and_native_ids(self):
        _,data=self.prepare_labeled();document=data['documents'][0]
        self.assertEqual([page['page'] for page in document['pages']],[1,2])
        self.assertEqual(document['source_page_count'],2)
        self.assertEqual(document['source_sha256'],hashlib.sha256(self.source.read_bytes()).hexdigest())
        for page in document['pages']:
            self.assertTrue(Path(page['source_image']).is_file())
            self.assertEqual({lid for row in page['lines'] for lid in row['native_line_ids']},
                             {row['id'] for row in page['native_lines']})
            self.assertTrue(all('predicted_role' not in row for row in page['lines']))
        original=json.loads((self.root/'evidence/unlabeled.json').read_text())
        self.assertTrue(all('_role' not in row for d in original['documents'] for p in d['pages'] for row in p['lines']))

    def test_frozen_hash_matches_bytes_and_existing_evidence_is_protected(self):
        labels,_=self.prepare_labeled();frozen=self.root/'frozen.json'
        result=freezing.freeze(labels,frozen)
        self.assertTrue(result['pass']);self.assertTrue(result['not_independent_gold_certification'])
        self.assertEqual(result['sha256'],hashlib.sha256(frozen.read_bytes()).hexdigest())
        self.assertTrue(frozen.with_suffix('.json.sha256').read_text().startswith(result['sha256']))
        with self.assertRaises(FileExistsError):freezing.freeze(labels,frozen)
        with self.assertRaises(FileExistsError):preparation.prepare([self.source],self.root/'evidence')

    def test_duplicate_whole_source_alias_is_refused_before_writing(self):
        alias=self.root/'renamed.pdf';alias.write_bytes(self.source.read_bytes())
        target=self.root/'duplicate'
        with self.assertRaisesRegex(ValueError,'Repeated source identity'):
            preparation.prepare([self.source,alias],target)
        self.assertFalse(target.exists())

    def test_label_completeness_requires_full_pages_and_nonduplicated_order(self):
        _,data=self.prepare_labeled();document=data['documents'][0]
        damaged=copy.deepcopy(data);damaged['documents'][0]['pages'].pop()
        self.assertFalse(freezing.audit(damaged)['pass'])
        document['pages'][0]['_order_regions'].append(document['pages'][0]['_order_regions'][0])
        self.assertFalse(freezing.audit(data)['pass'])

    def test_label_provenance_and_unresolved_reasons_are_required(self):
        _,data=self.prepare_labeled();document=data['documents'][0]
        document['label_source']='pending source review'
        self.assertFalse(freezing.audit(data)['pass'])
        document['label_source']='Original fixture author'
        row=document['pages'][0]['lines'][0];row['_assembly_unresolved']=True
        self.assertFalse(freezing.audit(data)['pass'])
        row['_unresolved_reason']='Two possible spatial interpretations require source review.'
        self.assertTrue(freezing.audit(data)['pass'])

    def test_accidental_source_text_and_geometry_edits_are_rejected(self):
        path,data=self.prepare_labeled()
        for key,value in [('text','Invented completion'),('bbox',[0,0,100,10])]:
            damaged=copy.deepcopy(data);damaged['documents'][0]['pages'][0]['lines'][0][key]=value
            path.write_text(json.dumps(damaged))
            with self.assertRaisesRegex(ValueError,'Physical-row evidence changed'):
                freezing.freeze(path,self.root/(key+'-frozen.json'))
            self.assertFalse((self.root/(key+'-frozen.json')).exists())

    def test_source_byte_change_is_rejected(self):
        labels,_=self.prepare_labeled();self.source.write_bytes(self.source.read_bytes()+b'\n% changed\n')
        with self.assertRaisesRegex(ValueError,'Source file changed'):
            freezing.freeze(labels,self.root/'frozen.json')

    def test_derived_source_lineage_is_recorded_and_repeated_family_rejected(self):
        parent='a'*64
        result=preparation.prepare([self.source],self.root/'derived',split='train',source_parent_sha256=[parent])
        data=json.loads(Path(result['annotations']).read_text())
        self.assertEqual(data['documents'][0]['source_parent_sha256'],[parent])
        _,labeled=self.prepare_labeled()
        labeled['documents'][0]['source_parent_sha256']=[parent]
        self.assertTrue(freezing.audit(labeled)['pass'])
        alias=copy.deepcopy(labeled['documents'][0]);alias.update(id='derived-copy',source_sha256='b'*64)
        labeled['documents'].append(alias)
        self.assertTrue(any('source family' in e for e in freezing.audit(labeled)['errors']))

    def test_malformed_lineage_rejected_before_evidence_is_created(self):
        for parents in [['invalid'],['A'*64]]:
            with self.assertRaisesRegex(ValueError,'lineage'):
                preparation.prepare([self.source],self.root/'bad-lineage',source_parent_sha256=parents)
            self.assertFalse((self.root/'bad-lineage').exists())
        with self.assertRaisesRegex(ValueError,'one source'):
            preparation.prepare([self.source,self.source],self.root/'bad-lineage',source_parent_sha256=['a'*64])


if __name__=='__main__':unittest.main()
