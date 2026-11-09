"""Source-first visual profiling and explicit, heuristic fallback decisions.
Never executes source HTML/JS. Scores are engineering heuristics, not probabilities.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,re,statistics,shutil,xml.etree.ElementTree as ET,zipfile
from translate import project,write,read,sha,snap,safe,digest
ASSETS=Path(__file__).resolve().parent.parent/'assets'
def catalog():return read(ASSETS/'layout-catalog.json')['presets']
def clamp(x,lo,hi):return max(lo,min(hi,float(x)))
def color(n):return '#'+format(int(n)&0xffffff,'06x')
def readable_accent(value,fallback='#304659'):
 """Ignore pale watermark/background text when choosing ink on white."""
 if not isinstance(value,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):return fallback
 channels=[int(value[i:i+2],16)/255 for i in (1,3,5)]
 linear=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in channels]
 luminance=sum(w*x for w,x in zip((.2126,.7152,.0722),linear))
 return value if 1.05/(luminance+.05)>=4.5 else fallback
def median(xs,default):return statistics.median(xs) if xs else default
def font_kind(s):return 'sans' if re.search(r'arial|helvetica|sans|calibri|gothic|黑体',s,re.I) else 'serif'
def pdf_profile(path,selected_pages=None):
 import fitz
 d=fitz.open(path);pages=[];sizes=[];fonts=[];colors=[];colored_spans=[];content=[];images=0;tables=0;headings=0;columns=[];linegaps=[];rules=[]
 for pn,p in enumerate(d):
  if selected_pages and pn+1 not in selected_pages:continue
  texts=[];blocks=p.get_text('dict')['blocks'];spans=[]
  for b in blocks:
   if b['type']!=0:continue
   texts.append(b)
   for line in b['lines']:
    ss=[s for s in line['spans'] if s['text'].strip()];spans+=ss
    for s in ss:
     sizes.extend([s['size']]*min(80,len(s['text'])));fonts.extend([s['font']]*min(80,len(s['text'])))
     # Normalize signed ARGB values exposed by some PyMuPDF versions.
     rgb=int(s['color'])&0xffffff
     if rgb not in {0,16777215} and readable_accent(color(rgb),None):
      colors.extend([rgb]*min(30,len(s['text'])));colored_spans.append(s)
    if len(b['lines'])>1:
     ys=[l['bbox'][1] for l in b['lines']];linegaps.extend(ys[i+1]-ys[i] for i in range(len(ys)-1) if 5<ys[i+1]-ys[i]<40)
  body=median([s['size'] for s in spans],11);hs=[s for s in spans if s['size']>body*1.35];headings+=len(hs)
  rects=[b['bbox'] for b in texts if len(''.join(s['text'] for l in b['lines'] for s in l['spans']))>12]
  w,h=p.rect.width,p.rect.height;col=1;centers=[]
  # Cluster left edges only for narrow paragraph regions, never single individual lines.
  paragraph_rects=[b['bbox'] for b in texts if sum(len(s['text']) for l in b['lines'] for s in l['spans'])>160 and len(b['lines'])>=3 and b['bbox'][3]-b['bbox'][1]<h*.8]
  for bb in paragraph_rects:
   if (bb[2]-bb[0])<w*.56:
    x=bb[0]/w
    existing=next((a for a in centers if abs(a[0]-x)<.08),None)
    if existing:existing[1]+=1
    else:centers.append([x,1])
  valid=sorted(x for x,n in centers if n>=2 or len(centers)<=2)
  if len(valid)>=2 and valid[-1]-valid[0]>.25:col=min(3,len(valid))
  columns.append(col);images+=len(p.get_image_info())
  draws=p.get_drawings();rule=sum(1 for x in draws if len(x.get('items',[]))<=5 and x.get('rect').height<4);rules.append(rule);tables+=int(len(draws)>15)
  if rects:
   bb=[min(x[0] for x in rects),min(x[1] for x in rects),max(x[2] for x in rects),max(x[3] for x in rects)];content.append(bb)
  else:bb=[w*.08,h*.08,w*.92,h*.92]
  pages.append({'page':pn+1,'width_pt':round(w,2),'height_pt':round(h,2),'columns':col,'native_chars':len(p.get_text().strip()),'images':len(p.get_image_info()),'content_bbox':list(bb),'horizontal_rules':rule})
 n=max(len(pages),1);body=median(sizes,11);w=median([p['width_pt'] for p in pages],595.3);h=median([p['height_pt'] for p in pages],841.9);chars=sum(p['native_chars'] for p in pages);native=sum(p['native_chars']>60 for p in pages)/n;bodyfont=Counter(fonts).most_common(1)
 # Near-black body ink can dominate counts even when the source title has a
 # clear colour. Prefer readable chromatic, title-sized spans over body ink.
 heading_ink=[]
 for s in colored_spans:
  rgb=[(int(s['color'])>>shift)&255 for shift in (16,8,0)]
  if s['size']>=body*1.18 and max(rgb)-min(rgb)>=32:heading_ink.extend([s['color']]*min(80,len(s['text'])))
 accent=Counter(heading_ink or colors).most_common(1)
 left=median([b[0]/w for b in content],.075);right=median([(w-b[2])/w for b in content],.075);top=median([b[1]/h for b in content],.06)
 score=round(.20+.30*native+.15*bool(fonts)+.12*bool(content)+.10*(len(set(columns))<=2)+.08*(chars>100)+.05*bool(accent or sum(rules)),3)
 doc={'kind':'pdf','pages':pages,'native_text_fraction':native,'body_pt':round(body,2),'font':font_kind(bodyfont[0][0]) if bodyfont else 'serif','accent':color(accent[0][0]) if accent else '#304659','columns':max(Counter(columns),key=lambda x:(Counter(columns)[x],x)),'page_mm':[round(w*25.4/72,2),round(h*25.4/72,2)],'margin_x_mm':round(clamp(min(left,right)*w*25.4/72,10,30),1),'margin_y_mm':round(clamp(top*h*25.4/72,14,28),1),'line_height':round(clamp(median(linegaps,body*1.6)/max(body,1),1.45,1.95),2),'heading_ratio':round(clamp(max(sizes,default=body)/max(body,1),1.25,2.5),2),'heading_rule':sum(rules)>0,'feature_confidence':score,'features':{'text':native,'images':min(1,images/n*.25),'tables':tables/n,'headings':min(1,headings/n*.1),'columns':max(Counter(columns),key=lambda x:(Counter(columns)[x],x)),'landscape':int(w>h),'linebreaks':0},'evidence':['Native text/font geometry from all pages','Column estimate from repeated narrow-block left edges','Color and horizontal-rule signals; original font binaries not copied'],'limits':['Heuristic column detection; source reading order and figures still require page review','Scans/outlined text need visual profiling or explicit agent supplement','Unusual sidebars, merged cells and mixed page layouts may need structural repair']}
 d.close();return doc

def html_profile(path):
 text=Path(path).read_text(encoding='utf-8-sig');styles='\n'.join(re.findall(r'<style\b[^>]*>([\s\S]*?)</style>',text,re.I));css=re.sub(r'/\*[\s\S]*?\*/','',styles)
 rules=[(s.strip(),b) for s,b in re.findall(r'([^{}]+)\{([^{}]*)\}',css) if '@' not in s]
 def prop(selector,name,default=None):
  vals=[]
  for sel,body in rules:
   if re.search(selector,sel,re.I):vals+=re.findall(r'(?:^|;)\s*'+re.escape(name)+r'\s*:\s*([^;]+)',body,re.I)
  return vals[-1].strip() if vals else default
 def mm(s,default):
  if not s:return default
  m=re.search(r'([\d.]+)\s*(mm|cm|pt|px)?',s)
  return float(m[1])*{'mm':1,'cm':10,'pt':25.4/72,'px':25.4/96,None:1}[m[2]] if m else default
 def pt(s,default):return mm(s,default*25.4/72)*72/25.4
 page=re.search(r'@page\s*\{([^}]+)',css,re.I);paper=page[1] if page else '';size=re.search(r'size\s*:\s*([^;]+)',paper,re.I);width=mm(prop(r'\.page\b|\.sheet\b','width'),210);height=mm(prop(r'\.page\b|\.sheet\b','height'),297)
 if size and 'landscape' in size[1]:width,height=297,210
 if size and 'letter' in size[1].lower():width,height=(279,216) if 'landscape' in size[1] else (216,279)
 if size and re.search(r'\d+mm\s+\d+mm',size[1]):nums=re.findall(r'[\d.]+',size[1]);width,height=map(float,nums[:2])
 cols=[int(x) for x in re.findall(r'column-count\s*:\s*([123])',css,re.I)];grids=re.findall(r'grid-template-columns\s*:\s*([^;\n}]+)',css,re.I)
 for g in grids:
  mt=re.search(r'repeat\(\s*([123])\s*,',g)
  if mt:cols.append(int(mt[1]))
  elif g.count('fr') in [2,3]:cols.append(g.count('fr'))
 # Count max structural columns, excluding responsive overrides which generally reduce to one.
 columns=max(cols,default=1);fs=prop(r'(?:^|,)\s*body\b','font-family','serif');sz=pt(prop(r'(?:^|,)\s*p\b|\.prose\b|\.cols\s+p|\.paragraph\b','font-size'),11)
 pad=prop(r'\.page\b|\.sheet\b','padding','18mm 18mm');pads=re.findall(r'[\d.]+(?:mm|cm|px|pt)',pad);margx=mm(pads[1] if len(pads)>1 else pads[0],18) if pads else 18;margy=mm(pads[0],18) if pads else 18
 accent=re.findall(r'--accent\s*:\s*(#[0-9a-fA-F]{3,8})',css);colors=re.findall(r'(?:color|border-color)\s*:\s*(#[0-9a-fA-F]{6})',css);acc=accent[-1] if accent else next((x for x in colors if x.lower() not in {'#000000','#ffffff'}),'#304659')
 lh=prop(r'(?:^|,)\s*p\b|\.prose\b|\.cols\s+p|\.paragraph\b','line-height','1.7');lead=float(lh) if re.fullmatch(r'[\d.]+',lh) else 1.7
 images=len(re.findall(r'<img\b',text,re.I));tables=len(re.findall(r'<table\b',text,re.I));hs=len(re.findall(r'<h[1-6]\b',text,re.I));score=round(.25+.22*bool(styles)+.13*bool(page)+.12*bool(cols)+.12*bool(rules)+.10*bool(accent or colors)+.06*bool(pads),3)
 return {'kind':'html','pages':[],'body_pt':round(sz,2),'font':font_kind(fs),'accent':acc,'columns':columns,'page_mm':[width,height],'margin_x_mm':clamp(margx,10,30),'margin_y_mm':clamp(margy,14,28),'line_height':clamp(lead,1.45,1.95),'heading_ratio':clamp(pt(prop(r'(?:^|,)\s*h1\b','font-size'),22)/max(sz,1),1.3,2.5),'heading_rule':bool(re.search(r'border-bottom\s*:',css)),'feature_confidence':score,'features':{'text':1,'images':min(1,images*.1),'tables':min(1,tables*.2),'headings':min(1,hs*.1),'columns':columns,'landscape':int(width>height),'linebreaks':float('<pre' in text)},'evidence':['Static CSS declarations and DOM structure; no source scripts executed','Allowlisted numeric/color/structure signals only; source CSS is not copied verbatim'],'limits':['CSS extraction is provisional for external styles, media queries, nested grids, absolute positioning and dynamic pages','Visual hierarchy and reading order still require the actual source view']}

def docx_profile(path):
 ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};w='{'+ns['w']+'}'
 with zipfile.ZipFile(path) as z:
  doc=ET.fromstring(z.read('word/document.xml'));sec=doc.find('.//w:sectPr',ns);pg=sec.find('w:pgSz',ns) if sec is not None else None;mar=sec.find('w:pgMar',ns) if sec is not None else None;cols=sec.find('w:cols',ns) if sec is not None else None
  size=[float(pg.get(w+k,default))*25.4/1440 for k,default in [('w','11906'),('h','16838')]] if pg is not None else [210,297]
  styles=ET.fromstring(z.read('word/styles.xml')) if 'word/styles.xml' in z.namelist() else doc
  sizes=[float(x.get(w+'val'))/2 for x in styles.findall('.//w:sz',ns) if x.get(w+'val','').isdigit()];colors=[x.get(w+'val') for x in styles.findall('.//w:color',ns) if re.fullmatch('[0-9A-Fa-f]{6}',x.get(w+'val','')) and x.get(w+'val') not in {'000000','FFFFFF'}];nf=doc.findall('.//w:tbl',ns);heads=doc.findall('.//w:pStyle',ns)
 return {'kind':'docx','pages':[],'body_pt':clamp(median(sizes,11),9.5,14),'font':'serif','accent':'#'+colors[0] if colors else '#34495b','columns':int(cols.get(w+'num','1')) if cols is not None else 1,'page_mm':size,'margin_x_mm':clamp(float(mar.get(w+'left','1134'))*25.4/1440,10,30) if mar is not None else 20,'margin_y_mm':clamp(float(mar.get(w+'top','1134'))*25.4/1440,14,28) if mar is not None else 20,'line_height':1.7,'heading_ratio':1.6,'heading_rule':False,'feature_confidence':.76 if sec is not None else .55,'features':{'text':1,'columns':int(cols.get(w+'num','1')) if cols is not None else 1,'tables':min(1,len(nf)*.25),'headings':min(1,len(heads)*.1),'images':0,'landscape':int(size[0]>size[1]),'linebreaks':0},'evidence':['OOXML section size/margins/columns and styles; no macros executed'],'limits':['DOCX typography, headers and anchored objects require native visual comparison']}

def profile(path,selected_pages=None):
 suffix=Path(path).suffix.lower()
 if suffix=='.pdf':result=pdf_profile(path,selected_pages)
 elif suffix in {'.html','.htm'}:result=html_profile(path)
 elif suffix=='.docx':result=docx_profile(path)
 else:result={'kind':'unprofiled','pages':[],'feature_confidence':.25,'features':{'text':.5,'tables':float(suffix in {'.csv','.tsv'}),'columns':1},'evidence':['No recoverable page-design geometry from this input route'],'limits':['Use agent visual supplement for scans/images; plain text has no authoritative page design']}
 result['source_sha256']=sha(path);return result

def rank_templates(features,requested=None):
 rows=[]
 for t in catalog():
  components=[]
  for k,v in t['fit_features'].items():
   got=features.get(k,0 if k not in {'text','columns'} else 1);dist=abs(float(got)-float(v));fit=1-min(1,dist/(2 if k=='columns' else 1));components.append(fit)
  score=sum(components)/len(components);score=.55+.40*score
  if features.get('columns',1)==t['columns']:score+=.025
  rows.append({'template':t['id'],'fit_score':round(min(.99,score),3),'reason':{'source_features':features,'template_features':t['fit_features']},'explicit_request':requested==t['id']})
 return sorted(rows,key=lambda x:(x['explicit_request'],x['fit_score']),reverse=True)

def source_design(p):
 cols=int(clamp(p.get('columns',1),1,3));width,height=p.get('page_mm',[210,297]);width=clamp(width,140,420);height=clamp(height,140,420)
 return {'id':'source-adapted','family':'source','columns':cols,'font':p.get('font','serif'),'body_pt':clamp(p.get('body_pt',11),9.5 if cols<3 else 9,14),'line_height':clamp(p.get('line_height',1.7),1.45,1.95),'margin_x_mm':clamp(p.get('margin_x_mm',18),10,30),'margin_y_mm':clamp(p.get('margin_y_mm',18),14,28),'accent':readable_accent(p.get('accent','#304659')),'page_mm':[width,height],'heading_ratio':p.get('heading_ratio',1.7),'heading_rule':p.get('heading_rule',False),'structural_signature':'source:'+str(cols)+':'+str(round(width/height,2))}

def configure(a):
 r,m,c=project(a.project);conf=m.get('layout',{});conf.update({'policy':a.policy,'confidence_threshold':a.threshold,'max_template_candidates':3})
 if not 0<=a.threshold<=1:raise ValueError('Threshold must be within 0..1.')
 if a.template:
  if a.template not in {x['id'] for x in catalog()}:raise ValueError('Unknown layout template.')
  if a.policy!='template':raise ValueError('An explicit template requires --policy template; source-first fallback is ranked automatically after visual review.')
  conf['template']=a.template
 if a.reference:
  src=Path(a.reference).expanduser().resolve()
  if not src.is_file():raise ValueError('Reference layout does not exist.')
  dest=r/'sources'/('layout-reference-'+sha(src)[:12]+src.suffix.lower());shutil.copy2(src,dest);conf['reference']={'file':dest.relative_to(r).as_posix(),'sha256':sha(dest),'name':src.name}
 if a.reject_source:raise ValueError('Use layout-review after rendering and adjustments. A rejection note alone cannot authorize fallback.')
 conf.pop('source_rejection',None);m['layout']=conf;write(r/'project.json',m);result=plan(r,m,c);write(r/'reports/layout-plan.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))

def fallback_review(a):
 from translate import source_snap,now
 r,m,c=project(a.project);rp=r/'reports/render-attempts.json'
 if not rp.exists():raise ValueError('Render and adjust the source design before requesting fallback.')
 attempts=read(rp)
 if attempts.get('snapshot')!=snap(m,c):raise ValueError('Render evidence is stale; render current content/configuration first.')
 if a.document not in {x['id'] for x in c['sources']}:raise ValueError('Unknown document.')
 relevant=[x for x in attempts.get('attempts',[]) if a.document in x.get('document_ids',[]) and x.get('route')=='source']
 # The second attempt may be geometry-driven or an explicit visual refinement. Never silently fallback from confidence alone.
 if len({x.get('adjustment_round',0) for x in relevant})<2:raise ValueError('At least one rendered source-layout adjustment must be compared with the initial rendering.')
 if not a.notes.strip() or not a.reason.strip():raise ValueError('Describe the severe visual defect and why source-preserving adjustments cannot resolve it.')
 artifacts={}
 for x in relevant:
  for rel in x.get('preview_files',[]):
   file=safe(r,rel)
   if file.exists():artifacts[rel]=sha(file)
 if not artifacts:raise ValueError('No rendered visual artifacts available for review.')
 frozen=r/'reports/layout-source-evidence'/('render-'+sha(rp)+'.json');frozen.parent.mkdir(exist_ok=True);shutil.copy2(rp,frozen)
 review={'evidence_report':frozen.relative_to(r).as_posix(),'at':now(),'document_id':a.document,'reviewer':a.reviewer,'severity':'severe','adjustments_exhausted':True,'reason':a.reason,'notes':a.notes,'source_snapshot':source_snap(m,c),'render_report_sha256':sha(rp),'artifacts':artifacts,'assessment':'Invoking agent/user visual judgment; not inferred from geometry or score alone'}
 path=r/'reports/layout-fallback-review.json';reviews=read(path) if path.exists() else [];reviews=[x for x in reviews if x['document_id']!=a.document]+[review];write(path,reviews);print('Recorded source-layout rejection; next build selects the highest-scoring compatible template.')

def valid_rejection(root,m,c,did):
 from translate import source_snap
 path=Path(root)/'reports/layout-fallback-review.json'
 if not path.exists():return None
 for rec in reversed(read(path)):
  if rec.get('document_id')!=did or rec.get('source_snapshot')!=source_snap(m,c) or rec.get('severity')!='severe' or not rec.get('adjustments_exhausted'):continue
  rp=safe(root,rec.get('evidence_report','reports/render-attempts.json'))
  if not rp.exists() or sha(rp)!=rec.get('render_report_sha256'):continue
  if not rec.get('artifacts') or any(not safe(root,f).exists() or sha(safe(root,f))!=hh for f,hh in rec['artifacts'].items()):continue
  return rec
 return None

def plan(root,m,c,overrides=None):
 conf=m.get('layout',{});threshold=conf.get('confidence_threshold',.72);allplans=[];profiles={};reference=conf.get('reference');refprofile=None
 if reference:
  fp=safe(root,reference['file'])
  if sha(fp)!=reference['sha256']:raise ValueError('Reference layout changed; configure again.')
  refprofile=profile(fp)
 for s in c['sources']:
  scope=s.get('selection_scope');selected_pages=scope.get('pages') if isinstance(scope,dict) else None
  p=dict(refprofile or profile(safe(root,s['file']),selected_pages))
  from structure_layout import read_map
  parsed=read_map(root,s,c)
  if parsed:
   p['parser_layout']={'file':s['layout_ir']['file'],'sha256':s['layout_ir']['sha256'],'pages':parsed['pages'],'review_status':parsed['review_status']}
   votes=Counter(page['columns'] for page in parsed['pages'] if page.get('columns'))
   if votes and not refprofile:
    proposed=votes.most_common(1)[0][0]
    # One observed prose band is insufficient to erase independently measured
    # multi-column geometry (e.g. a figure-heavy page with one paragraph per
    # side). Two or three parser bands remain positive column evidence.
    if proposed>1 or p.get('columns',1)==1:p['columns']=proposed
    p['features']={**p['features'],'columns':p['columns']}
   p['evidence']=p['evidence']+['Hash-bound parser output: ordered blocks, roles, typography, columns, figures and caption candidates; proposals require source review']
  profiles[s['id']]=p;ranking=rank_templates(p.get('features',{}),conf.get('template') if conf.get('policy')=='template' else None);reason=[];route='source';design=source_design(p);rejection=valid_rejection(root,m,c,s['id']);selected=None
  if conf.get('policy','source-first')=='template':selected=conf.get('template') or ranking[0]['template'];reason.append('User explicitly requested template mode.')
  elif rejection:selected=ranking[0]['template'];reason.append('Severe visual defect remains after source-design adjustment; current visual review authorizes fallback: '+rejection['reason'])
  else:
   reason.append('Source-first: render and adjust the inherited design before any fallback. Low feature confidence requests closer inspection, never authorizes fallback.')
   if p['feature_confidence']<threshold:reason.append('Low evidence score: inspect/recover geometry before judging layout; measurements are provisional.')
  if selected:
   design=next(dict(t) for t in catalog() if t['id']==selected);route='template';reason.append('Selected highest heuristic feature-fit rank (or explicit user choice). Preserve every source unit. Render and adjust this candidate before considering the next ranked candidate.')
  override=conf.get('presentation',{}).get('documents',{}).get(s['id'],{})
  __import__('refinement').design_patch(override);design.update(override)
  allplans.append({'document_id':s['id'],'route':route,'design':design,'source_confidence':p['feature_confidence'],'threshold':threshold,'ranking':ranking,'reasons':reason,'fallback_review':rejection,'reference':reference['name'] if reference else s['name']})
 return {'schema_version':'1.0.2','snapshot':snap(m,c),'policy':conf.get('policy','source-first'),'decision_order':['profile source','render source','adjust source and rerender','visual review: severe and unadjustable?','rank fallback templates','render/adjust/review nearest compatible candidate'],'scores_are':'Heuristic feature/fit scores, not statistically calibrated probabilities or aesthetic correctness','profiles':profiles,'documents':allplans,'visual_review_required':True,'automatic_template_switching':False}

def design_css(plan):
 out=[]
 for d in plan['documents']:
  ident=d['document_id'];x=d['design'];w,h=x['page_mm'];mx=x['margin_x_mm'];my=x['margin_y_mm'];font={"sans":'"Noto Sans","Arial Unicode MS","Arial",sans-serif',"mono":'"Noto Sans Mono","Courier New",monospace',"serif":'"Noto Serif","Noto Serif CJK SC","Songti SC","Noto Naskh Arabic","Times New Roman",serif'}[x["font"]];vars=f'--page-width:{w}mm;--page-height:{h}mm;--margin-x:{mx}mm;--margin-y:{my}mm;--body-size:{x["body_pt"]}pt;--body-leading:{x["line_height"]};--accent:{x["accent"]};--column-count:{x["columns"]};--heading-ratio:{x.get("heading_ratio",1.65)};font-family:{font};'
  out.append('[data-layout-doc="'+ident+'"]{'+vars+'} @page layout-'+ident+'{size:'+str(w)+'mm '+str(h)+'mm;margin:0}.sheet[data-layout-doc="'+ident+'"]{page:layout-'+ident+'}')
  if d['route']=='source' and not x.get('heading_rule'):out.append('[data-layout-doc="'+ident+'"] h2{border-bottom:0}')
 return '\n'.join(out)

def freshness(root,m,c):
 p=Path(root)/'reports/layout-plan.json'
 if not p.exists():return False,'Missing layout-plan report'
 old=read(p)
 if old.get('snapshot')!=snap(m,c):return False,'Layout-plan snapshot is stale'
 try:
  for s in c['sources']:
   ref=m.get('layout',{}).get('reference');file=safe(root,ref['file'] if ref else s['file'])
   if sha(file)!=old['profiles'][s['id']]['source_sha256']:return False,'Profiled input/reference changed'
 except (KeyError,ValueError,FileNotFoundError):return False,'Layout evidence invalid'
 return True,'Current source-layout evidence'
