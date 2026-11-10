"""Offline reader chrome, independent of the document's target language."""
from pathlib import Path
import html
import json

ASSETS = Path(__file__).resolve().parent.parent / 'assets'


def toolbar(title, edition, full=True):
    labels = json.loads((ASSETS / 'reader-locales.json').read_text( encoding='utf-8'))['en']
    esc = lambda x: html.escape(str(x), quote=True)
    label = edition if edition in {'faithful', 'interpretive', 'alignment'} else 'faithful'
    actions = ''
    if full:
        actions = ('<button type="button" data-reader-action="view" data-reader-label="view" aria-pressed="false" onclick="TranslationReader.toggle()">Reading / Pages</button>'
                   '<button type="button" data-reader-action="editor" data-reader-label="editor" onclick="window.openTranslationEditor()">Open in layout editor</button>')
    return ('<nav class="toolbar" data-reader-toolbar lang="en" dir="ltr">'
            '<span class="reader-title">' + esc(title) + ' · <span data-reader-label="' + label + '">' + esc(labels[label]) + '</span></span>' + actions +
            '<button type="button" data-reader-action="print" data-reader-label="print" onclick="window.print()">Print / Save PDF</button>'
            '<select data-reader-language aria-label="Interface language" title="Interface language"><option value="auto" data-reader-label="auto">System language</option></select></nav>')


def runtime():
    data = json.dumps(json.loads((ASSETS / 'reader-locales.json').read_text( encoding='utf-8')), ensure_ascii=False).replace('<', '\u003c')
    return 'const TRANSLATION_READER_LOCALES=' + data + ';' + chr(10) + (ASSETS / 'reader-i18n.js').read_text( encoding='utf-8')


def styles():
    return '''
.toolbar[data-reader-toolbar]{display:flex;align-items:center;flex-wrap:wrap;gap:8px;font:14px/1.4 system-ui,sans-serif}
.toolbar[data-reader-toolbar] .reader-title{flex:1 1 220px;min-width:0;overflow-wrap:anywhere}
.toolbar[data-reader-toolbar] button,.toolbar[data-reader-toolbar] select{font:inherit;margin:0;max-width:100%;white-space:normal;border:1px solid #9abcca;background:#193445;color:white;border-radius:5px;padding:7px 10px}
.toolbar[data-reader-toolbar] select{max-width:190px}.toolbar[data-reader-toolbar] option{background:white;color:#18242e}
.toolbar[data-reader-toolbar] :focus-visible{outline:2px solid #fff;outline-offset:2px}
@media(max-width:600px){.toolbar[data-reader-toolbar]{font-size:12px;padding:10px}.toolbar[data-reader-toolbar] .reader-title{flex-basis:100%}.toolbar[data-reader-toolbar] button{flex:1 1 110px}.toolbar[data-reader-toolbar] select{flex:1 1 110px;max-width:100%}}
@media print{.toolbar[data-reader-toolbar]{display:none!important}}
'''.strip()
