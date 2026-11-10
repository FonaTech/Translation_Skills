#!/usr/bin/env python3
"""Owned color fixtures through the actual build/render/editor export chain."""
from pathlib import Path
import argparse,base64,contextlib,io,json,os,sys,zipfile
import fitz
from PIL import Image,ImageDraw
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import translate as t,publishing,asset_fidelity as f,vector_assets as v


def run(output,browser=None):
 out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
 project=out/'project'
 if project.exists():raise ValueError('Use a fresh test directory; existing results are preserved.')
 report={'version':'1.0.3','checks':[],'scope':'Original owned color fixtures and actual browser/PDF/editor HTML/DOCX round trips. No semantic certification.'}
 def check(name,value,detail=None):
  report['checks'].append({'name':name,'pass':bool(value),'detail':detail})
  (out/'asset-fidelity-regression.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
  if not value:raise AssertionError(name+': '+str(detail))
 with contextlib.redirect_stdout(io.StringIO()):
  t.init(argparse.Namespace(project=str(project),title='Color fidelity fixtures',languages='en',style='editorial',page_size='A4',columns=1))
 _,meta,content=t.project(project)
 doc=fitz.open()
 cases=[('cmyk','CMYK',(0,0,0,0),None),('rgb-decode','RGB',(255,255,255),'[1 0 1 0 1 0]'),('gray-decode','L',255,'[1 0]'),('soft-mask','RGBA',(255,0,0,120),None),('original-dark','RGB',(14,20,30),None),('pure-vector',None,None,None),('small-binary','L',255,None)]
 for name,mode,color,decode in cases:
  pg=doc.new_page(width=80 if name=='small-binary' else 240,height=80 if name=='small-binary' else 180)
  if mode:
   im=Image.new(mode,(240,240) if name=='small-binary' else (180,100),color)
   if name=='small-binary':
    draw=ImageDraw.Draw(im)
    for row in range(24):
     for col in range(24):
      if (row*13+col*7+row*col)%5<2:draw.rectangle((col*10,row*10,col*10+9,row*10+9),fill=0)
   if mode=='CMYK':ImageDraw.Draw(im).rectangle((25,25,60,70),fill=(255,0,0,0))
   data=io.BytesIO();im.save(data,'JPEG' if mode=='CMYK' else 'PNG')
   x=pg.insert_image(fitz.Rect(4,4,76,76) if name=='small-binary' else fitz.Rect(20,20,220,160),stream=data.getvalue())
   if decode:doc.xref_set_key(x,'Decode',decode)
  if name!='small-binary':
   pg.draw_rect(fitz.Rect(18,18,222,162),color=(.1,.3,.5));pg.draw_line((30,155),(210,25),color=(.9,.1,.2))
  else:pg.draw_rect(fitz.Rect(3,3,77,77),color=(.1,.3,.5))
 source=project/'sources/owned-colors.pdf';doc.save(source);doc.close()
 content['sources']=[{'id':'D001','name':'owned-colors.pdf','file':'sources/owned-colors.pdf','sha256':t.sha(source),'page_count':len(cases),'display_title':'Color fixtures','running_title':'Color fidelity','next_block_index':1}]
 before=t.sha(source)
 with fitz.open(source) as doc:
  for n,(name,*_) in enumerate(cases):
   stem=project/'assets'/name
   result=v.export_crop(doc[n],doc[n].rect,stem)
   t.add_block(content,'D001','image',{'page':n+1,'bbox':list(doc[n].rect)},[],asset=result['vector'].relative_to(project).as_posix(),asset_sha256=t.sha(result['vector']),asset_fallback=result['fallback'].relative_to(project).as_posix(),asset_fallback_sha256=t.sha(result['fallback']),vector=result['metadata'],width_mm=20 if name=='small-binary' else 135,label_policy='no-text')
   check(name+' preserves vector paths',result['metadata']['svg_paths']>0)
 # Corrupt a color-safe PNG fallback and a retained-original asset independently.
 Image.new('RGB',(600,450),'black').save(project/'assets/cmyk.png')
 content['blocks'][0]['asset_fallback_sha256']=t.sha(project/'assets/cmyk.png')
 bad=project/'assets/wrong.png';Image.new('RGB',(600,450),'black').save(bad)
 t.add_block(content,'D001','image',{'page':1,'bbox':[0,0,240,180]},[],asset='assets/wrong.png',asset_sha256=t.sha(bad),width_mm=135,label_policy='no-text')
 t.write(project/'content.json',content)
 result=f.verify_project(project,browser)
 check('all retained-original assets checked',result['verified_source_crops']==len(cases)+1,result['verified_source_crops'])
 check('bad main asset replaced from source',result['asset_repairs']==1)
 check('bad compatibility fallback repaired',any(x.get('fallback_repaired') for x in result['assets']))
 check('all final metrics pass',all(x['final_metrics']['pass'] for x in result['assets']))
 check('source file unchanged',t.sha(source)==before)
 again=f.verify_project(project,browser)
 check('gate is idempotent',not again['content_changed'])
 _,meta,content=t.project(project)
 check('fresh release evidence accepted',not f.release_errors(project,meta,content))
 content['blocks'][0]['source']['bbox'][0]=1
 check('changed crop invalidates release',any(x['code']=='asset-fidelity-source-stale' for x in f.release_errors(project,meta,content)))
 _,meta,content=t.project(project)
 publishing.build(project,browser);publishing.render(project,browser)
 layout=t.read(project/'reports/layout.json')
 check('all three real PDF editions render',layout['pass'] and len(layout['outputs'])==3)
 check('no empty PDF pages',all(not x['empty_pdf_pages'] for x in layout['outputs']))
 check('small graphics have bounded recorded alignment',all(any(x['block']==content['blocks'][len(cases)-1]['id'] and max(abs(a-b) for a,b in zip(x['from'],x['to']))<=.51 for x in out['layout'].get('smallGraphicAlignment',[])) for out in layout['outputs']))
 check('print comparison uses physical page grid',all(t.read(project/'reports'/('figure-pdf-'+out['file'].removesuffix('.html')+'.json')).get('comparison_method')==f.PDF_COMPARISON_VERSION for out in layout['outputs']))
 with sync_playwright() as pw:
  br=pw.chromium.launch(headless=True,**({'executable_path':browser} if browser else {}))
  proof=br.new_page(viewport={'width':1280,'height':1400})
  proof.goto((project/'outputs/en-faithful.html').as_uri());proof.wait_for_function('window.translationReady')
  proof.add_style_tag(content='@media print{figure img{position:relative;top:3px}}')
  proof.pdf(path=str(out/'print-coordinate-fixture.pdf'),prefer_css_page_size=True,print_background=True)
  print_check=f.verify_rendered_figures(project,proof,out/'print-coordinate-fixture.pdf','print-coordinate-fixture')
  check('print geometry measured instead of screen geometry',print_check['pass'],print_check)
  proof.add_style_tag(content='@media print{figure img{filter:invert(1)!important}}')
  proof.pdf(path=str(out/'intentional-print-defect.pdf'),prefer_css_page_size=True,print_background=True)
  defect=f.verify_rendered_figures(project,proof,out/'intentional-print-defect.pdf','intentional-print-defect')
  check('actual PDF color corruption blocked',not defect['pass'])
  proof.close()
  pg=br.new_page(accept_downloads=True,viewport={'width':1540,'height':1050})
  pg.goto((ROOT/'skills/document-translation/assets/document-layout-editor.html').as_uri());pg.wait_for_function('window.studioReady')
  # Raw four-component JPEG, including MIME spoofing, must not pass the editor.
  raw=io.BytesIO();Image.new('CMYK',(30,20),(0,0,0,0)).save(raw,'JPEG')
  jpeg='data:image/jpeg;base64,'+base64.b64encode(raw.getvalue()).decode()
  unsafe='<svg xmlns="http://www.w3.org/2000/svg" width="30" height="20"><image href="'+jpeg+'" width="30" height="20"/></svg>'
  uri='data:image/svg+xml;base64,'+base64.b64encode(unsafe.encode()).decode()
  check('editor rejects CMYK JPEG',not pg.evaluate('(s)=>VectorImages.valid(s)',jpeg))
  check('editor rejects mislabeled CMYK JPEG',not pg.evaluate('(s)=>VectorImages.valid(s)',jpeg.replace('image/jpeg','image/png')))
  check('editor rejects embedded CMYK SVG',not pg.evaluate('(s)=>VectorImages.valid(s)',uri))
  fallback='data:image/png;base64,'+base64.b64encode((project/'assets/cmyk.png').read_bytes()).decode()
  sanitized=pg.evaluate('s=>Studio.sanitize(s).body.innerHTML','<img src="'+uri+'" data-raster-fallback="'+fallback+'">')
  check('legacy unsafe SVG uses PNG', 'unsafe-vector-replaced-with-png' in sanitized and 'src="data:image/png;' in sanitized)
  awaitless=pg.evaluate('(html)=>Studio.importHTML(html,"Owned color regression")',(project/'outputs/en-faithful.html').read_text( encoding='utf-8'))
  preview=pg.evaluate('Studio.preview()');check('editor source import preview passes',preview['pass'],preview)
  check('all source figure assets survive editor',sum(x['images'] for x in preview['pages'])==len(cases)+1)
  for kind in ['html','docx']:
   with pg.expect_download() as download:pg.evaluate('(kind)=>Studio.exportFile(kind)',kind)
   download.value.save_as(out/('editor-color-export.'+kind))
  with zipfile.ZipFile(out/'editor-color-export.docx') as z:
   check('DOCX CRC',z.testzip() is None)
   vectors=[x for x in z.namelist() if x.startswith('word/media/') and x.endswith('.svg')]
   check('DOCX retains all source SVGs',len(vectors)==len(cases),len(vectors))
   check('DOCX SVG embedded rasters safe',all(all(r['components'] in (1,3) for r in v.embedded_raster_colors(z.read(x))) for x in vectors))
  pg.evaluate('(html)=>Studio.importHTML(html,"HTML round trip")',(out/'editor-color-export.html').read_text( encoding='utf-8'))
  check('exported HTML reimports',pg.evaluate('Studio.preview().then(r=>r.pass)'))
  data=base64.b64encode((out/'editor-color-export.docx').read_bytes()).decode()
  imported=pg.evaluate('async s=>Formats.importDocx(Uint8Array.from(atob(s),c=>c.charCodeAt(0)).buffer)',data)
  check('DOCX reimports all figures',imported['html'].count('<img ')==len(cases)+1)
  pg.evaluate('window.print=()=>{window.printCalled=true}')
  pg.evaluate('Studio.exportFile("pdf")');pg.wait_for_function('window.printCalled')
  pg.pdf(path=str(out/'editor-color-print.pdf'),prefer_css_page_size=True,print_background=True)
  with fitz.open(out/'editor-color-print.pdf') as pdf:
   check('editor printed PDF has no empty pages',all(not publishing.page_is_visually_empty(p) for p in pdf))
  editor_figures=f.verify_rendered_figures(project,pg,out/'editor-color-print.pdf','editor-color-print','#printHost>.ed-page')
  check('editor actual PDF figures match source',editor_figures['pass'],editor_figures)
  pg.screenshot(path=str(out/'editor-color-preview.png'));br.close()
 report['pass']=all(x['pass'] for x in report['checks'])
 (out/'asset-fidelity-regression.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
 print(json.dumps({'pass':report['pass'],'checks':len(report['checks'])}))
 return report

if __name__=='__main__':
 from cli_encoding import configure_utf8
 configure_utf8()
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--browser',default=os.environ.get('TRANSLATION_BROWSER'));a=p.parse_args()
 raise SystemExit(0 if run(a.output,a.browser)['pass'] else 1)
