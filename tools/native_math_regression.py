"""Real-browser regression for bounded original-PDF inline runs.

Copyright 2026 Yufeng Zhan. MIT.
Run with --out PATH and optional --browser PATH (or TRANSLATION_BROWSER).
Uses existing PyMuPDF, FontTools, Pillow and Playwright dependencies.
"""
from pathlib import Path
from unittest.mock import patch
import argparse
import json
import os
import sys

import fitz
from playwright.sync_api import sync_playwright

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / 'skills/document-translation/scripts'))
import source_structure as structure
import pdf_text_recovery as recovery
import math_protection as math
import translate

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--browser', default=os.environ.get('TRANSLATION_BROWSER'))
args = parser.parse_args()
OUT = args.out.expanduser().resolve()
OUT.mkdir(parents=True, exist_ok=False)
source, pdf = OUT / 'owned-source.pdf', OUT / 'bounded-native.pdf'
with fitz.open() as doc:
    page = doc.new_page(width=350, height=180)
    page.insert_text((20, 55), 'Exact source glyphs across a narrow translated column.', fontsize=11)
    page.insert_text((20, 100), 'A separate neighboring source run must not collide.', fontsize=11)
    doc.save(source)
with fitz.open(source) as doc:
    raw = structure.raw_page(doc[0])
    rows = raw['native_lines']
    recovery.source_glyph_outlines(doc[0], rows, preserve_all=True)
    units = []
    for index, row in enumerate(rows):
        chars = [c for span in row['spans'] for c in span['chars']]
        styles = [{'native_glyph': c['native_glyph'], 'source_size_pt': 11,
                   'source_origin': c['origin'], 'bbox': c['bbox']} for c in chars]
        unit = {'id': 'U' + str(index), 'source': row['text']}
        math.attach(unit, [{'start': 0, 'end': len(row['text']), 'kind': 'source-glyph',
                           'character_styles': styles}])
        unit['protected_math'][0].update(page=1, body_size_pt=11)
        units.append(unit)
content = {'sources': [{'id': 'D', 'file': source.name, 'sha256': translate.sha(source)}],
           'blocks': [{'id': 'B' + str(i), 'source': {'document_id': 'D'}, 'units': [u]}
                      for i, u in enumerate(units)]}
markup = ('<!doctype html><style>@page{size:450pt 225pt;margin:0}'
          'body{margin:0;font-size:16px}.ed-page{width:600px;height:300px;box-sizing:border-box;padding:20px}'
          '.cols{display:grid;grid-template-columns:260px 260px;gap:20px}.col{min-width:0}</style>'
          '<div id="edPages"><div class="ed-page"><div class="cols">' +
          ''.join('<div class="col">' + math.source_render(u) + '</div>' for u in units) +
          '</div></div></div>')
(OUT / 'bounded-native.html').write_text(markup, encoding='utf-8')
with sync_playwright() as pw:
    browser = pw.chromium.launch(**({'executable_path': args.browser} if args.browser else {}))
    tab = browser.new_page()
    tab.set_content(markup)
    tab.emulate_media(media='print')
    geometry = tab.evaluate('''()=>[...document.querySelectorAll('.col')].map(col=>{
      const c=col.getBoundingClientRect(),s=col.querySelector('svg').getBoundingClientRect();
      return {column:[c.x,c.y,c.right,c.bottom],glyphs:[s.x,s.y,s.right,s.bottom]}})''')
    for g in geometry:
        a, b = g['column'], g['glyphs']
        assert b[0] >= a[0] - .01 and b[2] <= a[2] + .01, g
    native = math.prepare_native_pdf(tab)
    tab.pdf(path=str(pdf), print_background=True, prefer_css_page_size=True)
    with patch.object(translate, 'project', return_value=(OUT, {'editions': ['faithful']}, content)):
        (OUT / 'reports').mkdir(exist_ok=True)
        placements = math.overlay_native_pdf(OUT, pdf, native, 'zh-Hans-faithful')
        result = math.verify_pdf(OUT, tab, pdf, 'zh-Hans-faithful')
    assert result['pass'], result
    assert len(result['native_glyph_checks']) == sum(len(u['source']) for u in units)
    with fitz.open(pdf) as doc:
        doc[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(OUT / 'bounded-native.png')
    browser.close()
report = {'pass': True, 'browser': 'real Chromium; original PDF operator overlay',
          'geometries': geometry, 'native_glyph_checks': len(result['native_glyph_checks']),
          'source_sha256': translate.sha(source), 'pdf_sha256': translate.sha(pdf)}
(OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report))
