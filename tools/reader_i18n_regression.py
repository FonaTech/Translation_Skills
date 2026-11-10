#!/usr/bin/env python3
"""Real generated reader controls: locale detection, document invariants, actions."""
from pathlib import Path
import argparse
import contextlib
import io
import json
import sys
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'skills/document-translation/scripts'))
import translate as t
import publishing


def run(output, browser=None):
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    project = out / 'project'
    if project.exists():
        raise ValueError('Use a fresh output directory.')
    with contextlib.redirect_stdout(io.StringIO()):
        t.init(argparse.Namespace(project=str(project), title='Reader interface fixture', languages='zh-Hans', style='editorial', page_size='A4', columns=1))
    _, m, c = t.project(project)
    source = project / 'sources/owned.txt'
    source.write_text('Keep the value 12.5 V. Do not change the source.', encoding='utf-8')
    c['sources'] = [{'id': 'D001', 'name': 'owned.txt', 'file': 'sources/owned.txt', 'sha256': t.sha(source)}]
    b = t.add_block(c, 'D001', 'paragraph', {'element': '1'}, [source.read_text( encoding='utf-8')])
    b['units'][0]['translations'] = {'zh-Hans': {'faithful': '保留 12.5 V 这一数值。不要更改原文。', 'interpretive': '数值应保持为 12.5 V，原文内容不可更改。'}}
    t.write(project / 'content.json', c)
    publishing.build(project, browser)
    catalogs = t.read(ROOT / 'skills/document-translation/assets/reader-locales.json')
    report = {'version': '1.0.3', 'scope': 'Actual generated offline HTML; browser language simulation, not OS certification.', 'checks': [], 'pass': False}

    def check(name, value, detail=None):
        report['checks'].append({'name': name, 'pass': bool(value), 'detail': detail})
        t.write(out / 'reader-i18n-regression.json', report)
        if not value:
            raise AssertionError(name + ': ' + str(detail))

    check('16 complete catalogs', len(catalogs) == 16 and all(set(x) == set(catalogs['en']) and all(isinstance(v, str) and v.strip() for v in x.values()) for x in catalogs.values()))
    languages = [('en-US','en'),('zh-CN','zh-Hans'),('zh-TW','zh-Hant'),('ja-JP','ja'),('es-MX','es'),('fr-FR','fr'),('de-DE','de'),('pt-BR','pt'),('it-IT','it'),('ru-RU','ru'),('ko-KR','ko'),('ar-SA','ar'),('hi-IN','hi'),('id-ID','id'),('vi-VN','vi'),('tr-TR','tr'),('xx-ZZ','en')]
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, **({'executable_path': browser} if browser else {}))
        for tag, expected in languages:
            ctx = br.new_context(locale=tag)
            page = ctx.new_page()
            errors, requests = [], []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('request', lambda r: requests.append(r.url) if r.url.startswith(('http:', 'https:')) else None)
            for edition in ['faithful', 'interpretive', 'alignment']:
                page.goto((project / 'outputs' / ('zh-Hans-' + edition + '.html')).as_uri())
                page.wait_for_function('window.translationReady && window.TranslationReader')
                got = page.evaluate('''()=>({locale:TranslationReader.locale, labels:Object.fromEntries([...document.querySelectorAll('[data-reader-label]')].map(e=>[e.dataset.readerLabel,e.textContent])), lang:document.documentElement.lang, dir:document.documentElement.dir, uiDir:document.querySelector('[data-reader-toolbar]').dir})''')
                check(tag + ' ' + edition + ' labels and direction', got['locale'] == expected and got['lang'] == 'zh-Hans' and got['dir'] == 'ltr' and got['uiDir'] == ('rtl' if expected == 'ar' else 'ltr') and all(v == catalogs[expected][k] for k, v in got['labels'].items()), got)
                before = page.evaluate('document.querySelector(".reader").innerHTML')
                pages = page.evaluate('document.querySelector("#edPages").innerHTML')
                page.locator('[data-reader-language]').select_option('ja')
                check(tag + ' ' + edition + ' UI switch preserves text and pages', page.evaluate('document.querySelector(".reader").innerHTML') == before and page.evaluate('document.querySelector("#edPages").innerHTML') == pages)
                page.locator('[data-reader-language]').select_option('auto')
            check(tag + ' no remote requests or JS errors', not errors and not requests, {'errors': errors, 'requests': requests})
            ctx.close()

        ctx = br.new_context(locale='en-US', viewport={'width': 1366, 'height': 1000})
        page = ctx.new_page()
        file = project / 'outputs/zh-Hans-faithful.html'
        page.goto(file.as_uri()); page.wait_for_function('window.translationReady')
        page.evaluate('Object.defineProperty(navigator,"languages",{get:()=>["xx-ZZ","zh-HK","en-US"],configurable:true});window.dispatchEvent(new Event("languagechange"))')
        check('ordered system preferences and live changes', page.evaluate('TranslationReader.locale') == 'zh-Hant')
        page.locator('[data-reader-language]').select_option('es')
        page.evaluate('Object.defineProperty(navigator,"languages",{get:()=>["ja-JP"],configurable:true});window.dispatchEvent(new Event("languagechange"))')
        check('manual language overrides system change', page.evaluate('TranslationReader.locale') == 'es')
        page.reload(); page.wait_for_function('window.translationReady')
        check('manual language survives reload', page.evaluate('TranslationReader.locale') == 'es')
        page.locator('[data-reader-language]').select_option('auto')
        check('automatic mode restored', page.evaluate('TranslationReader.locale') == 'en')
        page.locator('[data-reader-action=view]').click()
        check('reading mode button works', page.evaluate('document.body.classList.contains("reading-flow")') and page.locator('[data-reader-action=view]').get_attribute('aria-pressed') == 'true')
        page.locator('[data-reader-action=view]').click()
        check('page mode button works', not page.evaluate('document.body.classList.contains("reading-flow")'))
        page.evaluate('window.print=()=>{window.readerPrintCalled=true}')
        page.locator('[data-reader-action=print]').click()
        check('print button invokes print', page.evaluate('window.readerPrintCalled'))
        for locale in catalogs:
            page.locator('[data-reader-language]').select_option(locale)
            for width in [1366, 390]:
                page.set_viewport_size({'width': width, 'height': 900})
                bounds = page.evaluate('''()=>[...document.querySelector('[data-reader-toolbar]').querySelectorAll('button,select')].map(e=>{const b=e.getBoundingClientRect();return {x:b.x,right:b.right,w:b.width,h:b.height}})''')
                check(locale + ' toolbar fits ' + str(width), all(x['x'] >= -.5 and x['right'] <= width + .5 and x['w'] > 0 and x['h'] > 0 for x in bounds), bounds)
                if locale in {'en', 'zh-Hans', 'zh-Hant', 'ja', 'ar', 'de'}:
                    page.screenshot(path=str(out / (locale + '-' + str(width) + '.png')))
        page.set_viewport_size({'width':1366,'height':1000})
        page.locator('[data-reader-language]').select_option('en')
        with page.expect_popup() as popup:
            page.locator('[data-reader-action=editor]').click()
        editor = popup.value
        editor.wait_for_function('()=>window.studioReady && Studio.state.sections.some(s=>s.html.includes("12.5 V"))', timeout=30000)
        check('editor button transfers actual document', editor.evaluate('Studio.state.sections.some(s=>s.html.includes("12.5 V"))'))
        check('reader UI locale leaves document language unchanged', editor.evaluate('Studio.state.lang') == 'zh-Hans')
        editor.close()
        page.emulate_media(media='print')
        check('reader toolbar excluded from printing', page.locator('[data-reader-toolbar]').evaluate('e=>getComputedStyle(e).display') == 'none')
        ctx.close()
        for name, setup, expected in [
            ('missing language APIs', 'Object.defineProperty(navigator,"languages",{get(){throw Error("missing")}});Object.defineProperty(navigator,"language",{get(){throw Error("missing")}})', 'en'),
            ('singular language API', 'Object.defineProperty(navigator,"languages",{get:()=>[]});Object.defineProperty(navigator,"language",{get:()=>"ja-JP"})', 'ja'),
            ('denied storage', 'Object.defineProperty(window,"localStorage",{get(){throw new DOMException("denied","SecurityError")}})', 'zh-Hans')]:
            cx = br.new_context(locale='zh-CN'); pg = cx.new_page(); pg.add_init_script(setup)
            pg.goto(file.as_uri()); pg.wait_for_function('window.translationReady')
            check(name, pg.evaluate('TranslationReader.locale') == expected)
            cx.close()
        cx = br.new_context(java_script_enabled=False)
        pg = cx.new_page(); pg.goto(file.as_uri())
        check('English controls without JavaScript', pg.locator('[data-reader-action=print]').text_content() == 'Print / Save PDF')
        cx.close(); br.close()
    report['pass'] = all(x['pass'] for x in report['checks'])
    t.write(out / 'reader-i18n-regression.json', report)
    print(json.dumps({'pass': report['pass'], 'checks': len(report['checks'])}))
    return report


if __name__ == '__main__':
    from cli_encoding import configure_utf8
    configure_utf8()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True); ap.add_argument('--browser')
    args = ap.parse_args()
    raise SystemExit(0 if run(args.output, args.browser)['pass'] else 1)
