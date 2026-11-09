#!/usr/bin/env python3
"""Exercise pixel snapping and joined source-page locators in actual Chromium."""
import argparse,json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
ASSETS=ROOT/'skills/document-translation/assets'

def run(output,browser=None):
 out=Path(output).resolve()
 if out.exists():raise ValueError('Use a fresh evidence directory.')
 if out.is_relative_to(ROOT):raise ValueError('Keep generated evidence outside the public repository.')
 out.mkdir(parents=True)
 result={'version':'1.0.2','scope':'Measured browser boundary and provenance fixtures; no semantic or aesthetic attestation.','checks':[]}
 def check(name,passed,detail=None):
  result['checks'].append({'name':name,'pass':bool(passed),'detail':detail})
  (out/'layout-runtime-regression.json').write_text(json.dumps(result,indent=2)+'\n')
  if not passed:raise AssertionError(name+': '+str(detail))
 with sync_playwright() as pw:
  br=pw.chromium.launch(headless=True,**({'executable_path':browser} if browser else {}));page=br.new_page()
  page.set_content('<html><head></head><body></body></html>')
  page.add_script_tag(content='const FAMILY_CSS="";const CONTENT_CSS="";const CATALOG=[];'+(ASSETS/'layout-runtime.js').read_text())
  for kind in ['normal','bottom','caption','joined','oversized-joined']:
   measured=page.evaluate(r'''async kind=>{
    document.querySelectorAll('style,#fixture,#edPages').forEach(x=>x.remove());
    const d={w:100,h:99.85,mx:10,my:10,size:10,leading:1.4,cols:1,gap:0,para:0,head:0,accent:'#304659',font:'serif'};
    const s={design:d,title:'fixture',sourceClass:'fixture'};
    const st=document.createElement('style');st.textContent=Layout.styles([s],'.fixture figure{margin:0;line-height:0}.fixture img{display:block;width:20.6px;height:20.6px}.fixture figcaption{height:12px;margin:0;line-height:12px;font-size:10px}.fixture .pair-grid{display:grid;grid-template-columns:repeat(3,1fr)}');document.head.append(st);
    const root=document.createElement('div');root.id='fixture';const section=document.createElement('section');section.className='ed-doc ed-section-0 fixture';root.append(section);document.body.append(root);
    const joined=kind.includes('joined');
    if(joined){
     const long=kind==='oversized-joined',text=long?'Visible clause. '.repeat(230):'A visible continuation.';
     section.innerHTML='<article class="pair" data-block="joined" data-source-page="1" data-source-pages="1,2"><div class="locator">D001 · p1,2</div><div class="pair-grid"><section><p>'+text+'</p></section><section><p>译文。</p></section><section><p>译写。</p></section></div></article>';
    }else{
     const uri='data:image/svg+xml;base64,'+btoa('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20" fill="#34495e"/></svg>');
     const offset=kind==='bottom'?(d.h-2*d.my-14)*96/25.4-20.6-.02:20.6;
     section.innerHTML='<p style="margin:0;height:'+offset+'px">spacer</p><figure data-block="small" data-span="column"><img style="outline:0px" src="'+uri+'">'+(kind==='caption'?'<figcaption>caption</figcaption>':'')+'</figure>';
    }
    const before=JSON.stringify(s),sourceText=root.textContent.replace(/\s+/g,''),{report,stage}=await Layout.paginate(document,[s],root);
    const img=stage.querySelector('img'),r=img?.getBoundingClientRect(),body=img?.closest('.ed-page-body').getBoundingClientRect(),caption=img?.closest('figure').querySelector('figcaption')?.getBoundingClientRect();
    return {report,parametersUnchanged:before===JSON.stringify(s),style:img?.getAttribute('style'),inside:!img||r.top>=body.top-.01&&r.bottom<=body.bottom+.01,captionGap:caption?caption.top-r.bottom:null,sourceText,headers:[...stage.querySelectorAll('.source-pages')].map(x=>x.textContent)};
   }''',kind)
   report=measured['report'];check(kind+' text and geometry',report['pass'] and report['textPreserved'] and measured['inside'],report)
   check(kind+' editable parameters unchanged',measured['parametersUnchanged'])
   if kind=='normal':check('safe pixel snap remains enabled',len(report['smallGraphicAlignment'])==1)
   if kind in {'bottom','caption'}:
    check(kind+' outward snap restored original style',not report['smallGraphicAlignment'] and measured['style']=='outline:0px',measured)
    if kind=='caption':check('adjacent caption is not overlapped',measured['captionGap']>=-.01,measured['captionGap'])
   if 'joined' in kind:
    check(kind+' all contributing pages survive pagination',all(set(p['source_pages'])=={'1','2'} for p in report['pages']),measured['headers'])
    if kind=='oversized-joined':check('oversized continuation actually exercised',len(report['pages'])>1 and bool(report['warnings']),report['warnings'])
   page.screenshot(path=str(out/(kind+'.png')),full_page=True)
  for kind in ['keep-page','keep-column','keep-disabled','keep-long','keep-break']:
   measured=page.evaluate(r'''async kind=>{
    document.querySelectorAll('style,#fixture,#edPages').forEach(x=>x.remove());
    const d={w:140,h:110,mx:10,my:10,size:10,leading:1.4,cols:kind==='keep-column'?2:1,gap:5,para:0,head:0,accent:'#304659',font:'serif'},s={design:d,title:'keep fixture',sourceClass:'fixture'};
    const st=document.createElement('style');st.textContent=Layout.styles([s],'.fixture figure{margin:0}.fixture .equation{height:60px;background:#eee}.fixture p{margin:0}');document.head.append(st);
    const root=document.createElement('div');root.id='fixture';const section=document.createElement('section');section.className='ed-doc ed-section-0 fixture';root.append(section);document.body.append(root);
    const capacity=(d.h-2*d.my-14)*96/25.4,long=kind==='keep-long';
    section.innerHTML='<p data-block="spacer" style="height:'+(long?50:capacity-30)+'px">preceding</p><p data-block="connector" data-keep-next="'+(kind!=='keep-disabled')+'">'+(long?'Visible clause. '.repeat(150):'and')+'</p>'+(kind==='keep-break'?'<hr class="ed-break">':'')+'<figure class="equation" data-span="column" data-block="equation">equation</figure>';
    const parameters=JSON.stringify(s),{report,stage}=await Layout.paginate(document,[s],root);
    const position=key=>[...stage.querySelectorAll('[data-block="'+key+'"]')].map(e=>{const r=e.getBoundingClientRect();return {page:[...stage.children].indexOf(e.closest('.ed-page')),left:Math.round(r.left),top:r.top,bottom:r.bottom}});
    return {report,parametersUnchanged:JSON.stringify(s)===parameters,connector:position('connector'),equation:position('equation')};
   }''',kind)
   check(kind+' full text and geometry preserved',measured['report']['pass'] and measured['parametersUnchanged'],measured)
   a=measured['connector'][-1];b=measured['equation'][0]
   together=a['page']==b['page'] and abs(a['left']-b['left'])<2
   if kind in {'keep-page','keep-column'}:check(kind+' connector shares actual column with equation',together and bool(measured['report'].get('keepNextMoves')),measured)
   if kind in {'keep-disabled','keep-break'}:check(kind+' explicit nonkeep or manual break respected',not together,measured)
   if kind=='keep-long':check('long kept paragraph stays splittable',len(measured['connector'])>1 and not measured['report'].get('keepNextMoves'),measured)
   page.screenshot(path=str(out/(kind+'.png')),full_page=True)
  for kind in ['alignment-keep','alignment-columns','alignment-disabled','alignment-break','alignment-long','alignment-oversized-next']:
   measured=page.evaluate(r'''async kind=>{
    document.querySelectorAll('style,#fixture,#edPages').forEach(x=>x.remove());
    const d={w:140,h:110,mx:10,my:10,size:10,leading:1.4,cols:kind==='alignment-columns'?2:1,gap:5,para:0,head:0,accent:'#304659',font:'serif'},s={design:d,title:'alignment keep',sourceClass:'fixture',alignmentLabels:['Original','Faithful','Interpretive']};
    const st=document.createElement('style');st.textContent=Layout.styles([s],'.fixture figure{margin:0}.fixture .equation{height:60px;background:#eee}.fixture p{margin:0}.fixture .pair-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))}.fixture .locator{font:8px/1.2 serif}');document.head.append(st);
    const root=document.createElement('div');root.id='fixture';const section=document.createElement('section');section.className='ed-doc ed-section-0 fixture';root.append(section);document.body.append(root);
    const capacity=(d.h-2*d.my-20)*96/25.4,long=kind==='alignment-long';
    const row='<article class="pair" data-block="connector" data-keep-next="'+(kind!=='alignment-disabled')+'"><div class="locator pair-start">U1 · p1</div><div class="pair-grid">'+['and','以及','以及'].map((v,i)=>'<section><p class="paragraph" data-uid="u'+i+'">'+(long?'Visible clause. '.repeat(160):v)+'</p></section>').join('')+'</div></article>';
    section.innerHTML='<p data-span="all" style="height:'+(long?40:capacity-42)+'px">preceding</p>'+row+(kind==='alignment-break'?'<hr class="ed-break">':'')+'<figure class="equation" data-span="column" data-block="equation"'+(kind==='alignment-oversized-next'?' style="height:'+(capacity-8)+'px"':'')+'>equation</figure>';
    const parameters=JSON.stringify(s),{report,stage}=await Layout.paginate(document,[s],root);
    const position=key=>[...stage.querySelectorAll('[data-block="'+key+'"]')].map(e=>({page:[...stage.children].indexOf(e.closest('.ed-page')),width:e.getBoundingClientRect().width,top:e.getBoundingClientRect().top}));
    return {report,parametersUnchanged:JSON.stringify(s)===parameters,connector:position('connector'),equation:position('equation'),bodyWidth:stage.querySelector('.ed-page-body').getBoundingClientRect().width};
   }''',kind)
   check(kind+' text and geometry retained',measured['report']['pass'] and measured['parametersUnchanged'],measured)
   a=measured['connector'][-1];b=measured['equation'][0];together=a['page']==b['page']
   if kind in {'alignment-keep','alignment-columns'}:
    check(kind+' short alignment row stays with following graphic',together and bool(measured['report'].get('keepNextMoves')),measured)
    check(kind+' alignment remains full width',abs(a['width']-measured['bodyWidth'])<1,measured)
   if kind=='alignment-columns':check('alignment keep measures actual following column',b['width']<measured['bodyWidth']*.6,measured)
   if kind in {'alignment-disabled','alignment-break'}:check(kind+' explicit split is respected',not together and not measured['report'].get('keepNextMoves'),measured)
   if kind=='alignment-long':check('long alignment row remains splittable',len(measured['connector'])>1 and not measured['report'].get('keepNextMoves'),measured)
   if kind=='alignment-oversized-next':check('oversized pair does not force an empty page',not together and not measured['report'].get('keepNextMoves') and all(p['chars'] or p['images'] for p in measured['report']['pages']),measured)
   page.screenshot(path=str(out/(kind+'.png')),full_page=True)
  # A print host receives serialized HTML. Test its actual line fragments.
  measured=page.evaluate(r'''async ()=>{
   document.querySelectorAll('style,#fixture,#edPages').forEach(x=>x.remove());
   const d={w:210,h:276,mx:10.5,my:14,size:9.75,leading:1.41,cols:2,gap:6.2,para:1.7,head:2.5,accent:'#231f20',font:'serif'},s={design:d,title:'serialized footer',sourceClass:'fixture'};
   const css=Layout.styles([s],'.fixture .metadata{font-size:.78em;line-height:1.45}');
   const st=document.createElement('style');st.textContent=css;document.head.append(st);
   const root=document.createElement('div');root.id='fixture';root.innerHTML='<section class="ed-doc ed-section-0 fixture"><p class="metadata">Copyright 2025</p><p class="metadata">'+('下载机构及使用条款 https://example.org/terms-and-conditions; '.repeat(9))+'</p></section>';document.body.append(root);
   const {report,stage}=await Layout.paginate(document,[s],root);
   const geometry=parent=>[...parent.querySelectorAll('.ed-band>*')].map(e=>[...e.getClientRects()].map(r=>{const p=e.closest('.ed-page').getBoundingClientRect();return [r.left-p.left,r.top-p.top,r.width,r.height]}));
   const before=geometry(stage),copy=document.createElement('iframe');document.body.append(copy);
   await new Promise(resolve=>{copy.onload=resolve;copy.srcdoc='<html><head><style>'+css+'</style></head><body>'+stage.outerHTML+'</body></html>';});
   await copy.contentDocument.fonts.ready;const after=geometry(copy.contentDocument),bands=[...stage.querySelectorAll('.ed-band')].filter(b=>b.style.columnCount);
   const out={pass:report.pass,integerHeights:bands.length>0&&bands.every(b=>Number.isInteger(parseFloat(b.style.height))),equal:JSON.stringify(before)===JSON.stringify(after),before,after};copy.remove();return out;
  }''')
  check('serialized balanced bands retain exact fragment geometry',measured['pass'] and measured['integerHeights'] and measured['equal'],measured)
  br.close()
 result['pass']=all(c['pass'] for c in result['checks']);(out/'layout-runtime-regression.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'pass':result['pass'],'checks':len(result['checks'])}));return result

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--browser',default=os.environ.get('TRANSLATION_BROWSER'));a=p.parse_args();raise SystemExit(0 if run(a.output,a.browser)['pass'] else 1)
