import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
from release_policy import PUBLIC_DOCUMENTATION, public_files


class ReleasePolicyTests(unittest.TestCase):
    def test_public_assets_survive_and_private_material_is_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            public = {
                'README.md', 'LICENSE', 'SHA256SUMS.txt', 'tools/release_policy.py',
                'docs/WORKFLOW.md', 'tools/full_document_editor_regression.py',
                '.github/workflows/validate.yml',
                'skills/document-translation/assets/models/training-data.json',
            }
            private = {
                'ACKNOWLEDGMENTS.md', 'docs/ACKNOWLEDGMENTS.md',
                'skills/document-translation/examples/demo/outputs/example.pdf',
                'skills/document-translation/demos/translated.html',
                'tools/outputs/translated.pdf',
                'UPLOAD_zh-CN.md', 'docs/UPLOAD_zh-CN.md', '译校与交付说明.md',
                'docs/译校与交付说明.md', 'validation/report.json',
                'docs/UPLOAD_ZH-cn.md', 'docs/DELIVERY_NOTES.md',
                'docs/delivery-notes.md', 'tools/private/source.pdf',
                'skills/document-translation/VALIDATION/report.json',
                'docs/delivery/recipient.md', 'tools/.env',
                'work/private.pdf', 'outputs/paper.pdf', 'private/report.md',
                'notes-for-recipient.md', 'tools/__pycache__/module.pyc',
                'skills/document-translation/examples/demo/reports/layout.json',
                'skills/document-translation/screenshots/review.png',
                'skills/document-translation/references/UPLOAD_zh-CN.md',
                'skills/document-translation/references/public-test-provenance.json',
                'tools/PUBLIC-TEST-PROVENANCE.JSON',
                'tools/recipient-notes.md', 'tools/standalone-explanation.md',
                'skills/document-translation/交付说明.md',
                'tools/session.log', 'tools/.DS_Store', 'tools/old.bak',
            }
            for name in public | private:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture', encoding='utf-8')
            actual = {p.relative_to(root).as_posix() for p in public_files(root)}
            self.assertEqual(actual, public)
            without_manifest = {p.relative_to(root).as_posix() for p in public_files(root, include_manifest=False)}
            self.assertEqual(without_manifest, public - {'SHA256SUMS.txt'})

    def test_symlink_is_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'tools').mkdir()
            (root / 'private.txt').write_text('local-only')
            try:
                (root / 'tools/leak.txt').symlink_to(root / 'private.txt')
            except (OSError, NotImplementedError):
                self.skipTest('Symlinks unavailable on this platform')
            self.assertEqual(public_files(root), [])

    def test_documentation_requires_an_explicit_public_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            public = set(PUBLIC_DOCUMENTATION) | {
                'codex/README.md', 'claude-plugin/README.md',
                'opencode/README.md', 'clouds-coder/README.md',
            }
            private = {
                'docs/recipient-notes.md', 'docs/standalone-explanation.md',
                'docs/regression-report.json', 'docs/review-screenshot.png',
                'docs/UPLOAD_zh-CN.md', 'docs/交付说明.md',
                'docs/personal/source.pdf',
            }
            for name in public | private:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture', encoding='utf-8')
            actual = {p.relative_to(root).as_posix() for p in public_files(root)}
            self.assertEqual(actual, public)
