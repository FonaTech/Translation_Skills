"""Original merged-table browser/DOCX regression. Copyright 2026 Yufeng Zhan, MIT."""
from pathlib import Path
import argparse,os,json,zipfile
from playwright.sync_api import sync_playwright
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--browser',default=os.environ.get('TRANSLATION_BROWSER'));args=p.parse_args()
BASE=args.output.resolve();BASE.mkdir(parents=True,exist_ok=True)
A=ROOT/'skills/document-translation/assets'
browser=args.browser
report={'version':'1.0.3','checks':[]}
with sync_playwright() as pw:
 br=pw.chromium.launch(headless=True,**({'executable_path':browser} if browser else {}));p=br.new_page(accept_downloads=True)
 p.goto((A/'document-layout-editor.html').resolve().as_uri());p.wait_for_function("()=>typeof Studio!=='undefined'")
 result=p.evaluate('''async()=>{const d={...Studio.defaultDesign(),w:120,h:120,mx:10,my:10,size:10,leading:1.4,cols:1,gap:0,para:0,head:0,accent:'#345',font:'serif'};const s={design:d,title:'Source table'};const source='<p style="height:180px">preceding body</p><table><thead><tr><th rowspan="2">Stub</th><th colspan="2">Group</th></tr><tr><th>A</th><th>B</th></tr></thead><tbody><tr><td rowspan="2">Shared</td><td>A1</td><td>B1</td></tr><tr><td>A2</td><td>B2</td></tr><tr><td>Final</td><td>A3</td><td>B3</td></tr></tbody></table>';await Studio.loadState({title:'Merge fixture',sourceCSS:'',sections:[{...Studio.state.sections[0],...s,html:source,overrides:{},locks:{},sourceClass:'',sourceAttrs:{},sourceStyle:''}]});const r=await Studio.preview(),doc=document.querySelector('#documentFrame').contentDocument;return {report:r,cells:[...doc.querySelectorAll('#edPages td,#edPages th')].map(c=>({text:c.textContent,rs:c.rowSpan,cs:c.colSpan,page:[...doc.querySelectorAll('.ed-page')].indexOf(c.closest('.ed-page'))}))};}''')
 report['checks'].append({'name':'merged table preview retains text and valid geometry','pass':result['report'].get('pass',False),'detail':result})
 cells=result['cells'];owner=next(c for c in cells if c['text']=='Shared');continuation=next(c for c in cells if c['text']=='A2')
 report['checks'].append({'name':'vertical-merge owner and continuation remain on same page','pass':owner['page']==continuation['page'] and owner['rs']==2})
 for text in ['Group','Stub']:
  cell=next(c for c in cells if c['text']==text)
  report['checks'].append({'name':text+' header span retained','pass':cell['cs']==2 if text=='Group' else cell['rs']==2})
 with p.expect_download() as event:p.evaluate("Studio.exportFile('docx')")
 event.value.save_as(BASE/'merged-table.docx')
 with zipfile.ZipFile(BASE/'merged-table.docx') as z:
  doc=ET.fromstring(z.read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};w='{'+ns['w']+'}'
  spans=doc.findall('.//w:gridSpan',ns);merges=doc.findall('.//w:vMerge',ns);text=''.join(doc.itertext())
  report['checks'].append({'name':'DOCX exports horizontal span, merge restart and continuations','pass':any(x.get(w+'val')=='2' for x in spans) and sum(x.get(w+'val')=='restart' for x in merges)==2 and len(merges)==4})
  report['checks'].append({'name':'DOCX owns merged text once','pass':text.count('Shared')==1 and all(x in text for x in ['A1','B1','A2','B2','A3','B3'])})
 p.screenshot(path=str(BASE/'table-editor.png'),full_page=True)
 br.close()
report['pass']=all(c['pass'] for c in report['checks'])
(BASE/'browser-tables.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'pass':report['pass'],'checks':len(report['checks'])},ensure_ascii=False))
raise SystemExit(0 if report['pass'] else 1)
