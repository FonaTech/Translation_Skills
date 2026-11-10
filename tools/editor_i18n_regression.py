#!/usr/bin/env python3
"""Behavioral, offline UI-language and document-preservation browser regression."""
from pathlib import Path
import argparse,json,base64,zipfile,xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright
import fitz
ROOT=Path(__file__).resolve().parent.parent
EDITOR=ROOT/'skills/document-translation/assets/document-layout-editor.html'

def run(output,browser=None):
 out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
 report={'scope':'Offline UI locales, document invariants, native exports, print pagination and responsive controls. Browser simulation is not an OS or harness certification.','checks':[],'pass':False}
 def check(name,value,detail=None):report['checks'].append({'name':name,'pass':bool(value),'detail':detail})
 with sync_playwright() as pw:
  br=pw.chromium.launch(headless=True,**({'executable_path':browser} if browser else {}))
  catalogs={p.stem:json.loads(p.read_text( encoding='utf-8')) for p in (ROOT/'skills/document-translation/assets/editor/locales').glob('*.json')}
  import re
  check('sixteen complete catalogs and identical placeholders',len(catalogs)==16 and all(set(d)==set(catalogs['en']) and all(re.findall(r'\{[a-zA-Z]+\}',v)==re.findall(r'\{[a-zA-Z]+\}',catalogs['en'][k]) for k,v in d.items()) for d in catalogs.values()))
  for source,expected in [('en-US','en'),('zh-CN','zh-Hans'),('zh-SG','zh-Hans'),('zh-TW','zh-Hant'),('zh-HK','zh-Hant'),('ja-JP','ja'),('es-MX','es'),('ar-SA','ar'),('de-DE','de'),('fr-FR','fr'),('pt-BR','pt'),('it-IT','it'),('ru-RU','ru'),('ko-KR','ko'),('hi-IN','hi'),('id-ID','id'),('vi-VN','vi'),('tr-TR','tr'),('xx-ZZ','en')]:
   ctx=br.new_context(locale=source);pg=ctx.new_page();errors=[];pg.on('pageerror',lambda e:errors.append(str(e)));pg.goto(EDITOR.as_uri());pg.wait_for_function('window.studioReady')
   got=pg.evaluate('({locale:I18n.locale,preference:I18n.preference,lang:document.documentElement.lang,dir:document.documentElement.dir,title:document.title,open:document.getElementById("openBtn").textContent})')
   check('fresh browser language '+source,got['locale']==expected and got['lang']==expected and got['preference']=='auto' and got['dir']==('rtl' if expected=='ar' else 'ltr') and not errors,got);ctx.close()
  ctx=br.new_context(locale='en-US',viewport={'width':1540,'height':1050},accept_downloads=True);pg=ctx.new_page();requests=[];errors=[];pg.on('request',lambda r:requests.append(r.url) if r.url.startswith(('http:','https:')) else None);pg.on('pageerror',lambda e:errors.append(str(e)));pg.goto(EDITOR.as_uri());pg.wait_for_function('window.studioReady')
  matches=pg.evaluate('Object.fromEntries(["zh-Hans-TW","zh-Hant-CN","zh_HK","es_AR","ja","ar-EG","zho","bad:lang"].map(x=>[x,I18n.match(x)]))')
  check('script-aware Chinese and region matching',matches=={'zh-Hans-TW':'zh-Hans','zh-Hant-CN':'zh-Hant','zh_HK':'zh-Hant','es_AR':'es','ja':'ja','ar-EG':'ar','zho':None,'bad:lang':None},matches)
  pg.evaluate('Object.defineProperty(navigator,"languages",{get:()=>["xx-ZZ","ja-JP","en-US"],configurable:true});window.dispatchEvent(new Event("languagechange"))')
  check('ordered preference and live automatic change',pg.evaluate('I18n.locale')=='ja')
  pg.locator('#uiLanguage').select_option('es');pg.reload();pg.wait_for_function('window.studioReady');check('manual override persists reload',pg.evaluate('I18n.locale==="es"&&I18n.preference==="es"'))
  pg.evaluate('Object.defineProperty(navigator,"languages",{get:()=>["ar-SA"],configurable:true});window.dispatchEvent(new Event("languagechange"))')
  check('system change respects manual override',pg.evaluate('I18n.locale')=='es')
  pg.locator('#uiLanguage').select_option('auto');check('automatic mode follows latest preferences',pg.evaluate('I18n.locale')=='ar')
  source='''<!doctype html><html lang="zh-Hans" dir="ltr"><head><style>.paper{width:210mm;padding:18mm;--page-width:210mm;--page-height:297mm;--body-size:11pt}</style></head><body><main class="paper"><h1>界面语言不可改变正文</h1><p>原文 English العربية。0 −12.5 μm CO₂ N/A。</p><p dir="rtl" lang="ar">هذه فقرة عربية أصلية.</p><table><tr><th>项目</th><th>数值</th></tr><tr><td>电压</td><td>0.85 V</td></tr></table></main></body></html>'''
  pg.evaluate('(html)=>Studio.importHTML(html,"Locale invariant")',source);pg.locator('#marginX').fill('23');pg.locator('#headerText').fill('Unsaved header');pg.evaluate("document.getElementById('findText').value='English'");before=pg.evaluate('JSON.stringify(Studio.state)');body=pg.evaluate('document.getElementById("documentFrame").contentDocument.querySelector(".ed-root").innerHTML')
  for language in sorted(catalogs):
   pg.locator('#uiLanguage').select_option(language)
   after=pg.evaluate('JSON.stringify(Studio.state)');current=pg.evaluate('document.getElementById("documentFrame").contentDocument.querySelector(".ed-root").innerHTML')
   check(language+' switch preserves complete document and pending controls',after==before and current==body and pg.locator('#marginX').input_value()=='23' and pg.locator('#headerText').input_value()=='Unsaved header' and pg.locator('#findText').input_value()=='English')
   bindings=pg.evaluate('Array.from(document.querySelectorAll("[data-i18n]")).filter(e=>!e.id||!["selectionStatus"].includes(e.id)).every(e=>{let p={};try{p=JSON.parse(e.dataset.i18nParams||"{}")}catch{}return e.textContent===I18n.t(e.dataset.i18n,p)})')
   check(language+' all explicit UI message bindings resolve',bindings)
   check(language+' help and prompts localized',pg.evaluate('document.getElementById("helpContent").textContent===new DOMParser().parseFromString(I18n.help(MIT_TEXT),"text/html").body.textContent&&I18n.t("prompt.rows")!=="prompt.rows"'))
  pg.evaluate('Studio.render()');r=pg.evaluate('Studio.preview()');check('Arabic UI preserves Chinese document direction and pagination',r['pass'] and pg.evaluate('document.getElementById("documentFrame").contentDocument.documentElement.lang==="zh-Hans"&&document.getElementById("documentFrame").contentDocument.documentElement.dir==="ltr"'))
  for kind in ['html','docx','txt']:
   with pg.expect_download() as item:pg.evaluate('(kind)=>Studio.exportFile(kind)',kind)
   item.value.save_as(out/('locale-export.'+kind))
  exported=(out/'locale-export.html').read_text( encoding='utf-8');check('HTML exports actual source language', '<html lang="zh-Hans" dir="ltr">' in exported)
  text=(out/'locale-export.txt').read_text( encoding='utf-8');check('TXT after preview retains all source text',all(x in text for x in ['界面语言不可改变正文','−12.5','هذه فقرة عربية أصلية.','0.85 V']))
  with zipfile.ZipFile(out/'locale-export.docx') as z:
   check('DOCX export CRC',z.testzip() is None);d=ET.fromstring(z.read('word/document.xml'));styles=ET.fromstring(z.read('word/styles.xml'));ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}';langs=[e.get(ns+'val') for e in d.iter(ns+'lang')];check('DOCX language tags retain multilingual source', 'zh-Hans' in langs and 'ar' in langs,langs)
   check('DOCX source numbers and Arabic text retained',all(x in ''.join(e.text or '' for e in d.iter(ns+'t')) for x in ['−12.5','هذه فقرة عربية أصلية.','0.85 V']))
  data=base64.b64encode((out/'locale-export.docx').read_bytes()).decode();imp=pg.evaluate('async data=>Formats.importDocx(Uint8Array.from(atob(data),c=>c.charCodeAt(0)).buffer)',data);check('DOCX reimport language preserved',imp['lang']=='zh-Hans' and imp['dir']=='ltr' and 'lang="ar"' in imp['html'],{'lang':imp['lang'],'dir':imp['dir']})
  # Actual PDF export route populates the print host; avoid opening an interactive OS dialog.
  pg.evaluate('window.print=()=>{window.printCalled=true}');pg.evaluate('Studio.exportFile("pdf")');pg.wait_for_function('window.printCalled');pg.pdf(path=str(out/'locale-print.pdf'),prefer_css_page_size=True,print_background=True)
  with fitz.open(out/'locale-print.pdf') as d:check('editor PDF page count matches DOM without blank tails',len(d)==len(r['pages']) and all(p.get_text().strip() for p in d),{'pdf_pages':len(d),'dom_pages':len(r['pages'])})
  # A corrupt but syntactically allowed bitmap must fail the geometry gate.
  pg.evaluate('html=>Studio.importHTML(html,"Broken image")','<html lang="en"><body><h1>Image gate</h1><img alt="broken test image" src="data:image/png;base64,AAAA"></body></html>');broken=pg.evaluate('Studio.preview()');check('broken image blocks successful layout',not broken['pass'] and any('Image failed to decode' in e for e in broken['errors']),broken)
  pg.evaluate('(html)=>Studio.importHTML(html,"Responsive multilingual UI")',source)
  for locale in sorted(catalogs):
   for width,height in [(1540,1050),(390,844)]:
    pg.set_viewport_size({'width':width,'height':height});pg.evaluate('(l)=>I18n.select(l)',locale);pg.evaluate("document.getElementById('toast').style.display='none';if(innerWidth<=540){document.getElementById('zoom').value='fit';document.getElementById('zoom').dispatchEvent(new Event('change'))}");pg.wait_for_timeout(50)
    measures=pg.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,bar:Array.from(document.querySelectorAll(".appbar button,#uiLanguage,.tabs button")).filter(e=>{let r=e.getBoundingClientRect();return r.left<-.5||r.right>innerWidth+.5||r.width<1}).map(e=>e.id||e.textContent)})')
    check(locale+' controls fit '+str(width),measures['scroll']<=width+1 and not measures['bar'],measures);pg.screenshot(path=str(out/(locale+'-'+str(width)+'.png')));
    if width<540:
     fit=pg.evaluate("(()=>{const frame=document.getElementById('documentFrame').getBoundingClientRect(),wrap=document.getElementById('frameWrap').getBoundingClientRect();return {frame:[frame.left,frame.right],wrap:[wrap.left,wrap.right],inspector:getComputedStyle(document.getElementById('layoutInspector')).display}})()");check(locale+' mobile document fits visible canvas',fit['frame'][0]>=fit['wrap'][0]-.5 and fit['frame'][1]<=fit['wrap'][1]+.5 and fit['inspector']=='none',fit);pg.locator('#inspectorToggle').click();check(locale+' mobile inspector accessible',pg.locator('#inspectorToggle').get_attribute('aria-expanded')=='true' and pg.locator('#applyLayout').is_visible());pg.locator('#inspectorToggle').click()
  check('no remote document or locale requests',not requests,requests);check('no uncaught editor errors',not errors,errors);ctx.close()
  # Restricted file origins and missing language API must retain English and stay usable.
  for label,setup,expected in [
   ('storage denied',"Object.defineProperty(window,'localStorage',{get(){throw new DOMException('Denied','SecurityError')}})",'zh-Hans'),
   ('language API absent',"Object.defineProperty(navigator,'languages',{get(){throw Error('unavailable')}});Object.defineProperty(navigator,'language',{get(){throw Error('unavailable')}})",'en'),
   ('language singular fallback',"Object.defineProperty(navigator,'languages',{value:[],configurable:true});Object.defineProperty(navigator,'language',{value:'es-AR',configurable:true})",'es'),
   ('bad saved locale',"localStorage.setItem('document-studio-ui-language-v101','../../bad')",'zh-Hans')]:
   cx=br.new_context(locale='zh-CN');p=cx.new_page();p.add_init_script(setup);p.goto(EDITOR.as_uri());p.wait_for_function('window.studioReady');check(label+' remains functional',p.evaluate('I18n.locale')==expected and p.evaluate('Studio.preview().then(r=>r.pass)'));cx.close()
  br.close()
 report['pass']=all(c['pass'] for c in report['checks']);(out/'editor-i18n-regression.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8');print(json.dumps({'pass':report['pass'],'checks':len(report['checks']),'failed':[c['name'] for c in report['checks'] if not c['pass']]},ensure_ascii=False));return report
if __name__=='__main__':
 from cli_encoding import configure_utf8
 configure_utf8()
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--browser');a=p.parse_args();raise SystemExit(0 if run(a.output,a.browser)['pass'] else 1)
