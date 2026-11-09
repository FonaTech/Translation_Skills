"""Escaped self-contained HTML, alignment and measured Chromium PDF output."""
from pathlib import Path
import base64,csv,html,json,os
from alignment import rows as aligned_rows
from reader_ui import toolbar as reader_toolbar, runtime as reader_runtime, styles as reader_styles
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
def pipeline_fingerprint():
 from translate import digest
 files=list(Path(__file__).parent.glob('*.py'))+[p for p in A.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 return digest({str(p.relative_to(A.parent)):sha(p) for p in sorted(files)})

def artifacts_current(r,m,c,kind):
 from translate import read
 report=r/'reports'/('build.json' if kind=='build' else 'layout.json')
 if not report.is_file():return False
 data=read(report)
 if data.get('snapshot')!=snap(m,c) or data.get('pipeline_fingerprint')!=pipeline_fingerprint():return False
 expected={f'{l}-{e}.html' for l in m['target_languages'] for e in m['editions']+['alignment']}
 if kind=='build':
  inventory=data.get('artifacts',{})
  if not expected.issubset(inventory):return False
  return all((r/'outputs'/f).is_file() and sha(r/'outputs'/f)==hsh for f,hsh in inventory.items())
 if {out.get('file') for out in data.get('outputs',[])}!=expected:return False
 return all((r/'outputs'/out[key]).is_file() and sha(r/'outputs'/out[key])==out.get(hashkey) for out in data['outputs'] for key,hashkey in [('file','html_sha256'),('pdf','pdf_sha256')])
def value(u,l,e):return u['translations'][l][e]
def uspan(u,l,e):return '<span class="trans-unit" data-uid="'+h(u['id'])+'"'+(' data-source-pages="'+h(','.join(map(str,sorted({seg['locator']['page'] for seg in u.get('source_segments',[]) if seg.get('locator',{}).get('page')}))))+'"' if u.get('source_segments') else '')+'>'+h(value(u,l,e))+'</span>'
def page_is_visually_empty(page):
 import fitz
 pix=page.get_pixmap(matrix=fitz.Matrix(.35,.35),colorspace=fitz.csGRAY,alpha=False)
 return not any(sample<255 for sample in pix.samples)
def source_pages(b):
 return sorted({x for x in [b['source'].get('page')]+[seg.get('locator',{}).get('page') for u in b.get('units',[]) for seg in u.get('source_segments',[])] if x is not None})
def loc(b):
 s=b['source'];pages=source_pages(b);return s['document_id']+(' · p'+','.join(map(str,pages)) if pages else ' · '+str(s.get('element','')))
def alignment_pair(b,u,l,editions,labels,*,last_in_block=False):
 keep=last_in_block and (b.get('type')=='heading' or b.get('presentation',{}).get('keep_next',False))
 uid=h(u['id']);b={**b,'units':[u]};attrs=' data-keep-next="'+str(bool(keep)).lower()+'" data-block="'+h(b['id'])+'" data-source-page="'+h(b['source'].get('page',''))+'" data-source-pages="'+h(','.join(map(str,source_pages(b))))+'"'
 notes=''.join('<aside class="editor-note">'+h(labels['note']+': '+n.get('note',''))+'</aside>' for n in u.get('notes',[]) if n.get('language',l)==l)
 return '<article class="pair"'+attrs+'><div class="locator pair-start">'+h(u['id']+' · '+loc(b))+'</div><div class="pair-grid">'+'<section class="pair-source" aria-label="'+h(labels['original'])+'"><p class="paragraph original" dir="auto"><span data-uid="'+uid+':source">'+h(u['source'])+'</span></p></section>'+''.join('<section class="pair-target" aria-label="'+h(labels[ed])+'"><p class="paragraph target"><span data-uid="'+uid+':'+ed+'">'+h(value(u,l,ed))+'</span></p></section>' for ed in editions)+'</div>'+notes+'</article>'

def block_attrs(b):
 p=b.get('presentation',{});role=p.get('role','body');span=p.get('span','auto')
 if role not in {'body','metadata','bibliography','abstract','keywords','caption','equation','note'}:role='body'
 if span not in {'auto','all','column'}:span='auto'
 hint=b.get('layout_hint',{});geometry=(' data-source-bbox="'+h(','.join(map(str,b['source']['bbox'])))+'"' if b['source'].get('bbox') else '')+' data-source-order="'+h(hint.get('order',''))+'" data-source-column="'+h(hint.get('column') or '')+'"'
 return geometry+' data-keep-next="'+str(p.get('keep_next',False)).lower()+'" data-block="'+h(b['id'])+'" data-source-page="'+h(b['source'].get('page',''))+'" data-span="'+span+'" class="paragraph block-'+role+'"'
def block_html(r,b,l,e,labels):
 typ=b['type'];txt=' '.join(uspan(u,l,e) for u in b.get('units',[]));locator='<div class="locator">'+h(loc(b))+' · '+h(b['id'])+'</div>';attrs=block_attrs(b)
 if b.get('format')=='code':
  rendered=[];source_lines=b.get('source_lines',[])
  left=min((x['bbox'][0] for x in source_lines),default=0);size=max(1,b.get('typography',{}).get('dominant_size_pt',10))
  def baseline(src):
   origins=[s.get('origin',[0,src['bbox'][3]])[1] for s in src.get('spans',[]) if s.get('text','').strip()]
   return sorted(origins)[len(origins)//2] if origins else src['bbox'][3]
  def visual_rows(pairs):
   groups=[]
   for pair in pairs:
    y=baseline(pair[1])
    if groups and abs(y-groups[-1]['baseline'])<=size*.35:
     groups[-1]['items'].append(pair)
     groups[-1]['baseline']=(groups[-1]['baseline']*(len(groups[-1]['items'])-1)+y)/len(groups[-1]['items'])
    else:groups.append({'baseline':y,'items':[pair]})
   return groups
  for u in b.get('units',[]):
   lines=value(u,l,e).split('\n')
   if len(lines)==len(source_lines):
    groups=visual_rows(list(zip(lines,source_lines)));visual=[]
    for group in groups:
     items=[];previous=None
     for line,src in group['items']:
      offset=max(0,(src['bbox'][0]-(previous['bbox'][2] if previous else left))/size)
      spacing='padding-inline-start:'+str(round(offset,3))+'em' if previous is None else 'margin-inline-start:'+str(round(offset,3))+'em'
      items.append('<span class="code-source-line" style="display:inline-block;'+spacing+'">'+h(line)+'</span>');previous=src
     visual.append('<span class="code-visual-row" style="display:block;white-space:pre">'+''.join(items)+'</span>')
    literal=''.join(visual)
   else:literal=h(value(u,l,e))
   rendered.append('<span class="trans-unit" data-uid="'+h(u['id'])+'">'+literal+'</span>')
  return '<pre'+attrs.replace('paragraph ','code-block ',1)+' style="white-space:pre-wrap;overflow-wrap:anywhere;text-align:start;font-family:ui-monospace,monospace;line-height:1.5"><code>'+'\n'.join(rendered)+'</code></pre>'
 if (typ=='reference' or b.get('presentation',{}).get('role')=='bibliography') and b.get('units'):
  # Each existing source unit remains intact. Do not infer reference boundaries
  # from punctuation or silently repair malformed bibliography strings.
  attrs=block_attrs({**b,'presentation':{**b.get('presentation',{}),'role':'bibliography'}})
  return ''.join('<p'+attrs+' data-reference-entry="true">'+uspan(u,l,e)+'</p>' for u in b['units'])
 if typ=='heading':
  lev=max(2,min(6,b.get('level',2)+1));return '<h'+str(lev)+(' data-title="true"' if b.get('level',2)==1 else '')+attrs.replace('paragraph ','')+'>'+txt+'</h'+str(lev)+'>'
 if typ=='table':
  lookup={u['id']:u for u in b['units']};n=b.get('header_rows',1);rows=[]
  for i,row in enumerate(b['rows']):
   tag='th' if i<n else 'td';rows.append('<tr>'+''.join(f'<{tag}>'+uspan(lookup[uid],l,e)+f'</{tag}>' for uid in row)+'</tr>')
  caps=''.join('<caption data-block="'+h(cb['id'])+'" data-source-page="'+h(cb['source'].get('page',''))+'">'+' '.join(uspan(u,l,e) for u in cb.get('units',[]))+'</caption>' for cb in b.get('_captions',[]))
  notes=''.join('<aside class="editor-note">'+h(labels['note']+': '+n.get('note',''))+'</aside>' for u in b.get('units',[]) for n in u.get('notes',[]) if n.get('language',l)==l)
  if notes:
   if caps:caps=caps.replace('</caption>',notes+'</caption>',1)
   else:caps='<caption>'+notes+'</caption>'
  return '<div'+attrs.replace('paragraph','table-wrap',1)+'><table>'+caps+'<thead>'+''.join(rows[:n])+'</thead><tbody>'+''.join(rows[n:])+'</tbody></table></div>'
 if typ in {'image','equation'}:
  p=safe(r,b['asset']);ext=p.suffix.lower().lstrip('.');mime='image/svg+xml' if ext=='svg' else 'image/jpeg' if ext in {'jpg','jpeg'} else 'image/'+ext
  if ext=='svg':
   from vector_assets import validate_svg,embedded_raster_colors
   validate_svg(p.read_bytes())
   if any(x['components'] not in (1,3) for x in embedded_raster_colors(p.read_bytes())):raise ValueError('Unsafe SVG raster colors: re-export from the source PDF before publishing.')
  src='data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode();label=b.get('label_policy','unreviewed')
  fallback=''
  if b.get('asset_fallback'):
   fp=safe(r,b['asset_fallback'])
   if fp.suffix.lower()!='.png':raise ValueError('Figure export fallback must be PNG.')
   fallback=' data-raster-fallback="data:image/png;base64,'+base64.b64encode(fp.read_bytes()).decode()+'"'
  caption=''.join('<p'+block_attrs(cb)+'>'+' '.join(uspan(u,l,e) for u in cb.get('units',[]))+'</p>'+''.join('<div class="editor-note">'+h(n.get('note',''))+'</div>' for u in cb.get('units',[]) for n in u.get('notes',[]) if n.get('language',l)==l) for cb in b.get('_captions',[]))
  note=h(b.get('label_note',label)) if label not in {'no-text','translated'} else ''
  return '<figure'+attrs.replace('paragraph','figure-block',1)+(' data-label-note="'+note+'"' if note else '')+'><img src="'+src+'"'+fallback+' alt="'+h(' '.join(value(u,l,e) for u in b.get('units',[])) or b['id'])+'" style="width:'+str(b.get('width_mm',150))+'mm"><figcaption>'+caption+('<div class="label-map">'+txt+'</div>' if txt else '')+'</figcaption><div class="locator figure-locator">'+h(loc(b))+' · '+h(b['id'])+'</div></figure>'
 if b.get('footnote'):
  links=''.join('<a href="#block-'+h(a['block_id'])+'" aria-label="Return to reference">↩</a>' for a in b['footnote']['anchors'] if b['footnote']['status']=='source-marker-matched')
  return '<aside id="block-'+h(b['id'])+'" role="doc-footnote"'+attrs+'>'+txt+links+'</aside>'
 refs=''.join('<a role="doc-noteref" href="#block-'+h(ref['note_block_id'])+'" aria-label="Footnote '+h(ref['marker'])+'">↗</a>' for ref in b.get('footnote_refs',[]))
 return '<p id="block-'+h(b['id'])+'"'+attrs+'>'+txt+refs+'</p>'
def source_presentation(c,source,l,e):
 """Use an existing document title for display; never rewrite source units."""
 if str(source.get('display_title','')).strip():return source
 title_block=next((b for b in c['blocks'] if b['source']['document_id']==source['id'] and b['type']=='heading' and b.get('level')==1 and b.get('units')),None)
 if title_block is None:return source
 edition='faithful' if e=='alignment' else e
 title=' '.join(value(u,l,edition) for u in title_block['units']).strip()
 return {**source,'display_title':title} if title else source

def document_section(m,source,x,l,e,lab):
 return {'alignmentLabels':[lab['original']]+[lab[ed] for ed in m['editions']] if e=='alignment' else None,'title':source.get('display_title',source['name']),'header':source.get('running_title',source.get('display_title',m['title'])),'footer':m.get('author_credit',''),'dir':m.get('direction',{}).get(l,'ltr'),'familyClass':'family-'+x['family'],'design':{'w':x['page_mm'][0],'h':x['page_mm'][1],'mx':x['margin_x_mm'],'my':x['margin_y_mm'],'cols':1 if e=='alignment' else x['columns'],'gap':x.get('column_gap_mm',7),'size':x['body_pt'],'leading':x['line_height'],'para':x.get('paragraph_gap_mm',1.8),'head':x.get('heading_gap_mm',3),'accent':x['accent'],'tableSize':x.get('table_pt',8),'cellPad':x.get('cell_padding_mm',1),'titleSize':x.get('title_pt',x['body_pt']*x.get('heading_ratio',1.65)),'captionSize':x.get('caption_pt',8),'font':x.get('font','serif')}}

def make_document(m,c,l,e,body,layout_plan):
 from layout_engine import design_css
 lab=LABELS.get(l.split('-')[0],LABELS['en']);direction=m.get('direction',{}).get(l,'ltr');css=(A/'layout.css').read_text()+'\n'+(A/'layout-flow.css').read_text()+'\n'+(A/'families.css').read_text()+'\n'+design_css(layout_plan);js='const CONTENT_CSS='+json.dumps((A/'document-content.css').read_text())+';const FAMILY_CSS="";const CATALOG=[];'+(A/'layout-model.js').read_text()+'\n'+(A/'layout-planner.js').read_text()+'\n'+(A/'layout-runtime.js').read_text()+'\n'+(A/'paginate.js').read_text();title=m['title']+' · '+lab.get(e,e)
 sections=[]
 for ds in layout_plan['documents']:
  x=ds['design'];source=source_presentation(c,next(z for z in c['sources'] if z['id']==ds['document_id']),l,e)
  sections.append(document_section(m,source,x,l,e,lab))
 js='window.layoutSections='+json.dumps(sections,ensure_ascii=False).replace('<','\\u003c')+';'+js+'\n'+'''window.openTranslationEditor=()=>{let popup;const listener=event=>{if(event.source!==popup)return;if(event.data?.type==='document-translation-editor-ready'){popup.postMessage({type:'document-translation-open-html',title:document.title,html:'<!doctype html>'+document.documentElement.outerHTML},'*');return;}if(event.data?.type==='document-translation-editor-loaded'||event.data?.type==='document-translation-editor-error')window.removeEventListener('message',listener);};window.addEventListener('message',listener);popup=window.open('document-layout-editor.html','documentTranslationLayoutEditor');if(!popup){window.removeEventListener('message',listener);alert(window.TranslationReader.t('popup'));}};'''
 return '<!doctype html><html lang="'+h(l)+'" dir="'+h(direction)+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\';script-src \'unsafe-inline\';style-src \'unsafe-inline\';img-src data: blob:;font-src data:;connect-src \'none\';base-uri \'none\'"><meta name="creator" content="Document Translation Skill"><title>'+h(title)+'</title><style>'+css+reader_styles()+'</style></head><body data-edition="'+h(lab.get(e,e))+'" data-footer="'+h(m.get('author_credit',''))+'" data-kind="'+e+'">'+reader_toolbar(m['title'],e)+'<main class="reader">'+body+'</main><script>'+reader_runtime()+js+'</script></body></html>'

def wrap_document(source,design,body,l,e,lab,has_title=False,settings=None):
 d=design['design'];ident=source['id'];scope=source.get('selection_scope','all');scope=json.dumps(scope,ensure_ascii=False) if isinstance(scope,dict) else str(scope)
 scope_text=('选取源页：' if l.startswith('zh') else 'Selected source pages: ')+', '.join(map(str,source['selection_scope']['pages'])) if isinstance(source.get('selection_scope'),dict) and 'pages' in source['selection_scope'] else ''
 # An interior-page excerpt has no source title to reconstruct. Keep the
 # filename in document metadata, rather than adding a large synthetic title
 # that pushes the first source plate onto a mostly empty extra page.
 excerpt=isinstance(source.get('selection_scope'),dict) and bool(source['selection_scope'].get('pages'))
 mast='<header class="mast'+(' excerpt-mast' if excerpt and not has_title else '')+'"><div class="edition">'+h(lab.get(e,e))+' · '+h(l)+'</div>'+('' if has_title or excerpt else '<h1>'+h(source.get('display_title',source['name']))+'</h1>')+'</header>'
 if scope_text or source.get('scope_note'):mast+='<div class="scope-list">'+h(scope_text)+' '+h(source.get('scope_note',''))+'</div>'
 # The document boundary carries its own measured page design. No synthetic headings or labels are inferred.
 stored=''
 if settings is not None:
  metadata={k:settings.get(k) for k in ['design','title','alignmentLabels','header','footer']}
  metadata.update(sourceDesign=settings['design'],route=design['route'],overrides={},locks={})
  stored=' data-studio-layout="'+h(json.dumps(metadata,ensure_ascii=False))+'"'
 return '<section class="layout-document family-'+h(d['family'])+'" data-layout-doc="'+h(ident)+'" data-columns="'+str(d['columns'] if e!='alignment' else 1)+'" data-family="'+h(d['family'])+'" data-route="'+h(design['route'])+'" data-template="'+h(d['id'])+'"'+stored+'>'+mast+body+'</section>'

def build(path,browser=None):
 from layout_engine import plan
 from asset_fidelity import verify_project
 from translate import enforce_figure_policy
 r,m,c=project(path);enforce_figure_policy(r,c);au=audit_data(r,m,c)
 if au['errors']:write(r/'reports/audit.json',au);raise ValueError('Build blocked: incomplete/invalid content; inspect reports/audit.json')
 verify_project(path,browser)
 r,m,c=project(path);au=audit_data(r,m,c)
 if au['errors']:write(r/'reports/audit.json',au);raise ValueError('Build blocked: incomplete/invalid content; inspect reports/audit.json')
 layout_plan=plan(r,m,c);write(r/'reports/layout-plan.json',layout_plan);designs={d['document_id']:d for d in layout_plan['documents']}
 for l in m['target_languages']:
  lab=LABELS.get(l.split('-')[0],LABELS['en'])
  for e in m['editions']+['alignment']:
   sections=[]
   for raw_source in c['sources']:
    source=source_presentation(c,raw_source,l,e)
    body=[]
    byid={b['id']:b for b in c['blocks']}
    bound={cid for b in c['blocks'] if b['source']['document_id']==source['id'] for cid in b.get('caption_block_ids',[])}
    caption_owner={cid:b['id'] for b in c['blocks'] for cid in b.get('caption_block_ids',[])}
    emitted_groups=set()
    for b in c['blocks']:
     if b['source']['document_id']!=source['id']:continue
     group=b.get('figure_group_id')
     parts=[x for x in c['blocks'] if group and x.get('figure_group_id')==group and x['source']['document_id']==source['id']]
     if len(parts)>1:
      if group in emitted_groups:continue
      emitted_groups.add(group)
      fragments=[]
      for part in parts:
       item={**part,'_captions':[],**({'units':[]} if e=='alignment' else {})}
       fragments.append(block_html(r,item,l,'faithful' if e=='alignment' else e,lab))
      captions=[byid[cid] for cid in b.get('caption_block_ids',[])]
      if e=='alignment':body.append('<div class="alignment-figure" data-span="all" data-source-page="'+h(b['source'].get('page',''))+'">')
      caption=''.join('<p'+block_attrs(cb)+'>'+' '.join(uspan(u,l,e) for u in cb.get('units',[]))+'</p>'+''.join('<div class="editor-note">'+h(n.get('note',''))+'</div>' for u in cb.get('units',[]) for n in u.get('notes',[]) if n.get('language',l)==l) for cb in captions) if e!='alignment' else ''
      body.append('<figure class="figure-group" data-span="'+('all' if e=='alignment' else 'column')+'" data-keep-next="'+str(e=='alignment' and bool(captions)).lower()+'" data-source-page="'+h(b['source'].get('page',''))+'" data-figure-group="'+h(group)+'"><div class="figure-group-parts">'+''.join(fragments)+'</div><figcaption>'+caption+'</figcaption></figure>')
      if e=='alignment':
       for part in parts:
        for parent in part.get('units',[]):
         for row in aligned_rows(parent,l):body.append(alignment_pair(part,row,l,m['editions'],lab))
       for cb in captions:
        for parent in cb.get('units',[]):
         for row in aligned_rows(parent,l):body.append(alignment_pair(cb,row,l,m['editions'],lab))
       body.append('</div>')
      continue
     if b['id'] in bound and (e!='alignment' or byid[caption_owner[b['id']]]['type'] in {'image','equation'}):continue
     if e!='alignment' and b.get('caption_block_ids'):b={**b,'_captions':[byid[cid] for cid in b['caption_block_ids'] if caption_owner[cid]==b['id']]}
     if e=='alignment' and b['type']=='table':
      cells={u['id']:u for u in b['units']};lines=[]
      for ri,row in enumerate(b['rows'],1):
       for ci,uid in enumerate(row,1):
        for u in aligned_rows(cells[uid],l):
         ident=h(u['id']);lines.append('<tr><td title="'+ident+'">'+str(ri)+':'+str(ci)+'</td><td><span data-uid="'+ident+':source">'+h(u['source'])+'</span></td>'+''.join('<td><span data-uid="'+ident+':'+ed+'">'+h(value(u,l,ed))+'</span></td>' for ed in m['editions'])+'</tr>')
      notes=''.join('<aside class="editor-note">'+h(lab['note']+': '+n.get('note',''))+'</aside>' for u in b.get('units',[]) for n in u.get('notes',[]) if n.get('language',l)==l)
      body.append('<p class="locator" data-block="'+h(b['id'])+'" data-source-page="'+h(b['source'].get('page',''))+'">'+h(loc(b)+' · '+b['id'])+'</p><div class="table-wrap alignment-cells" data-block="'+h(b['id'])+'" data-source-page="'+h(b['source'].get('page',''))+'"><table>'+('<caption>'+notes+'</caption>' if notes else '')+'<colgroup><col style="width:12%"><col style="width:29%"><col style="width:29%"><col style="width:30%"></colgroup><thead><tr><th>行:列 / R:C</th><th>'+h(lab['original'])+'</th>'+''.join('<th>'+h(lab[ed])+'</th>' for ed in m['editions'])+'</tr></thead><tbody>'+''.join(lines)+'</tbody></table></div>')
     elif e=='alignment':
      # Alignment archives must preserve the figures too, including vector crops.
      graphic=b['type'] in {'image','equation'}
      if graphic:body.append('<div class="alignment-figure" data-span="all" data-source-page="'+h(b['source'].get('page',''))+'">'+block_html(r,{**b,'units':[],'presentation':{**b.get('presentation',{}),'span':'all'}},l,'faithful',lab))
      rows=[u for parent in b.get('units',[]) for u in aligned_rows(parent,l)]
      for index,u in enumerate(rows):
       body.append(alignment_pair(b,u,l,m['editions'],lab,last_in_block=index==len(rows)-1))
      if graphic:
       for cid in b.get('caption_block_ids',[]):
        cb=byid[cid]
        for parent in cb.get('units',[]):
         for row in aligned_rows(parent,l):body.append(alignment_pair(cb,row,l,m['editions'],lab))
       body.append('</div>')
     else:
      body.append(block_html(r,b,l,e,lab))
      if b['type']!='table':body+=['<p class="editor-note">'+h(lab['note']+': '+n.get('note',''))+'</p>' for u in b.get('units',[]) for n in u.get('notes',[]) if n.get('language',l)==l]
    has_title=e!='alignment' and any(b['source']['document_id']==source['id'] and b['type']=='heading' and b.get('level',2)==1 for b in c['blocks'])
    settings=document_section(m,source,designs[source['id']]['design'],l,e,lab)
    sections.append(wrap_document(source,designs[source['id']],''.join(body),l,e,lab,has_title,settings))
   (r/'outputs'/f'{l}-{e}.html').write_text(make_document(m,c,l,e,''.join(sections),layout_plan),encoding='utf-8')
  with (r/'outputs'/f'{l}-alignment.csv').open('w',newline='',encoding='utf-8-sig') as f:
   cw=csv.writer(f);cw.writerow(['unit_id','document_id','page_or_element','source','faithful','interpretive','review_notes'])
   for b,parent in units(c):
    for u in aligned_rows(parent,l):cw.writerow([u['id'],b['source']['document_id'],','.join(map(str,source_pages({**b,'units':[parent]}))) or b['source'].get('element',''),u['source'],value(u,l,'faithful'),value(u,l,'interpretive'),json.dumps(u.get('notes',[]),ensure_ascii=False)])
 shutil=__import__('shutil');editor=A/'document-layout-editor.html';shutil.copy2(editor,r/'outputs/document-layout-editor.html');write(r/'reports/editor.json',{'version':'1.0.2','file':'document-layout-editor.html','sha256':sha(editor),'runtime_dependencies':[]})
 write(r/'reports/build.json',{'snapshot':snap(m,c),'pipeline_fingerprint':pipeline_fingerprint(),'artifacts':{p.name:sha(p) for p in (r/'outputs').iterdir() if p.suffix in {'.html','.csv'}},'layout_plan_sha256':sha(r/'reports/layout-plan.json'),'html':[p.name for p in (r/'outputs').glob('*.html') if p.name!='document-layout-editor.html'],'translation_supplied_by':'invoking agent/user','meaning_verified':False});print('Built per-document source-adapted HTML and CSV alignment.')

def persist_layout_metadata(htmltext,metadata):
 """Persist actual painted layout for safe disk import without script execution."""
 import re
 index=0
 def replace_section(match):
  nonlocal index
  if index>=len(metadata):raise ValueError('Rendered layout metadata has too few sections.')
  opening=match.group(0);value=h(json.dumps(metadata[index],ensure_ascii=False));index+=1
  if 'data-studio-layout=' not in opening:raise ValueError('Missing static editor metadata on document section.')
  return re.sub(r'data-studio-layout="[^"]*"',lambda _: 'data-studio-layout="'+value+'"',opening,count=1)
 result=re.sub(r'<section\b[^>]*\bdata-layout-doc="[^"]*"[^>]*>',replace_section,htmltext)
 if index!=len(metadata):raise ValueError('Rendered layout metadata has too many sections.')
 return result

def render(path,browser=None,refine=False):
 from playwright.sync_api import sync_playwright
 from layout_engine import freshness
 import fitz,shutil
 from asset_fidelity import verify_project,verify_rendered_figures
 from translate import enforce_figure_policy
 r,m,c=project(path)
 if enforce_figure_policy(r,c):build(path,browser)
 fidelity=verify_project(path,browser)
 if fidelity['content_changed']:build(path,browser)
 r,m,c=project(path);snapshot=snap(m,c);ok,why=freshness(r,m,c)
 if not ok:raise ValueError('Build first: '+why)
 lp=__import__('translate').read(r/'reports/layout-plan.json');results=[];exe=browser or os.environ.get('TRANSLATION_BROWSER');attempts=[]
 with sync_playwright() as p:
  br=p.chromium.launch(headless=True,**({'executable_path':exe} if exe else {}))
  for file in [r/'outputs'/f'{lang}-{ed}.html' for lang in m['target_languages'] for ed in m['editions']+['alignment']]:
   chosen=None;selected_sections=None;optimization=None
   for round in range(3):
    page=br.new_page(viewport={'width':1280,'height':1400});page_errors=[];page.on('pageerror',lambda e:page_errors.append(str(e)));page.goto(file.as_uri(),wait_until='load',timeout=90000)
    page.wait_for_function('()=>window.translationReady || window.translationError',timeout=90000)
    if round==0:
     ranked=page.evaluate('()=>window.optimizeTranslationLayout()')
     selected_sections=page.evaluate('()=>window.layoutChosenSections');optimization=ranked['optimization']
    if round:
     page.evaluate('(data)=>{window.translationReady=false;window.translationError=null;window.layoutChosenSections=data.sections;window.layoutAdjustmentRound=data.round;}',{'round':round,'sections':selected_sections})
     page.evaluate('paginate().catch(e=>{window.translationError=String(e);window.translationLayout={pass:false,error:String(e)};})')
    page.wait_for_function('()=>window.translationReady || window.translationError',timeout=90000);err=page.evaluate('window.translationError');layout=page.evaluate('window.translationLayout') or {'pass':False,'error':err};layout['optimization']=optimization;pdf=r/'reports/candidates'/f'{file.stem}-adjust-{round}.pdf';pdf.parent.mkdir(exist_ok=True)
    page.emulate_media(media='print')
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
    figure_report=None
    if len(doc)==dom_pages:
     figure_report=verify_rendered_figures(r,page,pdf,file.stem+'-adjust-'+str(round))
     layout['figure_fidelity']={'pass':figure_report['pass'],'figures':len(figure_report['figures']),'missing_figures':figure_report['missing_figures']}
     if not figure_report['pass']:layout={**layout,'pass':False,'errors':layout.get('errors',[])+['Actual PDF figure appearance differs from source; inspect reports/figure-pdf-'+file.stem+'-adjust-'+str(round)+'.json']}
    attempts.append({'file':file.name,'adjustment_round':round,'route':'source' if all(d['route']=='source' for d in lp['documents']) else 'template','document_ids':[d['document_id'] for d in lp['documents']],'pass':layout.get('pass',False) and not actual_empty,'error':err,'layout':layout,'pdf_pages':len(doc),'removed_trailing_blank_pages':list(reversed(removed_blank_pages)),'empty_pdf_pages':actual_empty,'preview_files':preview,'candidate_pdf':pdf.relative_to(r).as_posix(),'candidate_sha256':sha(pdf),'adjustments':['initial inherited design','preserve columns/page ratio; reduce gaps and fit images within available region','preserve columns/page ratio; relax heading spacing and lower type size within readability bound'][round]})
    metadata=page.evaluate('()=>[...document.querySelectorAll(".reader > .layout-document")].map(el=>JSON.parse(el.getAttribute("data-studio-layout")))')
    doc.close();page.close()
    if layout.get('pass') and not actual_empty:chosen=(pdf,layout,round,figure_report,metadata)
    if layout.get('pass') and (not refine or round>=1):break
   if chosen:
    candidate,layout,rd,figure_report,metadata=chosen;pdf=file.with_suffix('.pdf');shutil.copy2(candidate,pdf)
    # Embed the chosen adjustment so opening the HTML reproduces the same pagination.
    htmltext=persist_layout_metadata(file.read_text(),metadata);htmltext=__import__('re').sub(r'<script data-layout-adjustment>.*?</script>','',htmltext);settings='window.layoutAdjustmentRound='+str(rd)+';window.layoutChosenSections='+json.dumps(selected_sections,ensure_ascii=False).replace('<','\\u003c')+';window.layoutOptimization='+json.dumps(optimization,ensure_ascii=False).replace('<','\\u003c')+';';htmltext=htmltext.replace('<script>','<script data-layout-adjustment>'+settings+'</script><script>',1);file.write_text(htmltext)
    doc=fitz.open(pdf);doc.set_metadata({'title':m['title']+' · '+file.stem,'author':m.get('author_credit',''),'subject':'Translated reading edition; source scope and reviews in accompanying reports','creator':'Document Translation Skill','producer':'Chromium / PyMuPDF'});doc.saveIncr();pd=r/'reports/pages'/file.stem;pd.mkdir(parents=True,exist_ok=True)
    for old in pd.glob('page-*.png'):old.unlink()
    for i,pg in enumerate(doc):pg.get_pixmap(matrix=fitz.Matrix(1,1)).save(pd/f'page-{i+1:04d}.png')
    txt=''.join(pg.get_text() for pg in doc);(r/'reports'/(file.stem+'-pdf-text.txt')).write_text(txt)
    results.append({'file':file.name,'pdf':pdf.name,'pages':len(doc),'layout':layout,'chosen_adjustment_round':rd,'empty_pdf_pages':[i+1 for i,pg in enumerate(doc) if page_is_visually_empty(pg)],'html_sha256':sha(file),'pdf_sha256':sha(pdf)});doc.close()
    if figure_report is not None:
     figure_report={**figure_report,'edition':file.stem,'pdf_sha256':sha(pdf)}
     write(r/'reports'/('figure-pdf-'+file.stem+'.json'),figure_report)
   else:results.append({'file':file.name,'pdf':file.with_suffix('.pdf').name,'layout':{'pass':False},'error':'No source-preserving adjustment passed. Inspect candidate pages; template fallback requires severe visual rejection via layout-review.'})
  br.close()
 write(r/'reports/render-attempts.json',{'snapshot':snapshot,'attempts':attempts,'automatic_template_switching':False,'review_required':'Rendered candidates are evidence, not aesthetic or semantic certification.'})
 report={'snapshot':snapshot,'pipeline_fingerprint':pipeline_fingerprint(),'layout_plan_sha256':sha(r/'reports/layout-plan.json'),'outputs':results,'pass':bool(results) and all(x['layout']['pass'] and not x.get('empty_pdf_pages') for x in results)};write(r/'reports/layout.json',report)
 buildfile=r/'reports/build.json'
 if buildfile.exists():
  built=__import__('translate').read(buildfile)
  built['artifacts']={p.name:sha(p) for p in (r/'outputs').iterdir() if p.suffix in {'.html','.csv'}};write(buildfile,built)
 print(json.dumps({'rendered':len(results),'pages':{x['pdf']:x.get('pages') for x in results},'pass':report['pass']},ensure_ascii=False,indent=2))
 if not report['pass']:raise ValueError('Adjustment candidates need visual inspection and repair; no automatic template fallback was performed.')
