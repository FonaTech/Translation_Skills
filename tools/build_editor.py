#!/usr/bin/env python3
"""Build the offline single-file editor from maintained original sources."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'skills/document-translation/assets'


def build():
    e = ASSETS / 'editor'
    s = (e / 'editor.html').read_text()
    model = ASSETS / 'layout-model.js'
    data = {
        'EDITOR_CSS': (e / 'editor.css').read_text(),
        'CATALOG': 'const CATALOG=' + json.dumps(json.loads((ASSETS / 'layout-catalog.json').read_text())['presets'], ensure_ascii=False) + '; const FAMILY_CSS=' + json.dumps((ASSETS / 'families.css').read_text(), ensure_ascii=False) + '; const MIT_TEXT=' + json.dumps((ROOT / 'LICENSE').read_text()) + ';',
        'I18N': 'const EDITOR_LOCALES=' + json.dumps({p.stem:json.loads(p.read_text()) for p in sorted((e/'locales').glob('*.json'))},ensure_ascii=False) + ';const EDITOR_ERROR_KEYS=' + (e/'error-keys.json').read_text() + ';\n' + (e/'i18n.js').read_text(),
        'ARCHIVE': (e / 'archive.js').read_text(),
        'FORMATS': (e / 'svg.js').read_text() + '\n' + (e / 'formats.js').read_text(),
        'MODEL': (model.read_text() if model.exists() else '') + '\n' + (ASSETS / 'layout-planner.js').read_text(),
        'LAYOUT': (ASSETS / 'layout-runtime.js').read_text(),
        'APP': (e / 'app.js').read_text(),
    }
    for name, value in data.items():
        s = s.replace('/* ' + name + ' */', value)
    assert not re.search(r'/\* (?:I18N|CATALOG|APP|LAYOUT|MODEL|ARCHIVE|FORMATS|EDITOR_CSS) \*/', s)
    target = ASSETS / 'document-layout-editor.html'
    target.write_text(s)
    return target


if __name__ == '__main__':
    print(build())
