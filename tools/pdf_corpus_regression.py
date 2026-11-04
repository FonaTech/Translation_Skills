#!/usr/bin/env python3
"""Prepare seeded translation tasks; check real completed projects without filling translations."""
import argparse,contextlib,io,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import translate as t,publishing

def prepare(a):
 import fitz
 src=Path(a.pdf_root).expanduser().resolve();out=Path(a.output_root).expanduser().resolve()
 if not src.is_dir() or out.is_relative_to(ROOT):raise ValueError('Use an existing corpus and projects outside the repository.')
 if out.exists() and any(out.iterdir()):raise ValueError('Choose a fresh directory; existing projects are preserved.')
 files=sorted((p for p in src.rglob('*') if p.is_file() and p.suffix.lower()=='.pdf'),key=lambda p:p.relative_to(src).as_posix())
 if not 0<a.count<=len(files):raise ValueError('Count must be positive and no greater than the PDF population.')
 samples=[]
 for i,file in enumerate(random.Random(a.seed).sample(files,a.count),1):
  with fitz.open(file) as doc:pages=sorted({1,max(1,(len(doc)+1)//2)});count=len(doc)
  project=out/f'sample-{i:02d}'
  with contextlib.redirect_stdout(io.StringIO()):
   t.init(argparse.Namespace(project=str(project),title=file.stem,languages=a.language,style='editorial',page_size='A4',columns=1))
   t.ingest(argparse.Namespace(project=str(project),files=[str(file)],pages=','.join(map(str,pages)),password=None,order='auto',tables=False))
   t.tasks(argparse.Namespace(project=str(project),language=a.language,size=30,all=True))
  samples.append({'sample':i,'project':project.name,'source_sha256':t.sha(file),'source_filename':file.name,'source_relative_path':file.relative_to(src).as_posix(),'source_page_count':count,'selected_pages':pages})
 t.write(out/'selection.json',{'seed':a.seed,'pdf_count':len(files),'language':a.language,'sampling':'Random(seed).sample of sorted relative PDF paths','middle_page_rule':'one-based lower midpoint: floor((page_count + 1) / 2)','samples':samples,'semantic_translation_complete':False,'next':'Current agent: inspect extraction, repair, regenerate tasks, translate both editions, apply real packets, review meaning, build/render, inspect pages, record reviews, release, then check. No model service is required.'})
 print(json.dumps({'prepared':len(samples),'selected_pages':sum(len(s['selected_pages']) for s in samples),'semantic_translation_complete':False,'status':'AWAITING_CURRENT_AGENT_TRANSLATION'}));return 0

def visual_metrics(page):
 import fitz
 pix=page.get_pixmap(matrix=fitz.Matrix(.5,.5),colorspace=fitz.csGRAY,alpha=False)
 return {'visually_empty':publishing.page_is_visually_empty(page),'ink_pixel_ratio':round(sum(v<245 for v in pix.samples)/max(1,pix.width*pix.height),6)}

def check(a):
 import fitz
 out=Path(a.output_root).expanduser().resolve();manifest=t.read(out/'selection.json');results=[]
 for sample in manifest['samples']:
  root,meta,content=t.project(out/sample['project']);audit=t.audit_data(root,meta,content);errors=list(audit['errors']);source=content['sources'][0]
  if source['sha256']!=sample['source_sha256'] or source.get('selection_scope')!={'pages':sample['selected_pages']}:errors.append({'code':'sample-source-or-scope-changed'})
  logs=root/'reports/translation-applications.json';applications=t.read(logs) if logs.exists() else [];ids={u['id'] for _,u in t.units(content)}
  applied={uid for rec in applications if rec['source_hash']==t.source_snap(meta,content) for uid in rec['unit_ids']}
  if not ids or not ids<=applied:errors.append({'code':'real-packet-coverage-missing','missing':sorted(ids-applied)})
  with contextlib.redirect_stdout(io.StringIO()):code=t.release(argparse.Namespace(project=str(root),zip=None))
  if code:errors+=t.read(root/'reports/release.json')['errors']
  generated=[]
  for lang in meta['target_languages']:
   for edition in meta['editions']+['alignment']:
    pdf=root/'outputs'/f'{lang}-{edition}.pdf'
    if not pdf.exists():continue
    with fitz.open(pdf) as doc:metrics=[visual_metrics(p) for p in doc]
    if not metrics or any(x['visually_empty'] for x in metrics):errors.append({'code':'empty-output-page','file':pdf.name})
    generated.append({'file':pdf.name,'sha256':t.sha(pdf),'pages':len(metrics),'page_metrics':metrics})
  results.append({**sample,'units':len(ids),'applied_units':len(ids&applied),'outputs':generated,'errors':errors,'pass':not errors})
 report={'version':(ROOT/'VERSION').read_text().strip(),'seed':manifest['seed'],'pdf_count':manifest['pdf_count'],'sampled_pages':sum(len(s['selected_pages']) for s in results),'translation_provider':'current invoking agent; no automatic service','pass':bool(results) and all(s['pass'] for s in results),'samples':results,'limits':'Reviews represent the named reviewer. Mechanical checks cannot certify semantic accuracy.'}
 t.write(out/'regression-report.json',report);print(json.dumps({'pass':report['pass'],'samples':len(results),'sampled_pages':report['sampled_pages'],'failed_samples':[s['sample'] for s in results if not s['pass']]},indent=2));return 0 if report['pass'] else 1

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 q=sub.add_parser('prepare');q.add_argument('--pdf-root',required=True);q.add_argument('--output-root',required=True);q.add_argument('--seed',type=int,default=173);q.add_argument('--count',type=int,default=8);q.add_argument('--language',default='zh-Hans');q.set_defaults(fn=prepare)
 q=sub.add_parser('check');q.add_argument('--output-root',required=True);q.set_defaults(fn=check);a=p.parse_args();return a.fn(a)
if __name__=='__main__':
 try:sys.exit(main())
 except (OSError,ValueError) as error:print('ERROR: '+str(error),file=sys.stderr);sys.exit(2)
