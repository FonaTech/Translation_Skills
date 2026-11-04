"""Prepare explicit review checklists; blank attestations never count as reviews."""
import argparse,sys
from pathlib import Path
from translate import project,write,snap,safe,sha,units
from refinement import check_manifest

def create(project_path,kind,output):
 import layout_engine
 r,m,c=project(project_path);record={'schema_version':'1.0.1','kind':kind,'snapshot':snap(m,c),'reviewer':'','summary':'Complete after inspecting every enumerated item; this checklist is not itself evidence.','findings':[]}
 if kind=='semantic':
  record['editions']=list(m['editions']);record['unit_reviews']=[{'unit_id':u['id'],'faithful':'pending','interpretive':'pending','observation':''} for _,u in units(c)]
 elif kind=='extraction':
  record['block_reviews']=[{'block_id':b['id'],'status':'pending','observation':''} for b in c['blocks']]
 else:
  report=r/'reports/layout.json'
  if not report.exists():raise ValueError('Build and render all editions before preparing visual evidence.')
  layout=__import__('translate').read(report)
  if layout.get('snapshot')!=snap(m,c):raise ValueError('Render current content before reviewing.')
  record['pages']=[]
  for out in layout['outputs']:
   for i,page in enumerate(out['layout']['pages'],1):
    f=f'reports/pages/{Path(out["pdf"]).stem}/page-{i:04d}.png';record['pages'].append({'pdf':out['pdf'],'page':i,'source_pages':page.get('source_pages',[]),'block_ids':page.get('block_ids',[]),'preview':f,'sha256':sha(safe(r,f)),'observation':''})
  record['source_evidence']=[]
  for source in c['sources']:
   fp=safe(r,source['file'])
   if fp.suffix.lower()=='.pdf':
    profile=layout['outputs'][0]['layout']['pages'];selected=set()
    for page in profile:
     selected.update(page.get('source_pages',[]))
    # Explicit project scope is authoritative; full source can be lengthy.
    scope=source.get('selection_scope')
    numbers=scope.get('pages',[]) if isinstance(scope,dict) else sorted(int(x) for x in selected if str(x).isdigit())
    for n in numbers:
     rel=f'previews/{source["id"]}-p{int(n):04d}.png';img=safe(r,rel)
     if not img.exists():raise ValueError('Missing source preview; inspect/recreate '+rel)
     record['source_evidence'].append({'file':rel,'page':int(n),'sha256':sha(img),'observation':''})
  if not record['source_evidence']:raise ValueError('Visual review requires project-local source page previews.')
 path=Path(output);write(path,record)
 count=len(record.get('unit_reviews',record.get('block_reviews',record.get('pages',[]))))
 print(f'Checklist created with {count} entries. Fill it only after actual inspection: {path}')

def main():
 p=argparse.ArgumentParser();p.add_argument('project');p.add_argument('--kind',choices=['extraction','semantic','visual'],required=True);p.add_argument('--output',required=True);a=p.parse_args()
 try:create(a.project,a.kind,a.output)
 except (ValueError,KeyError,FileNotFoundError) as e:print(str(e),file=sys.stderr);return 1
 return 0
if __name__=='__main__':sys.exit(main())
