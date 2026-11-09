#!/usr/bin/env python3
"""Freeze source-authored labels with identity and consistency checks, not gold certification.

Copyright 2026 Yufeng Zhan. MIT. Private evidence belongs outside this repository.
"""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import source_structure as structure
from structure_annotation_contract import source_identities


def audit(data):
    """Validate explicit full-page truth fields; never generate missing labels."""
    seen=set();families=set();errors=[];page_count=0;unresolved=0
    for document in data.get('documents',[]):
        name=document.get('id','<missing>');identity=document.get('source_sha256')
        if not isinstance(identity,str) or len(identity)!=64 or any(c not in '0123456789abcdef' for c in identity) or identity in seen:errors.append(name+': invalid/repeated source SHA-256')
        seen.add(identity)
        try:
            lineage=source_identities(document)
            if lineage & families:errors.append(name+': repeated source family or derived copy')
            families.update(lineage)
        except ValueError as error:errors.append(name+': '+str(error))
        if document.get('split') not in {'train','validation','test'}:errors.append(name+': invalid split')
        label_source=document.get('label_source','')
        if not label_source or label_source.lower().startswith('pending'):errors.append(name+': supply actual label provenance')
        pages=document.get('pages',[]);numbers=[p.get('page') for p in pages]
        count=document.get('source_page_count',0)
        if not isinstance(count,int) or count<1 or any(not isinstance(n,int) for n in numbers) or sorted(numbers)!=list(range(1,count+1)) or not numbers:
            errors.append(name+': full-document pages required')
        for page in pages:
            page_count+=1;prefix=name+' page '+str(page['page']);rows=[r for r in page['lines'] if r['text'].strip()]
            ids=[r['id'] for r in rows];groups=defaultdict(set)
            if len(ids)!=len(set(ids)):errors.append(prefix+': repeated physical-row IDs')
            for row in rows:
                if row.get('_role') not in structure.ROLES:errors.append(prefix+': missing/invalid role '+row['id'])
                if not isinstance(row.get('_group'),str) or not row['_group'].strip():errors.append(prefix+': missing group '+row['id'])
                else:groups[row['_group']].add(row.get('_role'))
                if row.get('_assembly_unresolved'):
                    unresolved+=1
                    if not row.get('_unresolved_reason'):errors.append(prefix+': unresolved row needs reason '+row['id'])
            if any(len(v)!=1 for v in groups.values()):errors.append(prefix+': mixed roles inside a single paragraph group')
            ordered=[lid for region in page.get('_order_regions',[]) for lid in region]
            if len(ordered)!=len(set(ordered)) or set(ordered)!=set(ids):errors.append(prefix+': reading regions must cover every nonblank row exactly once')
    if not seen:errors.append('No labeled sources.')
    return {'pass':not errors,'documents':len(seen),'pages':page_count,
            'unresolved_assembly_rows':unresolved,'errors':errors,
            'not_independent_gold_certification':True}


def verify_source_evidence(data):
    """Re-extract immutable native evidence; reject annotation-time text edits.

    This checks the PDF text layer, not OCR correctness or semantic truth. Labels
    and private inspection notes may be added, but source geometry/text and the
    full-source feature profile must match the extraction revision in use.
    """
    import fitz
    if data.get('extraction_revision')!=structure.EXTRACTION_REVISION:
        raise ValueError('Extraction revision changed; re-extract and inspect labels before freezing.')
    for document in data['documents']:
        path=Path(document['source_file'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=document['source_sha256']:
            raise ValueError('Source file changed: '+document['id'])
        with fitz.open(path) as pdf:
            if len(pdf)!=document['source_page_count']:
                raise ValueError('Source page count changed: '+document['id'])
            extracted=[structure.raw_page(page,detect_tables=True) for page in pdf]
        for page in document['pages']:
            raw=extracted[page['page']-1]
            for key in ['page','width','height','rotation','cropbox','raw_sha256','native_lines',
                        'table_regions','rejected_table_regions','structure_regions','graphic_regions','heading_regions']:
                if structure.digest(page.get(key))!=structure.digest(raw.get(key)):
                    raise ValueError('Source evidence changed: '+document['id']+' page '+str(page['page'])+' '+key)
            rows=[{k:v for k,v in row.items() if not k.startswith('_')} for row in page['lines']]
            if structure.digest(rows)!=structure.digest(raw['lines']):
                raise ValueError('Physical-row evidence changed: '+document['id']+' page '+str(page['page']))
        saved_profile=json.loads(json.dumps(document['profile']))
        source_profile=json.loads(json.dumps(structure.document_profile(extracted)))
        # JSON turns numeric histogram keys into strings. Canonicalize both
        # sides before sorting keys, and ignore order in the furniture set.
        for profile in (saved_profile,source_profile):
            profile['repeated_furniture']=sorted(profile.get('repeated_furniture',[]))
        if structure.digest(saved_profile)!=structure.digest(source_profile):
            raise ValueError('Full-source feature profile changed: '+document['id'])


def freeze(annotations,output):
    annotations=Path(annotations);output=Path(output)
    if output.exists() or output.with_suffix(output.suffix+'.sha256').exists():raise FileExistsError('Frozen evidence must not be overwritten.')
    data=json.loads(annotations.read_text(encoding='utf-8'));check=audit(data)
    if not check['pass']:raise ValueError(json.dumps(check,ensure_ascii=False))
    verify_source_evidence(data)
    data['freeze']={'utc':datetime.now(timezone.utc).isoformat(),
                    'input_annotation_sha256':hashlib.sha256(annotations.read_bytes()).hexdigest(),
                    'consistency_check':check,'meaning':'Identity and label completeness only; author remains responsible for source inspection and truth. No model prediction was used by this tool.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n',encoding='utf-8')
    return {'sha256':digest,**check}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--annotations',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(freeze(args.annotations,args.output),ensure_ascii=False))


if __name__=='__main__':main()
