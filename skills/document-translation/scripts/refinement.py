"""Validated presentation patches and page-evidenced agent review. No model API."""
import copy
from translate import project,read,write,safe,sha,snap,source_snap,now,units
NUMERIC={'columns':(1,3),'body_pt':(8,24),'line_height':(1.15,2.5),'margin_x_mm':(6,50),'margin_y_mm':(8,50),'column_gap_mm':(3,20),'paragraph_gap_mm':(.5,10),'heading_gap_mm':(1,15),'table_pt':(6,18),'cell_padding_mm':(.3,5),'title_pt':(12,40),'caption_pt':(6,18),'heading_ratio':(1.1,3)}
ROLES={'body','metadata','bibliography','abstract','keywords','caption','equation','note'}
def design_patch(p):
 if not isinstance(p,dict):raise ValueError('Presentation override must be an object.')
 for k,v in p.items():
  if k in NUMERIC:
   low,high=NUMERIC[k]
   if isinstance(v,bool) or not isinstance(v,(float,int)) or not low<=v<=high:raise ValueError('Out-of-range design value: '+k)
   if k=='columns' and int(v)!=v:raise ValueError('Columns must be an integer.')
  elif k=='font':
   if v not in {'serif','sans','mono'}:raise ValueError('Unknown font family.')
  elif k=='accent':
   import re
   if not isinstance(v,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',v):raise ValueError('Accent requires #RRGGBB.')
  elif k=='page_mm':
   if not isinstance(v,list) or len(v)!=2 or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not 100<=x<=600 for x in v):raise ValueError('Page dimensions require two values in 100..600 mm.')
  elif k=='heading_rule':
   if not isinstance(v,bool):raise ValueError('heading_rule must be boolean.')
  else:raise ValueError('Unsupported presentation key: '+k)
 return p

def validate_blocks(c):
 errors=[];lookup={b['id']:b for b in c['blocks']};used={}
 for b in c['blocks']:
  p=b.get('presentation',{})
  if set(p)-{'role','span','keep_next'} or p.get('role','body') not in ROLES or p.get('span','auto') not in {'auto','all','column'} or not isinstance(p.get('keep_next',False),bool):errors.append({'code':'invalid-block-presentation','block':b['id']})
  refs=b.get('caption_block_ids',[])
  if not isinstance(refs,list) or refs and b['type'] not in {'image','equation','table'}:errors.append({'code':'invalid-caption-binding','block':b['id']});continue
  for cid in refs:
   cb=lookup.get(cid)
   if cb is None or cb['type'] not in {'paragraph','heading'} or cb.get('caption_block_ids') or cb['source']['document_id']!=b['source']['document_id'] or (cb['source'].get('page') and b['source'].get('page') and cb['source']['page']!=b['source']['page']):errors.append({'code':'invalid-caption-reference','block':b['id'],'caption':cid})
   if cid in used and not (b.get('figure_group_id')==cid and lookup[used[cid]].get('figure_group_id')==cid):errors.append({'code':'duplicate-caption-binding','block':b['id'],'caption':cid})
   used[cid]=b['id']
 return errors

def apply_patch(a):
 r,m,c=project(a.project);packet=read(a.patch)
 if not packet.get('reason','').strip():raise ValueError('Explain the observed layout problem and expected improvement.')
 evidence={}
 for f in packet.get('evidence',[]):
  path=safe(r,f)
  if not path.is_file():raise ValueError('Missing visual evidence: '+f)
  evidence[f]=sha(path)
 if not evidence:raise ValueError('A refinement needs source or rendered evidence paths.')
 if set(packet)-{'reason','evidence','documents','blocks'}:raise ValueError('Refinement accepts presentation only; translate content through apply.')
 before=snap(m,c);src=source_snap(m,c);m=copy.deepcopy(m);c=copy.deepcopy(c)
 docs={s['id'] for s in c['sources']};blocks={b['id']:b for b in c['blocks']}
 for did,p in packet.get('documents',{}).items():
  if did not in docs:raise ValueError('Unknown document: '+did)
  design_patch(p);m.setdefault('layout',{}).setdefault('presentation',{}).setdefault('documents',{}).setdefault(did,{}).update(p)
 for bid,p in packet.get('blocks',{}).items():
  if bid not in blocks or set(p)-{'presentation','width_mm','caption_block_ids'}:raise ValueError('Unsupported block patch: '+bid)
  if 'width_mm' in p and (not isinstance(p['width_mm'],(int,float)) or not 10<=p['width_mm']<=500):raise ValueError('Image width must be 10..500 mm.')
  for k,v in p.items():
   if k=='presentation':blocks[bid].setdefault(k,{}).update(v)
   else:blocks[bid][k]=v
 errors=validate_blocks(c)
 if errors:raise ValueError(str(errors))
 assert source_snap(m,c)==src,'Presentation patch changed source semantics'
 write(r/'project.json',m);write(r/'content.json',c)
 log=r/'reports/refinements.json';rows=read(log) if log.exists() else []
 rows.append({'at':now(),'before_snapshot':before,'after_snapshot':snap(m,c),'source_hash':src,'patch':packet,'evidence':evidence,'translation_changed':False});write(log,rows)
 print('Applied presentation-only refinement; rebuild, rerender and inspect changed pages.')

def check_manifest(r,m,c,kind,data):
 if not isinstance(data,dict) or data.get('snapshot')!=snap(m,c):raise ValueError('Review evidence snapshot is absent or stale.')
 if not data.get('reviewer','').strip() or not data.get('summary','').strip():raise ValueError('Review evidence needs a reviewer and substantive summary.')
 findings=data.get('findings',[])
 for f in findings:
  if not f.get('observation') or f.get('status') not in {'resolved','accepted','open'}:raise ValueError('Each finding needs an observation and status.')
  if f['status']=='open' and f.get('severity','major') in {'major','critical'}:raise ValueError('Unresolved consequential finding blocks release.')
  if f['status']=='resolved' and not f.get('resolution'):raise ValueError('Resolved finding needs its actual correction.')
 if kind in {'semantic','extraction'}:
  expected={u['id'] for _,u in units(c)} if kind=='semantic' else {b['id'] for b in c['blocks']}
  key='unit_id' if kind=='semantic' else 'block_id';field='unit_reviews' if kind=='semantic' else 'block_reviews';records=data.get(field,[]);seen=[x.get(key) for x in records]
  if len(seen)!=len(set(seen)) or set(seen)!=expected:raise ValueError('Review coverage must enumerate current '+key+' exactly.')
  if kind=='semantic':
   if set(data.get('editions',[]))!=set(m['editions']):raise ValueError('Review must cover both editions.')
   for rec in records:
    if any(not isinstance(rec.get(ed),str) or not rec[ed].strip() or rec[ed]=='pending' for ed in m['editions']) or not rec.get('observation','').strip():raise ValueError('Every source unit needs an observed review of both editions: '+str(rec.get(key)))
  elif any(x.get('status') not in {'checked','exception'} or not x.get('observation','').strip() for x in records):raise ValueError('Every source block needs an extraction/structure observation.')
  return {}
 report=read(r/'reports/layout.json');expected={(out['pdf'],i) for out in report['outputs'] for i in range(1,out['pages']+1)};seen=[];artifacts={}
 for rec in data.get('pages',[]):
  key=(rec.get('pdf'),rec.get('page'));seen.append(key)
  if not rec.get('observation','').strip():raise ValueError('Every inspected output page needs an observation.')
  f=rec.get('preview');fp=safe(r,f)
  if not fp.is_file() or sha(fp)!=rec.get('sha256'):raise ValueError('Inspected page image changed or missing: '+str(f))
  expected_path='reports/pages/'+str(rec.get('pdf','')).removesuffix('.pdf')+'/page-'+str(rec.get('page',0)).zfill(4)+'.png'
  if f!=expected_path:raise ValueError('Preview is not the rendered PDF page for this entry.')
  artifacts[f]=sha(fp)
  if rec.get('structural_status') not in {'pass','adjusted','accepted-exception'}:raise ValueError('Each output page needs a visual-layout disposition.')
  if rec['structural_status']=='adjusted' and not rec.get('resolution','').strip():raise ValueError('Page adjustment needs its actual change.')
 if len(seen)!=len(set(seen)) or set(seen)!=expected:raise ValueError('Visual review must enumerate every delivered PDF page exactly.')
 sources=data.get('source_evidence',[])
 if not sources:raise ValueError('Visual review needs inspected source previews or native source files.')
 for rec in sources:
  f=rec['file'];fp=safe(r,f)
  if not fp.is_file() or sha(fp)!=rec.get('sha256') or not rec.get('observation','').strip():raise ValueError('Source comparison evidence invalid.')
  artifacts[f]=sha(fp)
 return artifacts
