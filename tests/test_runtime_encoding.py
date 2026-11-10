"""Exercise real CP936 streams and reject locale-dependent document I/O. MIT."""
import ast
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/document-translation/scripts'
sys.path.insert(0, str(SCRIPTS))
import runtime_encoding


class RuntimeEncodingTests(unittest.TestCase):
    def test_cp936_stream_reproduces_failure_then_roundtrips_utf8(self):
        expected = '简体中文 繁體中文 日本語 العربية ∫α₂ → 😀'
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding='cp936', errors='strict')
        with self.assertRaises(UnicodeEncodeError):
            stream.write(expected)
        with patch.dict(os.environ), patch.object(sys, 'stdout', stream):
            runtime_encoding.configure_utf8()
            runtime_encoding.configure_utf8()
            print(expected, end='')
            stream.flush()
            self.assertEqual(stream.encoding, 'utf-8')
        self.assertEqual(raw.getvalue().decode('utf-8'), expected)
        stream.detach()

    def test_capturing_host_and_consumed_stdin_are_preserved(self):
        captured = io.StringIO()
        incoming = io.TextIOWrapper(io.BytesIO(b'ab'), encoding='cp936')
        self.assertEqual(incoming.read(1), 'a')
        with patch.dict(os.environ), patch.object(sys, 'stdin', incoming), patch.object(sys, 'stdout', captured), patch.object(sys, 'stderr', None):
            runtime_encoding.configure_utf8()
            print('中文 😀')
            self.assertIs(sys.stdout, captured)
            self.assertEqual(incoming.read(), 'b')
        self.assertEqual(captured.getvalue(), '中文 😀\n')

    def test_child_environment_overrides_stale_gbk_without_mutating_parent(self):
        source = {'PYTHONUTF8': '0', 'PYTHONIOENCODING': 'gbk', 'KEEP': 'value'}
        env = runtime_encoding.utf8_environment(source)
        self.assertEqual(source['PYTHONIOENCODING'], 'gbk')
        self.assertEqual(env['KEEP'], 'value')
        result = subprocess.run([sys.executable, '-c', 'import sys;print(sys.flags.utf8_mode);print("\\u4e2d\\u6587 \\u222b\\u03b1 \\U0001f600")'],
                                env=env, capture_output=True, check=True)
        self.assertEqual(result.stdout.decode('utf-8').splitlines(), ['1', '中文 ∫α 😀'])

    def test_json_models_reader_and_source_files_ignore_cp936_default(self):
        import reader_ui
        import source_structure
        import figure_learning
        import translate
        original_open = io.open
        # Simulate a legacy locale even when the host enables Python UTF-8 mode.
        original_text_encoding = io.text_encoding
        def legacy_text_encoding(encoding, stacklevel=2):
            return 'locale' if encoding is None else original_text_encoding(encoding, stacklevel)
        def gbk_open(file, mode='r', buffering=-1, encoding=None, *args, **kwargs):
            if 'b' not in mode and encoding in {None, 'locale'}:
                encoding = 'cp936'
            return original_open(file, mode, buffering, encoding, *args, **kwargs)
        payload = {'text': '中文 日本語 العربية ∫α 😀', 'source': 'No added text.'}
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / '中文 日本語 😀' / '内容.json'
            target.parent.mkdir()
            with patch('io.text_encoding', side_effect=legacy_text_encoding), patch('io.open', side_effect=gbk_open):
                # Control proves this test actually imposes the legacy default.
                with self.assertRaises(UnicodeEncodeError):
                    target.with_suffix('.bad').write_text(payload['text'])
                translate.write(target, payload)
                self.assertEqual(translate.read(target), payload)
                self.assertIn('TRANSLATION_READER_LOCALES', reader_ui.runtime())
                self.assertTrue(source_structure.load_model())
                self.assertTrue(figure_learning.load_model())
                target.write_bytes(b'{"bad":"\xff"}')
                with self.assertRaises(UnicodeDecodeError):
                    translate.read(target)

    def test_cli_emits_unicode_errors_to_a_redirected_legacy_console(self):
        env = {**os.environ, 'PYTHONUTF8': '0', 'PYTHONIOENCODING': 'cp936'}
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / '中文 ∫ 😀'
            result = subprocess.run([sys.executable, '-X', 'utf8=0', str(SCRIPTS / 'translate.py'),
                'init', str(project), '--title', '日本語 ∫α 😀', '--languages', 'zh-Hans'],
                env=env, capture_output=True, check=True)
            self.assertIn(str(project.resolve()), result.stdout.decode('utf-8'))
            self.assertEqual(json.loads((project / 'project.json').read_text(encoding='utf-8'))['title'], '日本語 ∫α 😀')
            result = subprocess.run([sys.executable, '-X', 'utf8=0', str(SCRIPTS / 'translate.py'),
                'init', str(project), '--title', '日本語', '--languages', 'zh-Hans'],
                env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Existing project preserved', result.stderr.decode('utf-8'))
            self.assertNotIn('UnicodeEncodeError', result.stderr.decode('utf-8'))

    def test_owned_text_io_and_subprocesses_have_explicit_encoding(self):
        failures = []
        for directory in [SCRIPTS, ROOT / 'tools']:
            for path in directory.glob('*.py'):
                tree = ast.parse(path.read_text(encoding='utf-8'))
                for call in ast.walk(tree):
                    if not isinstance(call, ast.Call):
                        continue
                    name = call.func.attr if isinstance(call.func, ast.Attribute) else call.func.id if isinstance(call.func, ast.Name) else ''
                    keywords = {k.arg: k.value for k in call.keywords}
                    if name in {'read_text', 'write_text'} and 'encoding' not in keywords and len(call.args) < (1 if name == 'read_text' else 2):
                        failures.append(f'{path.name}:{call.lineno}: {name}')
                    text_mode = any(isinstance(keywords.get(key), ast.Constant) and keywords[key].value is True for key in ('text', 'universal_newlines'))
                    if name in {'run', 'Popen', 'check_output'} and text_mode and 'encoding' not in keywords:
                        failures.append(f'{path.name}:{call.lineno}: subprocess text')
        self.assertEqual(failures, [])


if __name__ == '__main__':
    runtime_encoding.configure_utf8()
    unittest.main()
