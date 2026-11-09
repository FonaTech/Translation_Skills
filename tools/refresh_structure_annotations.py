#!/usr/bin/env python3
"""Refresh source evidence by immutable native IDs, never by predictions. MIT.

Refuse changes to native text or conflicting role/group labels. Frozen test
annotations should be retained as historical evidence; write a new development
file. Sources are private inputs, not redistributable training assets.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import source_structure as structure


def refresh(data):
    import fitz
    data = copy.deepcopy(data)
    audit = []
    conflicts = []
    for doc in data['documents']:
        source = Path(doc['source_file'])
        if hashlib.sha256(source.read_bytes()).hexdigest() != doc['source_sha256']:
            raise ValueError('Source identity changed: '+doc['id'])
        selected = {page['page'] for page in doc['pages']}
        with fitz.open(source) as pdf:
            raw = [structure.raw_page(page, detect_tables=page.number+1 in selected) for page in pdf]
        pages = []
        for old in doc['pages']:
            page = raw[old['page']-1]
            labels = {lid: row for row in old['lines'] for lid in row.get('native_line_ids',[row['id']])}
            prior = {row['id']: row['text'] for row in old.get('native_lines',old['lines'])}
            for row in page['native_lines']:
                if row['id'] not in labels or prior.get(row['id']) != row['text']:
                    conflicts.append({'document':doc['id'],'page':page['page'],
                                      'line':row['id'],'reason':'Native text changed or has no label.'})
            for row in page['lines']:
                parents = [labels[lid] for lid in row['native_line_ids'] if lid in labels]
                labeled = [parent for parent in parents if parent['text'].strip()]
                roles = {parent.get('_role') for parent in labeled}
                groups = {parent.get('_group') for parent in labeled}
                if len(roles)>1 or len(groups)>1:
                    conflicts.append({'document':doc['id'],'page':page['page'],
                        'line':row['id'],'texts':[parent['text'] for parent in labeled],
                        'roles':sorted(str(x) for x in roles),'groups':sorted(str(x) for x in groups),
                        'reason':'New physical row merges contradictory labels; source review required.'})
                if labeled or parents:
                    parent = (labeled or parents)[0]
                    row.update({k:copy.deepcopy(v) for k,v in parent.items() if k.startswith('_')})
                    for flag in ['_assembly_unresolved','_pair_excluded']:
                        if any(p.get(flag) for p in parents):row[flag]=True
                    reasons = sorted({p['_unresolved_reason'] for p in parents if p.get('_unresolved_reason')})
                    if reasons:row['_unresolved_reason']='; '.join(reasons)
            reverse = {lid:row['id'] for row in page['lines'] for lid in row['native_line_ids']}
            if old.get('_order_regions'):
                regions = []
                seen = set()
                for region in old['_order_regions']:
                    current = []
                    for old_id in region:
                        for lid in labels[old_id].get('native_line_ids',[old_id]):
                            if lid in reverse and reverse[lid] not in seen:
                                current.append(reverse[lid]);seen.add(reverse[lid])
                    if current:regions.append(current)
                page['_order_regions'] = regions
            pages.append(page)
        doc.update(pages=pages,profile=structure.document_profile(raw),
                   source_page_count=len(raw),profile_scope='entire-original-source')
        audit.append({'document':doc['id'],'pages':len(pages),
                      'native_rows':sum(len(page['native_lines']) for page in pages),
                      'physical_rows':sum(len(page['lines']) for page in pages)})
    data['extraction_revision'] = structure.EXTRACTION_REVISION
    data['feature_revision'] = structure.FEATURE_REVISION
    return data, {'documents':audit,'conflicts':conflicts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--annotations',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--audit',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    data,audit = refresh(json.loads(args.annotations.read_text(encoding='utf-8')))
    args.audit.parent.mkdir(parents=True,exist_ok=True)
    args.audit.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if audit['conflicts']:raise ValueError('Conflicting evidence; inspect '+str(args.audit))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'documents':len(data['documents']),
                      'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == '__main__':main()
