"""Escaped self-contained HTML, alignment and measured Chromium PDF output."""
from pathlib import Path
import base64,csv,html,json,os
from alignment import rows as aligned_rows
from translate import project,units,audit_data,write,snap,sha,safe
A=Path(__file__).resolve().parent.parent/'assets'
LABELS={
'en':{'faithful':'Faithful complete edition','interpretive':'Interpretive edition','alignment':'Source alignment','original':'Original','print':'Print / Save PDF','source':'Source','note':'Editorial note'},
'zh':{'faithful':'忠实全译版','interpretive':'理解性译写版','alignment':'逐句／句群对照册','original':'原文','print':'打印／保存 PDF','source':'来源','note':'译校说明'},
'ja':{'faithful':'忠実な全訳版','interpretive':'理解を助ける訳文版','alignment':'原文対照','original':'原文','print':'印刷 / PDF','source':'出典','note':'訳注'},
'ar':{'faithful':'الترجمة الكاملة الأمينة','interpretive':'الصياغة التفسيرية','alignment':'مقابلة النص الأصلي','original':'الأصل','print':'طباعة / PDF','source':'المصدر','note':'ملاحظة تحريرية'},
'es':{'faithful':'Traducción íntegra fiel','interpretive':'Versión interpretativa','alignment':'Cotejo con el original','original':'Original','print':'Imprimir / PDF','source':'Fuente','note':'Nota editorial'},
'fr':{'faithful':'Traduction intégrale fidèle','interpretive':'Version interprétative','alignment':'Alignement avec la source','original':'Original','print':'Imprimer / PDF','source':'Source','note':'Note éditoriale'} }
def h(x):return html.escape(str(x),quote=True)
def value(u,l,e):return u['translations'][l][e]
def uspan(u,l,e):return '<span class="trans-unit" data-uid="'+h(u['id'])+'">'+h(value(u,l,e))+'</span>'
def page_is_visually_empty(page):
 import fitz
 pix=page.get_pixmap(matrix=fitz.Matrix(.35,.35),colorspace=fitz.csGRAY,alpha=False)
 return not any(sample<255 for sample in pix.samples)
def loc(b):
 s=b['source'];return s['document_id']+(' · p'+str(s['page']) if s.get('page') else ' · '+str(s.get('element','')))
def block_attrs(b):
 p=b.get('presentation',{});role=p.get('role','body');span=p.get('span','auto')
 if role not in {'body','metadata','abstract','keywords','caption','equation','note'}:role='body'
 if span not in {'auto','all','column'}:span='auto'
 return ' data-keep-next="'+str(p.get('keep_next',False)).lower()+'" data-block="'+h(b['id'])+'" data-source-page="'+h(b['source'].get('page',''))+'" data-span="'+span+'" class="paragraph block-'+role+'"'
def block_html(r,b,l,e,labels):
 typ=b['type'];txt=' '.join(uspan(u,l,e) for u in b.get('units',[]));locator='<div class="locator">'+h(loc(b))+' · '+h(b['id'])+'</div>';attrs=block_attrs(b)
 if typ=='heading':
  lev=max(2,min(6,b.get('level',2)+1));return '<h'+str(lev)+attrs.replace('paragraph ','')+'>'+txt+'</h'+str(lev)+'>'
 if typ=='table':
  lookup={u['id']:u for u in b['units']};n=b.get('header_rows',1);rows=[]
  for i,row in enumerate(b['rows']):
   tag='th' if i<n else 'td';rows.append('<tr>'+''.join(f'<{tag}>'+uspan(lookup[uid],l,e)+f'</{tag}>' for uid in row)+'</tr>')
  caps=''.join('<caption data-block="'+h(cb['id'])+'" data-source-page="'+h(cb['source'].get('page',''))+'">'+' '.join(uspan(u,l,e) for u in cb.get('units',[]))+'</caption>' for cb in b.get('_captions',[]))
  return '<div'+attrs.replace('paragraph','table-wrap',1)+'><table>'+caps+'<thead>'+''.join(rows[:n])+'</thead><tbody>'+''.join(rows[n:])+'</tbody></table></div>'
 if typ in {'image','equation'}:
  p=safe(r,b['asset']);ext=p.suffix.lower().lstrip('.');mime='image/jpeg' if ext in {'jpg','jpeg'} else 'image/'+ext
  src='data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode();label=b.get('label_policy','unreviewed')
  caption=''.join('<p'+block_attrs(cb)+'>'+' '.join(uspan(u,l,e) for u in cb.get('units',[]))+'</p>'+''.join('<div class="editor-note">'+h(n.get('note',''))+'</div>' for u in cb.get('units',[]) for n in u.get('notes',[]) if n.get('language',l)==l) for cb in b.get('_captions',[]))
  return '<figure'+attrs.replace('paragraph','figure-block',1)+'><img src="'+src+'" alt="'+h(' '.join(value(u,l,e) for u in b.get('units',[])) or b['id'])+'" style="width:'+str(b.get('width_mm',150))+'mm"><figcaption>'+caption+('<div class="label-map">'+txt+'</div>' if txt else '')+'</figcaption>'+locator+('<div class="asset-note">'+h(b.get('label_note',label))+'</div>' if label not in {'no-text','translated'} else '')+'</figure>'
 return '<p'+attrs+'>'+txt+'</p>'
def make_document(m,c,l,e,body,layout_plan):
 from layout_engine import design_css
 lab=LABELS.get(l.split('-')[0],LABELS['en']);direction=m.get('direction',{}).get(l,'ltr');css=(A/'layout.css').read_text()+'\n'+(A/'layout-flow.css').read_text()+'\n'+(A/'families.css').read_text()+'\n'+design_css(layout_plan);js='const FAMILY_CSS="";const CATALOG=[];'+(A/'layout-runtime.js').read_text()+'\n'+(A/'paginate.js').read_text();title=m['title']+' · '+lab.get(e,e)
 sections=[]
 for ds in layout_plan['documents']:
  x=ds['design'];source=next(z for z in c['sources'] if z['id']==ds['document_id'])
  sections.append({'title':source.get('display_title',source['name']),'header':source.get('running_title',source.get('display_title',m['title'])),'footer':m.get('author_credit',''),'dir':direction,'familyClass':'family-'+x['family'],'design':{'w':x['page_mm'][0],'h':x['page_mm'][1],'mx':x['margin_x_mm'],'my':x['margin_y_mm'],'cols':1 if e=='alignment' else x['columns'],'gap':x.get('column_gap_mm',7),'size':x['body_pt'],'leading':x['line_height'],'para':x.get('paragraph_gap_mm',1.8),'head':x.get('heading_gap_mm',3),'accent':x['accent'],'tableSize':x.get('table_pt',8),'cellPad':x.get('cell_padding_mm',1),'titleSize':x.get('title_pt',20),'captionSize':x.get('caption_pt',8),'font':x.get('font','serif')}})
 js='window.layoutSections='+json.dumps(sections,ensure_ascii=False).replace('<','\\u003c')+';'+js+'\n'+'''window.openTranslationEditor=()=>{let popup;const listener=event=>{if(event.source!==popup)return;if(event.data?.type==='document-translation-editor-ready'){popup.postMessage({type:'document-translation-open-html',title:document.title,html:'<!doctype html>'+document.documentElement.outerHTML},'*');return;}if(event.data?.type==='document-translation-editor-loaded'||event.data?.type==='document-translation-editor-error')window.removeEventListener('message',listener);};window.addEventListener('message',listener);popup=window.open('document-layout-editor.html','documentTranslationLayoutEditor');if(!popup){window.removeEventListener('message',listener);alert('Please allow this local editor window to open.');}};'''
 return '<!doctype html><html lang="'+h(l)+'" dir="'+h(direction)+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\';script-src \'unsafe-inline\';style-src \'unsafe-inline\';img-src data: blob:;font-src data:;connect-src \'none\';base-uri \'none\'"><meta name="creator" content="Document Translation Skill"><title>'+h(title)+'</title><style>'+css+'</style></head><body data-edition="'+h(lab.get(e,e))+'" data-footer="'+h(m.get('author_credit',''))+'" data-kind="'+e+'"><nav class="toolbar"><span>'+h(title)+'</span><button onclick="document.body.classList.toggle(&quot;reading-flow&quot;)">阅读 / 页面</button><button onclick="window.openTranslationEditor()">在布局编辑器中打开</button><button onclick="window.print()">'+h(lab['print'])+'</button></nav><main class="reader">'+body+'</main><main class="print-stage" aria-hidden="true"></main><script>'+js+'</script></body></html>'

def wrap_document(source,design,body,l,e,lab,has_title=False):
 d=design['design'];ident=source['id'];scope=source.get('selection_scope','all');scope=json.dumps(scope,ensure_ascii=False) if isinstance(scope,dict) else str(scope)
 scope_text=('选取源页：' if l.startswith('zh') else 'Selected source pages: ')+', '.join(map(str,source['selection_scope']['pages'])) if isinstance(source.get('selection_scope'),dict) and 'pages' in source['selection_scope'] else ''
 mast='<header class="mast"><div class="edition">'+h(lab.get(e,e))+' · '+h(l)+'</div>'+('' if has_title else '<h1>'+h(source.get('display_title',source['name']))+'</h1>')+'</header>'
 if scope_text or source.get('scope_note'):mast+='<div class="scope-list">'+h(scope_text)+' '+h(source.get('scope_note',''))+'</div>'
 # The document boundary carries its own measured page design. No synthetic headings or labels are inferred.
 return '<section class="layout-document family-'+h(d['family'])+'" data-layout-doc="'+h(ident)+'" data-columns="'+str(d['columns'] if e!='alignment' else 1)+'" data-family="'+h(d['family'])+'" data-route="'+h(design['route'])+'" data-template="'+h(d['id'])+'">'+mast+body+'</section>'

def build(path):
 from layout_engine import plan
 r,m,c=project(path);au=audit_data(r,m,c)
 if au['errors']:write(r/'reports/audit.json',au);raise ValueError('Build blocked: incomplete/invalid content; inspect reports/audit.json')
 layout_plan=plan(r,m,c);write(r/'reports/layout-plan.json',layout_plan);designs={d['document_id']:d for d in layout_plan['documents']}
 for l in m['target_languages']:
  lab=LABELS.get(l.split('-')[0],LABELS['en'])
  for e in m['editions']+['alignment']:
   sections=[]
   for source in c['sources']:
    body=[]
    byid={b['id']:b for b in c['blocks']}
    bound={cid for b in c['blocks'] if b['source']['document_id']==source['id'] for cid in b.get('caption_block_ids',[])}
    for b in c['blocks']:
     if b['source']['document_id']!=source['id']:continue
     if e!='alignment' and b['id'] in bound:continue
     if e!='alignment' and b.get('caption_block_ids'):b={**b,'_captions':[byid[cid] for cid in b['caption_block_ids']]}
     if e=='alignment' and b['type']=='table':
      cells={u['id']:u for u in b['units']};lines=[]
      for ri,row in enumerate(b['rows'],1):
       for ci,uid in enumerate(row,1):
        for u in aligned_rows(cells[uid],l):
         ident=h(u['id']);lines.append('<tr><td title="'+ident+'">'+str(ri)+':'+str(ci)+'</td><td><span data-uid="'+ident+':source">'+h(u['source'])+'</span></td>'+''.join('<td><span data-uid="'+ident+':'+ed+'">'+h(value(u,l,ed))+'</span></td>' for ed in m['editions'])+'</tr>')
      body.append('<p class="locator">'+h(loc(b)+' · '+b['id'])+'</p><div class="table-wrap alignment-cells"><table><colgroup><col style="width:12%"><col style="width:29%"><col style="width:29%"><col style="width:30%"></colgroup><thead><tr><th>行:列 / R:C</th><th>'+h(lab['original'])+'</th>'+''.join('<th>'+h(lab[ed])+'</th>' for ed in m['editions'])+'</tr></thead><tbody>'+''.join(lines)+'</tbody></table></div>')
     elif e=='alignment':
      # Alignment archives must preserve the figures too, including vector crops.
      if b['type'] in {'image','equation'}:body.append(block_html(r,{**b,'units':[]},l,'faithful',lab))
      for parent in b.get('units',[]):
       for u in aligned_rows(parent,l):
        uid=h(u['id']);body.append('<article class="pair"><div class="locator pair-start">'+h(u['id']+' · '+loc(b))+'</div><h6 class="pair-label">'+h(lab['original'])+'</h6><p class="paragraph original" dir="auto"><span data-uid="'+uid+':source">'+h(u['source'])+'</span></p>'+''.join('<h6 class="pair-label">'+h(lab[ed])+'</h6><p class="paragraph target"><span data-uid="'+uid+':'+ed+'">'+h(value(u,l,ed))+'</span></p>' for ed in m['editions'])+'</article>')
     else:
      body.append(block_html(r,b,l,e,lab));body+=['<p class="editor-note">'+h(lab['note']+': '+n.get('note',''))+'</p>' for u in b.get('units',[]) for n in u.get('notes',[]) if n.get('language',l)==l]
    has_title=e!='alignment' and any(b['source']['document_id']==source['id'] and b['type']=='heading' and b.get('level',2)==1 for b in c['blocks'])
    sections.append(wrap_document(source,designs[source['id']],''.join(body),l,e,lab,has_title))
   (r/'outputs'/f'{l}-{e}.html').write_text(make_document(m,c,l,e,''.join(sections),layout_plan),encoding='utf-8')
  with (r/'outputs'/f'{l}-alignment.csv').open('w',newline='',encoding='utf-8-sig') as f:
   cw=csv.writer(f);cw.writerow(['unit_id','document_id','page_or_element','source','faithful','interpretive','review_notes'])
   for b,parent in units(c):
    for u in aligned_rows(parent,l):cw.writerow([u['id'],b['source']['document_id'],b['source'].get('page',b['source'].get('element','')),u['source'],value(u,l,'faithful'),value(u,l,'interpretive'),json.dumps(u.get('notes',[]),ensure_ascii=False)])
 shutil=__import__('shutil');editor=A/'document-layout-editor.html';shutil.copy2(editor,r/'outputs/document-layout-editor.html');write(r/'reports/editor.json',{'version':'1.0.1','file':'document-layout-editor.html','sha256':sha(editor),'runtime_dependencies':[]})
 write(r/'reports/build.json',{'snapshot':snap(m,c),'layout_plan_sha256':sha(r/'reports/layout-plan.json'),'html':[p.name for p in (r/'outputs').glob('*.html') if p.name!='document-layout-editor.html'],'translation_supplied_by':'invoking agent/user','meaning_verified':False});print('Built per-document source-adapted HTML and CSV alignment.')

def render(path,browser=None,refine=False):
 from playwright.sync_api import sync_playwright
 from layout_engine import freshness
 import fitz,shutil
 r,m,c=project(path);snapshot=snap(m,c);ok,why=freshness(r,m,c)
 if not ok:raise ValueError('Build first: '+why)
 lp=__import__('translate').read(r/'reports/layout-plan.json');results=[];exe=browser or os.environ.get('TRANSLATION_BROWSER');attempts=[]
 with sync_playwright() as p:
  br=p.chromium.launch(headless=True,**({'executable_path':exe} if exe else {}))
  for file in [r/'outputs'/f'{lang}-{ed}.html' for lang in m['target_languages'] for ed in m['editions']+['alignment']]:
   chosen=None
   for round in range(3):
    page=br.new_page(viewport={'width':1280,'height':1400});page_errors=[];page.on('pageerror',lambda e:page_errors.append(str(e)));page.goto(file.as_uri(),wait_until='load',timeout=90000)
    page.wait_for_function('window.translationReady || window.translationError',timeout=90000)
    if round:
     page.evaluate('(r)=>{window.translationReady=false;window.translationError=null;window.layoutAdjustmentRound=r;}',round)
     page.evaluate('paginate().catch(e=>{window.translationError=String(e);window.translationLayout={pass:false,error:String(e)};})')
    page.wait_for_function('window.translationReady || window.translationError',timeout=90000);err=page.evaluate('window.translationError');layout=page.evaluate('window.translationLayout') or {'pass':False,'error':err};pdf=r/'reports/candidates'/f'{file.stem}-adjust-{round}.pdf';pdf.parent.mkdir(exist_ok=True)
    page.pdf(path=str(pdf),print_background=True,prefer_css_page_size=True);doc=fitz.open(pdf);removed_blank_pages=[]
    # Chromium can append a default Letter page after named-size CSS pages.
    # Remove only provably empty trailing pages; interior blanks remain failures.
    while len(doc)>1:
     last=doc[-1]
     if last.get_links() or not page_is_visually_empty(last):break
     removed_blank_pages.append(len(doc));doc.delete_page(len(doc)-1)
    if removed_blank_pages:
     cleaned=pdf.with_suffix('.cleaned.pdf');doc.save(cleaned,garbage=4,deflate=True);doc.close();cleaned.replace(pdf);doc=fitz.open(pdf)
    preview=[]
    for i in range(len(doc)):
     dest=pdf.with_name(pdf.stem+f'-p{i+1:04d}.png');doc[i].get_pixmap(matrix=fitz.Matrix(.8,.8)).save(dest);preview.append(dest.relative_to(r).as_posix())
    actual_empty=[i+1 for i,pg in enumerate(doc) if page_is_visually_empty(pg)]
    dom_pages=len(layout.get('pages',[]))
    if page_errors:layout={**layout,'pass':False,'errors':layout.get('errors',[])+['Browser page error: '+x for x in page_errors]}
    if len(doc)!=dom_pages:
     layout={**layout,'pass':False,'errors':layout.get('errors',[])+['PDF/DOM page count mismatch'],'pdf_page_count':len(doc),'dom_page_count':dom_pages}
    attempts.append({'file':file.name,'adjustment_round':round,'route':'source' if all(d['route']=='source' for d in lp['documents']) else 'template','document_ids':[d['document_id'] for d in lp['documents']],'pass':layout.get('pass',False) and not actual_empty,'error':err,'layout':layout,'pdf_pages':len(doc),'removed_trailing_blank_pages':list(reversed(removed_blank_pages)),'empty_pdf_pages':actual_empty,'preview_files':preview,'candidate_pdf':pdf.relative_to(r).as_posix(),'candidate_sha256':sha(pdf),'adjustments':['initial inherited design','preserve columns/page ratio; reduce gaps and fit images within available region','preserve columns/page ratio; relax heading spacing and lower type size within readability bound'][round]})
    doc.close();page.close()
    if layout.get('pass') and not actual_empty:chosen=(pdf,layout,round)
    if layout.get('pass') and (not refine or round>=1):break
   if chosen:
    candidate,layout,rd=chosen;pdf=file.with_suffix('.pdf');shutil.copy2(candidate,pdf)
    # Embed the chosen adjustment so opening the HTML reproduces the same pagination.
    htmltext=file.read_text();htmltext=__import__('re').sub(r'<script data-layout-adjustment>.*?</script>','',htmltext);htmltext=htmltext.replace('<script>','<script data-layout-adjustment>window.layoutAdjustmentRound='+str(rd)+';</script><script>',1);file.write_text(htmltext)
    doc=fitz.open(pdf);doc.set_metadata({'title':m['title']+' · '+file.stem,'author':m.get('author_credit',''),'subject':'Translated reading edition; source scope and reviews in accompanying reports','creator':'Document Translation Skill','producer':'Chromium / PyMuPDF'});doc.saveIncr();pd=r/'reports/pages'/file.stem;pd.mkdir(parents=True,exist_ok=True)
    for old in pd.glob('page-*.png'):old.unlink()
    for i,pg in enumerate(doc):pg.get_pixmap(matrix=fitz.Matrix(1,1)).save(pd/f'page-{i+1:04d}.png')
    txt=''.join(pg.get_text() for pg in doc);(r/'reports'/(file.stem+'-pdf-text.txt')).write_text(txt)
    results.append({'file':file.name,'pdf':pdf.name,'pages':len(doc),'layout':layout,'chosen_adjustment_round':rd,'empty_pdf_pages':[i+1 for i,pg in enumerate(doc) if page_is_visually_empty(pg)],'html_sha256':sha(file),'pdf_sha256':sha(pdf)});doc.close()
   else:results.append({'file':file.name,'pdf':file.with_suffix('.pdf').name,'layout':{'pass':False},'error':'No source-preserving adjustment passed. Inspect candidate pages; template fallback requires severe visual rejection via layout-review.'})
  br.close()
 write(r/'reports/render-attempts.json',{'snapshot':snapshot,'attempts':attempts,'automatic_template_switching':False,'review_required':'Rendered candidates are evidence, not aesthetic or semantic certification.'})
 report={'snapshot':snapshot,'layout_plan_sha256':sha(r/'reports/layout-plan.json'),'outputs':results,'pass':bool(results) and all(x['layout']['pass'] and not x.get('empty_pdf_pages') for x in results)};write(r/'reports/layout.json',report);print(json.dumps({'rendered':len(results),'pages':{x['pdf']:x.get('pages') for x in results},'pass':report['pass']},ensure_ascii=False,indent=2))
 if not report['pass']:raise ValueError('Adjustment candidates need visual inspection and repair; no automatic template fallback was performed.')
