#!/usr/bin/env python3
"""Exercise actual complete translations through the offline editor, without semantic attestations."""
import argparse
import base64
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'skills/document-translation/scripts'))
import publishing
import translate as t
import asset_fidelity

EDITOR = ROOT / 'skills/document-translation/assets/document-layout-editor.html'

# Content and stable locators are checked independently of page count and scores.
FINGERPRINT = r'''root=>{
 const units={};for(const el of root.querySelectorAll('[data-uid]'))
  units[el.dataset.uid]=(units[el.dataset.uid]||'')+el.textContent;
 return {units,text:root.textContent.replace(/\s+/g,''),
  locators:[...root.querySelectorAll('[data-block][data-source-page]')].map(x=>[x.dataset.block,x.dataset.sourcePage]),
  sourcePageSets:[...root.querySelectorAll('[data-source-pages]')].map(x=>[x.dataset.uid||x.dataset.block||null,x.dataset.sourcePages]),
  images:[...root.querySelectorAll('img')].map(x=>({block:x.closest('[data-block]')?.dataset.block||null,src:x.getAttribute('src'),fallback:x.getAttribute('data-raster-fallback')}))};
}'''

# Compare the actually painted pages before any requested optimization/edit.
# Page counts alone miss changed heading styles or a different distribution.
PAINTED_PAGES = r'''d=>[...d.querySelectorAll('#edPages>.ed-page')].map(page=>{
 const origin=page.getBoundingClientRect(),round=x=>Math.round(x*10)/10;
 return [...page.querySelector('.ed-page-body').querySelectorAll('[data-block],.mast,h1,h2,h3,img')].map(el=>{
  const r=el.getBoundingClientRect(),s=d.defaultView.getComputedStyle(el);
  return {block:el.dataset.block||null,tag:el.tagName,text:el.textContent,
   geometry:[r.left-origin.left,r.top-origin.top,r.width,r.height].map(round),
   typography:[s.fontFamily,s.fontSize,s.lineHeight,s.fontWeight,s.margin,s.padding]};
 });
})'''


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def run(projects, output, browser=None):
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError('Use a fresh output directory; preserve previous regression evidence.')
    if output.is_relative_to(ROOT):
        raise ValueError('Keep private projects and regression evidence outside the public skill.')
    output.mkdir(parents=True)
    result = {'version': '1.0.3', 'checks': [], 'cases': [], 'pass': False,
              'semantic_review': 'not implied: the invoking agent must inspect both complete translations',
              'scope': 'Actual full HTML editions, direct disk import, measured optimization, manual controls, HTML/PDF/DOCX round trips'}

    def save():
        (output / 'full-document-editor-regression.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def check(case, name, passed, detail=None):
        result['checks'].append({'case': case, 'name': name, 'pass': bool(passed), 'detail': detail})
        save()
        if not passed:
            raise AssertionError(case + ': ' + name + ': ' + str(detail))

    def fingerprint(page):
        return page.evaluate('()=>(' + FINGERPRINT + ')(document.getElementById("documentFrame").contentDocument.querySelector(".ed-root"))')

    def preview(page, case):
        value = page.evaluate('Studio.preview()')
        check(case, 'pagination retains full text and fits pages', value['pass'] and value['textPreserved'] and
              all(not p['overflow'] and (p['chars'] or p['images']) for p in value['pages']),
              {'pages': len(value['pages']), 'errors': value['errors'], 'fill': [p['vertical_fill'] for p in value['pages']]})
        return value

    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, **({'executable_path': browser} if browser else {}))
        for number, project in enumerate(projects, 1):
            project, meta, content = t.project(project)
            check(project.name, 'complete selected content has both translations', not t.audit_data(project, meta, content)['errors'])
            for language in meta['target_languages']:
                for edition in meta['editions'] + ['alignment']:
                    case = f'{number:02d}-{project.name}-{language}-{edition}'
                    folder = output / case
                    folder.mkdir()
                    page = br.new_page(accept_downloads=True, viewport={'width': 1540, 'height': 1050})
                    page.set_default_timeout(120000)
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(EDITOR.as_uri())
                    page.wait_for_function('()=>window.studioReady')
                    source = project / 'outputs' / f'{language}-{edition}.html'
                    reader = br.new_page()
                    reader.goto(source.as_uri())
                    reader.wait_for_function('()=>window.translationReady || window.translationError', timeout=120000)
                    check(case, 'reader starts without layout errors', reader.evaluate('!window.translationError'))
                    original = reader.evaluate('()=>(' + FINGERPRINT + ')(document.querySelector(".reader"))')
                    expected = reader.evaluate('()=>[...document.querySelectorAll(".reader > .layout-document")].map(el=>JSON.parse(el.getAttribute("data-studio-layout")))')
                    painted = reader.evaluate('()=>(' + PAINTED_PAGES + ')(document)')
                    reader.close()
                    page.evaluate('(html)=>Studio.importHTML(html,"Full document regression")', source.read_text( encoding='utf-8'))
                    state = page.evaluate('JSON.parse(JSON.stringify(Studio.state))')
                    check(case, 'disk import preserves design, legends and running text', len(state['sections']) == len(expected) and all(
                        s['design'] == e['design'] and s.get('sourceDesign') == e.get('sourceDesign',e['design']) and
                        s.get('alignmentLabels') == e.get('alignmentLabels') and s['header'] == e['header'] and s['footer'] == e['footer']
                        for s, e in zip(state['sections'], expected)))
                    check(case, 'disk import preserves every unit, image and source locator', fingerprint(page) == original,
                          {'units': len(original['units']), 'images': len(original['images']), 'fingerprint': digest(original)})
                    before = preview(page, case)
                    imported_paint = page.evaluate('()=>(' + PAINTED_PAGES + ')(document.getElementById("documentFrame").contentDocument)')
                    check(case, 'disk import preserves every painted page and element geometry', painted == imported_paint,
                          {'reader_pages': len(painted), 'editor_pages': len(imported_paint),
                           'reader_paint_sha256': digest(painted), 'editor_paint_sha256': digest(imported_paint)})
                    print(json.dumps({'case': case, 'phase': 'disk-import', 'pages': len(before['pages'])}), flush=True)
                    page.evaluate('Studio.optimize()')
                    decision = page.evaluate('Studio.state.decisions.at(-1)')
                    check(case, 'real candidate geometry and ranking recorded', len(decision['candidates']) > 1 and
                          any(c['id'] == decision['chosen'] and c['safe'] for c in decision['candidates']),
                          {'chosen': decision['chosen'], 'mode': decision['ranking_mode'], 'candidates': len(decision['candidates'])})
                    check(case, 'automatic layout preserves full source surface', fingerprint(page) == original)
                    optimized = preview(page, case)
                    page.screenshot(path=str(folder / 'editor-optimized.png'))
                    # Change controls in preview mode, then verify painted geometry.
                    current = page.evaluate('Studio.state.sections[0].design')
                    settings = {'bodySize': current['size'] + .25, 'bodyLeading': min(2.2, current['leading'] + .03),
                                'marginX': current['mx'] + .5, 'paraGap': current['para'] + .2}
                    for key, value in settings.items():
                        page.locator('#' + key).fill(str(round(value, 5)))
                    page.locator('#applyLayout').click()
                    page.wait_for_function('(size)=>Math.abs(Studio.state.sections[0].design.size-size)<.001', arg=settings['bodySize'])
                    page.wait_for_function('()=>document.getElementById("documentFrame").contentDocument.querySelector(".ed-root")')
                    visible = page.evaluate('''()=>{const d=document.getElementById('documentFrame').contentDocument,root=d.querySelector('.ed-doc'),p=root.querySelector('p.paragraph:not(.block-caption,.block-metadata,.block-note,.block-keywords)')||root.querySelector('p'),s=d.defaultView.getComputedStyle(p),r=d.defaultView.getComputedStyle(root);return {size:parseFloat(s.fontSize),leading:parseFloat(s.lineHeight),para:parseFloat(s.marginBottom),margin:parseFloat(r.paddingLeft)}}''')
                    check(case, 'manual values change visible typography and margins',
                          abs(visible['size'] - settings['bodySize'] * 96 / 72) < .2 and
                          abs(visible['leading'] - settings['bodySize'] * 96 / 72 * settings['bodyLeading']) < .3 and
                          abs(visible['para'] - settings['paraGap'] * 96 / 25.4) < .2 and
                          abs(visible['margin'] - settings['marginX'] * 96 / 25.4) < .2, visible)
                    manual = page.evaluate('JSON.parse(JSON.stringify(Studio.state.sections[0]))')
                    page.evaluate('Studio.optimize()')
                    locked = page.evaluate('Studio.state.sections[0]')
                    check(case, 'subsequent optimization respects manual locks', all(
                        locked['design'][k] == manual['design'][k] for k in ['size', 'leading', 'mx', 'para']))
                    final = preview(page, case)
                    check(case, 'manual layout preserves every unit, image and locator', fingerprint(page) == original)
                    saved_state = page.evaluate('JSON.parse(JSON.stringify(Studio.state))')
                    for kind in ['html', 'docx']:
                        with page.expect_download() as download:
                            page.evaluate('(kind)=>Studio.exportFile(kind)', kind)
                        download.value.save_as(folder / ('edited.' + kind))
                    page.evaluate('window.print=()=>{window.regressionPrintCalled=true}')
                    page.evaluate('Studio.exportFile("pdf")')
                    page.wait_for_function('()=>window.regressionPrintCalled')
                    iframe_paint = page.evaluate('()=>(' + PAINTED_PAGES + ')(document.getElementById("documentFrame").contentDocument)')
                    page.emulate_media(media='print')
                    host_paint = page.evaluate('()=>(' + PAINTED_PAGES.replace('#edPages>.ed-page', '#printHost>.ed-page') + ')(document)')
                    check(case, 'print host retains exact preview geometry before PDF generation', host_paint == iframe_paint)
                    print_overflow = page.evaluate('''()=>[...document.querySelectorAll('#printHost>.ed-page')].map((p,i)=>({page:i+1,width:p.clientWidth,painted:p.scrollWidth})).filter(p=>p.painted>p.width+2)''')
                    check(case, 'print host has no horizontal overflow that can shrink PDF pages', not print_overflow, print_overflow)
                    pdf = folder / 'edited.pdf'
                    page.pdf(path=str(pdf), prefer_css_page_size=True, print_background=True)
                    import fitz
                    with fitz.open(pdf) as doc:
                        empty = [i+1 for i, p in enumerate(doc) if publishing.page_is_visually_empty(p)]
                        check(case, 'printed PDF page count and no blank pages', len(doc) == len(final['pages']) and not empty,
                              {'pdf_pages': len(doc), 'dom_pages': len(final['pages']), 'empty': empty})
                        for i, p in enumerate(doc):
                            p.get_pixmap(matrix=fitz.Matrix(.8, .8), alpha=False).save(folder / f'page-{i+1:04d}.png')
                    fidelity = asset_fidelity.verify_rendered_figures(project, page, pdf, 'editor-full-' + edition, '#printHost>.ed-page')
                    check(case, 'actual printed figures match source crops', fidelity['pass'],
                          {'figures': len(fidelity['figures']), 'missing': fidelity['missing_figures']})
                    page.emulate_media(media='screen')
                    # Reopen the delivered file itself. Reimporting HTML into
                    # the editor cannot prove its standalone resolver/print CSS.
                    exported = br.new_page()
                    standalone_errors = []
                    exported.on('pageerror', lambda e: standalone_errors.append(str(e)))
                    exported.goto((folder / 'edited.html').as_uri(), timeout=120000)
                    exported.wait_for_function('()=>window.studioAssetsReady || window.studioAssetsError', timeout=120000)
                    check(case, 'standalone image pool resolves without script errors',
                          exported.evaluate('!window.studioAssetsError') and not standalone_errors, standalone_errors)
                    exported.evaluate('async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode()))}')
                    standalone = exported.evaluate('()=>(' + FINGERPRINT + ')(document.querySelector(".ed-root"))')
                    check(case, 'standalone disk HTML retains text, units, locators and image bytes', standalone == original,
                          {'units': len(standalone['units']), 'images': len(standalone['images']), 'fingerprint': digest(standalone)})
                    del standalone
                    exported.emulate_media(media='print')
                    printed = exported.evaluate('()=>(' + PAINTED_PAGES + ')(document)')
                    editor_printed = page.evaluate('()=>(' + PAINTED_PAGES + ')(document.getElementById("documentFrame").contentDocument)')
                    check(case, 'standalone print preserves every painted element and typography', printed == editor_printed,
                          {'standalone_pages': len(printed), 'editor_pages': len(editor_printed)})
                    disk_pdf = folder / 'standalone.pdf'
                    exported.pdf(path=str(disk_pdf), prefer_css_page_size=True, print_background=True)
                    with fitz.open(pdf) as editor_pdf, fitz.open(disk_pdf) as reopened_pdf:
                        same = len(editor_pdf) == len(reopened_pdf)
                        differences = []
                        if same:
                            for i, (left, right) in enumerate(zip(editor_pdf, reopened_pdf), 1):
                                a = left.get_pixmap(matrix=fitz.Matrix(.8, .8), alpha=False)
                                b = right.get_pixmap(matrix=fitz.Matrix(.8, .8), alpha=False)
                                if a.width != b.width or a.height != b.height or a.samples != b.samples:
                                    differences.append(i)
                        check(case, 'standalone printed PDF matches editor pages pixel for pixel', same and not differences,
                              {'pages': len(reopened_pdf), 'different_pages': differences})
                    exported.close()
                    page.evaluate('(html)=>Studio.importHTML(html,"Exported HTML")', (folder / 'edited.html').read_text( encoding='utf-8'))
                    restored = page.evaluate('Studio.state.sections')
                    check(case, 'HTML round trip preserves all content and image bytes', fingerprint(page) == original)
                    check(case, 'HTML round trip preserves editable parameters and legends', all(
                        all(a.get(k) == b.get(k) for k in ['design','sourceDesign','locks','overrides','alignmentLabels','header','footer','title'])
                        for a,b in zip(saved_state['sections'],restored)))
                    preview(page, case)
                    with zipfile.ZipFile(folder / 'edited.docx') as archive:
                        check(case, 'DOCX CRC and document part valid', archive.testzip() is None and 'word/document.xml' in archive.namelist())
                    data = base64.b64encode((folder / 'edited.docx').read_bytes()).decode()
                    imported = page.evaluate('async s=>Formats.importDocx(Uint8Array.from(atob(s),c=>c.charCodeAt(0)).buffer)', data)
                    roundtrip = page.evaluate('(html)=>(' + FINGERPRINT + ')(Studio.sanitize(html).body)', imported['html'])
                    check(case, 'DOCX round trip preserves all visible text and image count',
                          roundtrip['text'] == original['text'] and len(roundtrip['images']) == len(original['images']),
                          {'original_characters': len(original['text']), 'docx_characters': len(roundtrip['text']),
                           'original_images': len(original['images']), 'docx_images': len(roundtrip['images'])})
                    check(case, 'no editor browser exceptions', not errors, errors)
                    result['cases'].append({'case': case, 'input_sha256': t.sha(source), 'before_pages': len(before['pages']),
                        'optimized_pages': len(optimized['pages']), 'manual_pages': len(final['pages']),
                        'ranking_mode': decision['ranking_mode'], 'chosen': decision['chosen'], 'units': len(original['units']),
                        'html_sha256': t.sha(folder/'edited.html'), 'pdf_sha256': t.sha(pdf), 'docx_sha256': t.sha(folder/'edited.docx')})
                    save()
                    print(json.dumps({'case': case, 'phase': 'completed', 'pages': len(final['pages'])}), flush=True)
                    page.close()
        br.close()
    result['pass'] = all(x['pass'] for x in result['checks'])
    save()
    return result


if __name__ == '__main__':
    from cli_encoding import configure_utf8
    configure_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', action='append', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--browser', default=os.environ.get('TRANSLATION_BROWSER'))
    args = parser.parse_args()
    run(args.project, args.output, args.browser)
