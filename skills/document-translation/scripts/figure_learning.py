"""Portable source-caption and artwork association heads. Copyright Yufeng Zhan. MIT.
Scores are model outputs, never calibrated guarantees. Native text is not completed.
"""
from pathlib import Path
import json,math,re
MODEL_PATH=Path(__file__).resolve().parents[1]/'assets/models/figure-binding.json'
PREFIX=re.compile(r'^\s*(?:(?:supplementary\s+)?(?:fig(?:ure)?s?\.?|table|plate|f\s*i\s*g\s*u\s*r\s*e|t\s*a\s*b\s*l\s*e)\s*[A-Z]?(?:\d+(?:\.\d+)*|[IVX]+)|[图圖図表]\s*\d+|(?:abbildung|abb\.|figura|рис\.)\s*\d+)',re.I)
REFERENCE=re.compile(r'^\s*(?:fig(?:ure)?s?\.?|table|plate)\s*[A-Z]?(?:\d+(?:\.\d+)*|[IVX]+)[a-z]?(?:\s*\([a-z]\))?\s*(?:shows?|illustrates?|demonstrates?|depicts?|presents?|underscores?|indicates?|summarizes?|reports?|compares?|is|was|are|were|for\s+details?\b|in\s+(?:the|section)\b)',re.I)
CAPTION_FEATURES=['prefix','narrative_reference','block_prefix','block_reference','block_position','size_body_log','block_size_range','bold','italic','sans','log_length','letters','digits','width','height','left','top','right','bottom','direction_y','prev_gap','next_gap','block_log_lines','block_width','block_height','same_font_block','prefix_before','reference_before','font_size_delta','table_word','graphic_gap_above','graphic_gap_below','graphic_overlap','panel_start','terminal','starts_lower','spatial_caption_chain','chain_steps','spatial_reference_chain']
LINK_FEATURES=['gap_below','gap_above','overlap','center_delta','width_ratio','height','width','top','bottom','caption_top','caption_bottom','caption_width','is_below','is_above','blockers','header_art','caption_header','distance','raster','vector','horizontal_separation','contains_caption','caption_number','caption_is_table']
_cache=None
_cache_signature=None
def _validate_head(head, inputs):
 dims=head.get('dimensions',[])
 if len(dims)!=3 or dims[0]!=inputs or dims[2]!=2 or not isinstance(dims[1],int) or not 1<=dims[1]<=4096 or head.get('activation')!='tanh':raise ValueError('Invalid figure model dimensions or activation')
 hidden=dims[1]
 for name,length in [('mean',inputs),('scale',inputs),('bias',hidden),('output_bias',2)]:
  row=head.get(name,[])
  if len(row)!=length or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in row):raise ValueError('Invalid figure model vector: '+name)
 if any(x<=0 for x in head['scale']):raise ValueError('Invalid figure model scale')
 for name,rows,cols in [('weights',inputs,hidden),('output',hidden,2)]:
  matrix=head.get(name,[])
  if len(matrix)!=rows or any(len(row)!=cols or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in row) for row in matrix):raise ValueError('Invalid figure model matrix: '+name)
def load_model():
 global _cache,_cache_signature
 if not MODEL_PATH.is_file():return None
 stat=MODEL_PATH.stat();signature=(str(MODEL_PATH.resolve()),stat.st_mtime_ns,stat.st_size)
 if _cache is None or signature!=_cache_signature:
  data=json.loads(MODEL_PATH.read_text( encoding='utf-8'));
  if data.get('caption_features')!=CAPTION_FEATURES or data.get('link_features')!=LINK_FEATURES:raise ValueError('Figure model feature contract mismatch')
  _validate_head(data.get('caption_head',{}),len(CAPTION_FEATURES));_validate_head(data.get('link_head',{}),len(LINK_FEATURES))
  if any(not isinstance(data.get(k),(int,float)) or not math.isfinite(data[k]) or not 0<data[k]<1 for k in ['caption_threshold','link_threshold']):raise ValueError('Invalid figure model threshold')
  _cache=data;_cache_signature=signature
 return _cache
def union(boxes):return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
def font_family(line):
 name=re.sub(r'^[A-Z]{6}\+','',line.get('font','')).lower()
 return re.sub(r'(?:bold|italic|oblique|regular|roman|psmt|mt|ps|[-_ ,])','',name)
def baseline(line):
 if __package__:
     from .source_structure import text_baseline
 else:
     from source_structure import text_baseline
 return text_baseline(line) if line.get('spans') else line['bbox'][3]
def section_boundary(text):
 return bool(re.match(r'^\s*(?:(?:acknowledg(?:e)?ments?|references|bibliography|literature cited|conclusions?|abstract|keywords|致谢|致謝|参考文献|參考文獻|参考文献)\s*(?::|：|$)|\[\d+\]\s*[A-Z])',text,re.I))
def continuation(previous,current):
 a=previous['bbox'];b=current['bbox'];size=max(.1,current['size']);gap=b[1]-a[3]
 if previous['id']==current['id'] or not any(c.isalnum() for c in current['text']):return False
 if PREFIX.match(current['text']) or section_boundary(current['text']):return False
 # Font ascent/descent boxes overlap in perfectly ordinary typesetting. The
 # writing baseline, rather than the box gap, defines a physical next row.
 step=baseline(current)-baseline(previous)
 if not .35*size<=step<=2.25*size:return False
 # A blank paragraph gap remains a boundary even when prose starts lowercase.
 if previous['native_block']!=current['native_block'] and gap>.70*size:return False
 table_title=bool(re.match(r'^\s*(?:table|表)\s*(?:[IVX]+|\d+)\s*$',previous['text'],re.I) and current['text'].strip().isupper() and .72<=size/max(.1,previous['size'])<=1)
 if abs(math.log(max(.1,previous['size'])/size))>.075 and not table_title:return False
 if font_family(previous)!=font_family(current):return False
 overlap=max(0,min(a[2],b[2])-max(a[0],b[0]))/max(1,min(a[2]-a[0],b[2]-b[0]))
 shaped_tail=(previous['native_block']==current['native_block'] and abs(a[2]-b[2])<size*2 and overlap>.65)
 if abs(a[0]-b[0])>=size*2 and abs((a[0]+a[2]-b[0]-b[2])/2)>=size*3 and not shaped_tail:return False
 if previous['native_block']!=current['native_block'] and (b[2]-b[0])>max(1,a[2]-a[0])*1.7:return False
 if previous['native_block']!=current['native_block'] and re.search(r'[.!?。]\s*$',previous['text']) and gap>size*.35 and not (current['text'].lstrip().startswith('(') or current['text'].lstrip()[:1].islower()):return False
 return True
def caption_column_continuations(page,accepted):
 # A caption can flow down a left column then restart on the right at the
 # same top baseline. Require matching font/size and an unfinished left tail;
 # never cross an independent numbered caption or an ordinary paragraph gap.
 lines=page['lines'];result=[]
 for anchor in lines:
  if anchor['id'] not in accepted or not PREFIX.match(anchor['text']) or REFERENCE.match(anchor['text']):continue
  left=[anchor]
  for row in sorted(lines,key=baseline):
   if row['id'] in accepted and continuation(left[-1],row):left.append(row)
  if re.search(r'[.!?。]\s*$',left[-1]['text']):continue
  bb=union([x['bbox'] for x in left]);size=max(1,anchor['size'])
  starts=[r for r in lines if not PREFIX.match(r['text']) and not section_boundary(r['text']) and
   r['bbox'][0]>=bb[2]+size*.8 and r['bbox'][0]-bb[2]<page['width']*.12 and
   abs(baseline(r)-baseline(anchor))<size*.5 and abs(math.log(max(.1,r['size'])/size))<.075 and
   font_family(r)==font_family(anchor) and len(r['text'].strip())>30]
  if not starts:continue
  chain=[min(starts,key=lambda r:r['bbox'][0])]
  for row in sorted(lines,key=baseline):
   if row not in chain and continuation(chain[-1],row) and row['bbox'][3]<=bb[3]+size*.6:chain.append(row)
  result.append((left,chain))
 return result
def caption_features(line,page,profile):
 text=line['text'].strip();b=line['bbox'];w=page['width'];h=page['height'];size=max(.1,line['size']);lines=[x for x in page['lines'] if x['text'].strip()]
 peers=[x for x in lines if x['native_block']==line['native_block']] or [line];peers.sort(key=lambda x:(x['bbox'][1],x['bbox'][0]));pos=next(i for i,x in enumerate(peers) if x['id']==line['id']);pb=union([x['bbox'] for x in peers]);sizes=[x['size'] for x in peers]
 before=peers[:pos+1];anchor=next((x for x in peers if PREFIX.match(x['text'])),None)
 def compatible(x):return abs(x['bbox'][0]-b[0])<max(10,size*2) and abs(x['size']-size)<size*.22
 prev=[x for x in lines if x is not line and x['bbox'][3]<=b[1]+size*.2 and compatible(x)];nxt=[x for x in lines if x is not line and x['bbox'][1]>=b[3]-size*.2 and compatible(x)]
 pg=min((b[1]-x['bbox'][3] for x in prev),default=size*8)/size;ng=min((x['bbox'][1]-b[3] for x in nxt),default=size*8)/size
 graphics=page.get('graphic_regions',[]);over=[g for g in graphics if min(g[2],b[2])>max(g[0],b[0])]
 above=min((max(0,b[1]-g[3])/h for g in over if g[3]<=b[1]+2),default=1);below=min((max(0,g[1]-b[3])/h for g in over if g[1]>=b[3]-2),default=1)
 n=max(1,len(text));first=peers[0]['text'].strip();fonts=[re.sub(r'^[A-Z]{6}\+','',x['font']).lower() for x in peers];ft=re.sub(r'^[A-Z]{6}\+','',line['font']).lower()
 current=line;seen=set();chain=reference_chain=0;steps=0
 for depth in range(40):
  ct=current['text'].strip()
  if re.match(r'^\d{1,3}[A-Z][a-z]{2}',ct):break
  if PREFIX.match(ct):
   chain=int(not REFERENCE.match(ct));reference_chain=int(bool(REFERENCE.match(ct)));steps=depth;break
  cb=current['bbox'];cs=max(.1,current['size']);cx=(cb[0]+cb[2])/2
  earlier=[x for x in lines if x['id'] not in seen and continuation(x,current)]
  if not earlier:break
  current=max(earlier,key=baseline);seen.add(current['id'])
 return [float(bool(PREFIX.match(text))),float(bool(REFERENCE.match(text))),float(bool(PREFIX.match(first))),float(bool(REFERENCE.match(first))),pos/max(1,len(peers)-1),math.log(size/max(.1,profile['body_size'])),(max(sizes)-min(sizes))/size,float(bool(line.get('flags',0)&16)),float(bool(line.get('flags',0)&2)),float(any(x in ft for x in ['sans','helvetica','arial'])),math.log1p(n)/6,sum(c.isalpha() for c in text)/n,sum(c.isdigit() for c in text)/n,(b[2]-b[0])/w,(b[3]-b[1])/h,b[0]/w,b[1]/h,b[2]/w,b[3]/h,abs(line.get('direction',[1,0])[1]),min(8,pg),min(8,ng),math.log1p(len(peers))/4,(pb[2]-pb[0])/w,(pb[3]-pb[1])/h,fonts.count(ft)/len(fonts),float(any(PREFIX.match(x['text']) for x in before)),float(any(REFERENCE.match(x['text']) for x in before)),(size-anchor['size'])/size if anchor else 0,float(bool(re.match(r'^\s*(?:table|表)',text,re.I))),above,below,float(bool(over)),float(bool(re.match(r'^\s*\(?[a-z]\)',text))),float(bool(re.search(r'[.!?。]\s*$',text))),float(bool(text and text[0].islower())),chain,steps/40,reference_chain]
def link_features(box,caption,page,blocks=(),kind='vector-cluster'):
 b=box;c=caption['bbox'];w=page['width'];h=page['height'];bw=max(1,b[2]-b[0]);cw=max(1,c[2]-c[0]);over=max(0,min(b[2],c[2])-max(b[0],c[0]))/min(bw,cw)
 blockers=0
 for row in blocks:
  r=row['bbox'];txt=row.get('text','')
  if len(txt)>85 and not PREFIX.match(txt) and min(c[3],b[3])<=r[1] and r[3]<=max(c[1],b[1]) and min(r[2],b[2])>max(r[0],b[0]):blockers+=1
 text=caption.get('text','');gap=c[1]-b[3];up=b[1]-c[3]
 return [max(-1,min(1,gap/h)),max(-1,min(1,up/h)),over,abs((b[0]+b[2]-c[0]-c[2])/2)/w,math.log(bw/cw),max(0,b[3]-b[1])/h,bw/w,b[1]/h,b[3]/h,c[1]/h,c[3]/h,cw/w,float(gap>=-8),float(up>=-8),min(4,blockers)/4,float(b[3]<h*.08),float(c[1]<h*.10),min(abs(gap),abs(up))/h,float('raster' in kind),float('vector' in kind),max(0,c[0]-b[2],b[0]-c[2])/w,float(b[0]<=c[0] and b[1]<=c[1] and b[2]>=c[2] and b[3]>=c[3]),float(bool(PREFIX.match(text))),float(bool(re.match(r'^\s*(?:table|表)',text,re.I)))]
def predict(head,rows):
 if __package__:
     from .source_structure import predict_many
 else:
     from source_structure import predict_many
 return [p[1] for p in predict_many(head,rows)]
def caption_scores(page,profile,model=None):
 model=model or load_model()
 if model is None:return {}
 lines=[x for x in page['lines'] if x['text'].strip()]
 features=[caption_features(x,page,profile) for x in lines]
 scores=dict(zip([x['id'] for x in lines],predict(model['caption_head'],features)))
 for line,feat in zip(lines,features):
  bb=line['bbox'];cx=(bb[0]+bb[2])/2;cy=(bb[1]+bb[3])/2
  peers=[x for x in lines if x['native_block']==line['native_block']]
  first=min(peers,key=lambda x:(x['bbox'][1],x['bbox'][0]))
  if section_boundary(line['text']) or section_boundary(first['text']):scores[line['id']]=0;continue
  if REFERENCE.match(first['text']) or REFERENCE.match(line['text']):scores[line['id']]=0;continue
  if re.match(r'^\s*(?:fig(?:ure)?s?\.?)\s*\d+[a-z]?\s*\((?:sec(?:tion)?\.?|chapter)\s',first['text'],re.I):scores[line['id']]=0;continue
  if not any(c.isalnum() for c in line['text']):scores[line['id']]=0;continue
  if re.match(r'^\s*(?:fig(?:ure)?s?\.?)\s*\d+[a-z]?\s*\((?:sec(?:tion)?\.?|chapter)\s',line['text'],re.I):scores[line['id']]=0;continue
  table_inside=any(t[0]-.5<=cx<=t[2]+.5 and t[1]-.5<=cy<=t[3]+.5 for t in page.get('structure_regions',[])) or any(t['bbox'][0]-.5<=cx<=t['bbox'][2]+.5 and t['bbox'][1]-.5<=cy<=t['bbox'][3]+.5 for t in page.get('table_regions',[]))
  if table_inside and not PREFIX.match(line['text']):scores[line['id']]=0;continue
  if sum(c.isalpha() for c in line['text'])<3 or re.match(r'^\s*\d{1,3}[A-Z][a-z]{2}',line['text']):scores[line['id']]=min(scores[line['id']],.49)
  elif not PREFIX.match(line['text']) and not feat[CAPTION_FEATURES.index('spatial_caption_chain')] and scores[line['id']]<.9:scores[line['id']]=min(scores[line['id']],.49)
 # A compact classifier cannot treat each native PDF object as a paragraph.
 # Preserve a source-contiguous, typography-compatible caption after a learned
 # anchor, even when PDF serialization splits every row into another object.
 accepted={l['id'] for l in lines if scores[l['id']]>=model['caption_threshold'] and PREFIX.match(l['text'])}
 for _ in range(40):
  added=[]
  for line,feat in zip(lines,features):
   if line['id'] in accepted or scores[line['id']]==0:continue
   b=line['bbox'];size=max(.1,line['size']);cx=(b[0]+b[2])/2
   prev=[x for x in lines if x['id'] in accepted and continuation(x,line)]
   if prev:added.append(line['id'])
  if not added:break
  accepted.update(added)
 for left,right in caption_column_continuations(page,accepted):accepted.update(x['id'] for x in right)
 for lid in accepted:scores[lid]=max(scores[lid],model['caption_threshold'])
 return scores
def refine(page,profile,decisions):
 model=load_model()
 if model is None:return
 scores=caption_scores(page,profile,model);byid={x['line_id']:x for x in decisions}
 for lid,score in scores.items():
  row=byid.get(lid)
  if row is None:continue
  row['caption_model_score']=round(score,6)
  if score>=model['caption_threshold']:
   row.update(assigned_role='caption',semantic_role='caption',review_required=True,caption_model_id=model['id'])
  elif row['assigned_role']=='caption':
   row.update(assigned_role='body',semantic_role='body',review_required=True,caption_model_id=model['id'])
def caption_groups(page,decisions):
 lookup={x['line_id']:x for x in decisions};rows=[x for x in page['lines'] if lookup.get(x['id'],{}).get('assigned_role')=='caption'];groups=[]
 for row in sorted(rows,key=lambda x:(baseline(x),x['bbox'][0])):
  size=max(.1,row['size']);bb=row['bbox'];cx=(bb[0]+bb[2])/2
  compatible=[g for g in groups if not PREFIX.match(row['text']) and continuation(g['members'][-1],row)]
  if compatible:
   g=max(compatible,key=lambda g:(g['members'][-1]['native_block']==row['native_block'],baseline(g['members'][-1])));g['members'].append(row);g['bbox']=union([g['bbox'],bb])
  else:groups.append({'id':'caption-'+row['id'],'kind':'caption','representation':'source-caption','bbox':bb[:],'members':[row]})
 # Keep left-column and source-contiguous right-column caption text in one
 # ordered group instead of interleaving by y coordinate.
 accepted={x['id'] for x in rows}
 for left,right in caption_column_continuations(page,accepted):
  lids={x['id'] for x in left};rids={x['id'] for x in right}
  a=next((g for g in groups if lids.issubset({x['id'] for x in g['members']})),None)
  b=next((g for g in groups if rids.issubset({x['id'] for x in g['members']})),None)
  if a is not None and b is not None and a is not b:
   a['members'].extend(b['members']);a['bbox']=union([a['bbox'],b['bbox']]);groups.remove(b)
 return groups
