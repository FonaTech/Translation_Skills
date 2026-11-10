#!/usr/bin/env python3
"""Prepare private source-only PDF evidence, without loading any learned model.

Copyright 2026 Yufeng Zhan. MIT. Input document rights remain with their owners.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import source_structure as structure
from structure_annotation_contract import source_identities


def parse_page_spec(value):
    pages=set()
    for part in value.split(','):
        bounds=part.strip().split('-',1)
        try:
            start=int(bounds[0]);end=int(bounds[-1])
        except ValueError as exc:
            raise ValueError('Page selection must use positive numbers and ranges, e.g. 4,8-10.') from exc
        if start<1 or end<start:raise ValueError('Page selection must use ascending positive page numbers.')
        pages.update(range(start,end+1))
    return sorted(pages)


def prepare(files,output,split='test',dpi=108,source_parent_sha256=None,page_numbers=None):
    import fitz
    output=Path(output).resolve()
    if output.exists():raise FileExistsError('Preserve existing evidence; select a new directory.')
    if split not in {'train','validation','test'}:raise ValueError('Invalid whole-source split.')
    if not 72<=dpi<=300:raise ValueError('Evidence DPI must be between 72 and 300.')
    parents=list(source_parent_sha256 or [])
    source_identities({'source_parent_sha256':parents})
    if parents and len(files)!=1:raise ValueError('Record derived-copy parents for one source at a time.')
    sources=[];seen=set()
    for name in files:
        path=Path(name).expanduser().resolve()
        identity=hashlib.sha256(path.read_bytes()).hexdigest()
        if identity in seen:raise ValueError('Repeated source identity: '+path.name)
        seen.add(identity);sources.append((path,identity))
    if not sources:raise ValueError('Select at least one source PDF.')
    if page_numbers is not None and len(sources)!=1:
        raise ValueError('Page selection is supported for exactly one source PDF per run.')
    output.mkdir(parents=True);(output/'pages').mkdir();documents=[];gallery=[];ledger=[]
    for path,identity in sources:
        source_id=path.stem+'-'+identity[:12]
        with fitz.open(path) as pdf:
            if pdf.needs_pass:raise ValueError('Unlock an authorized copy before annotation: '+path.name)
            source_page_count=len(pdf)
            selected=set(page_numbers) if page_numbers is not None else None
            if selected and max(selected)>len(pdf):raise ValueError('Selected page exceeds source page count: '+path.name)
            pages=[structure.raw_page(page,detect_tables=True) for page in pdf
                   if selected is None or page.number+1 in selected]
            if not pages:raise ValueError('Page selection is empty.')
            profile_pages=[structure.raw_page(page,detect_tables=True) for page in pdf] if selected is not None else pages
            profile=structure.document_profile(profile_pages)
            for page in pages:
                number=page['page'];image=output/'pages'/f'{identity[:16]}-p{number:04d}.png'
                pdf[number-1].get_pixmap(matrix=fitz.Matrix(dpi/72,dpi/72),alpha=False).save(image)
                page['source_image']=str(image)
                gallery.append('<article><h2>'+html.escape(path.name)+' · '+str(number)+'</h2><img loading="lazy" src="'+image.relative_to(output).as_posix()+'" alt="Original source page"><details><summary>Native rows / 原生文本行</summary><pre>'+html.escape('\n'.join(r['id']+' '+r['text'] for r in page['lines']))+'</pre></details></article>')
                for row in page['lines']:
                    ledger.append({'document':source_id,'page':number,**{k:row[k] for k in ['id','text','bbox','font','size','native_line_ids']}})
        documents.append({'id':source_id,'source_file':str(path),'source_sha256':identity,
            **({'source_parent_sha256':parents} if parents else {}),
            'source_page_count':source_page_count,'split':split,'pages':pages,
            'profile':profile,'label_source':'pending source-only inspection',
            'content_structure_metrics':{}})
    data={'version':'1.0.3','extraction_revision':structure.EXTRACTION_REVISION,
          'feature_revision':structure.FEATURE_REVISION,'annotation_protocol':'Unlabeled source evidence. Author roles, paragraph groups, spatial reading regions and unresolved flags from complete source inspection before opening predictions. No trained model loaded.',
          'documents':documents}
    (output/'unlabeled.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'rows.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in ledger),encoding='utf-8')
    (output/'source-evidence.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Source-only annotation evidence</title><style>body{font:16px system-ui;background:#eef1f4;color:#142333;margin:0;padding:24px}article{max-width:1050px;margin:24px auto;background:white;padding:20px}img{max-width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}h2{font-size:18px;overflow-wrap:anywhere}</style><h1>Source-only evidence / 原文标注素材</h1><p>No predictions or review completion are generated. Document rights remain with their owners.</p>'+''.join(gallery),encoding='utf-8')
    return {'documents':len(documents),'pages':sum(len(d['pages']) for d in documents),
            'annotations':str(output/'unlabeled.json'),'predictions_generated':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files',nargs='+',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--split',choices=['train','validation','test'],default='test')
    parser.add_argument('--dpi',type=int,default=108)
    parser.add_argument('--pages',help='Optional 1-based page list/ranges for one PDF, e.g. 4,8-10. Remaining pages are not rendered.')
    parser.add_argument('--source-parent-sha256',action='append',default=[],help='Original and ancestor identities of a repaired, OCR or converted copy; repeat as needed.')
    args=parser.parse_args();selected=parse_page_spec(args.pages) if args.pages else None
    print(json.dumps(prepare(args.files,args.output,args.split,args.dpi,args.source_parent_sha256,selected)))


if __name__=='__main__':
    from cli_encoding import configure_utf8
    configure_utf8()
    main()
