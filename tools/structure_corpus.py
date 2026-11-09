#!/usr/bin/env python3
"""Private corpus extraction and structural evaluation; never invent annotations.

A native-line accounting pass is explicitly separate from measured correctness.
Copyright 2026 Yufeng Zhan. MIT.
"""
from pathlib import Path
from collections import Counter
import argparse
import gzip
import hashlib
import json
import random
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import source_structure as s
from structure_annotation_contract import reviewed_group_lines,source_identities

PROSE_ROLES={'body','title','heading','metadata','caption','reference','list'}


def equation_region_counts(groups, blocks, unresolved_spatial):
    """Compare 2D membership, never PDF object-order edges or equation meaning."""
    truth=[frozenset(row['id'] for row in group) for group in groups.values()
           if group and all(row.get('_role')=='equation' for row in group)]
    eligible=[region for region in truth if not region & unresolved_spatial]
    eligible_ids=set().union(*eligible) if eligible else set()
    # Damaged glyph maps do not erase inspected spatial memberships. Ignore
    # predictions that touch no region with complete spatial labels.
    predicted=[frozenset(block['line_ids']) for block in blocks
               if block['role']=='equation' and set(block['line_ids']) & eligible_ids]
    exact=sum(region in predicted for region in eligible)
    return {'truth_regions':len(truth),'eligible_regions':len(eligible),
            'unscorable_regions':len(truth)-len(eligible),'predicted_eligible_regions':len(predicted),
            'exact_regions':exact,
            'false_positive_regions':sum(region not in eligible for region in predicted)}


def certification_gate(rows,expected_identities):
    """Require complete per-document evidence; scores on labeled subsets cannot pass."""
    reasons=[];expected=set(expected_identities or [])
    actual={r.get('source_sha256') for r in rows if r.get('source_sha256')}
    if not expected:reasons.append('Expected corpus source identities are missing.')
    if len(rows)!=len(actual):reasons.append('Missing or repeated evaluated source identities.')
    if expected-actual:reasons.append(f'{len(expected-actual)} expected documents lack evaluation.')
    if actual-expected:reasons.append('Evaluation contains sources outside the expected corpus.')
    for row in rows:
        blockers=[]
        if not row.get('full_document_truth'):blockers.append('incomplete-page-truth')
        if row.get('role_truth_coverage')!=1:blockers.append('missing-role-truth')
        if row.get('assembly_truth_coverage')!=1 or row.get('ambiguous_group_rows_excluded'):blockers.append('unresolved-assembly-truth')
        if row.get('reading_order_truth_coverage')!=1:blockers.append('partial-reading-order-truth')
        if not row.get('native_accounting_pass'):blockers.append('native-accounting-failed')
        for metric in ['role_accuracy','join_precision','join_recall','reading_order_accuracy','exact_prose_group_accuracy']:
            value=row.get(metric)
            if not isinstance(value,(int,float)) or not .99<=value<=1:blockers.append(metric+'-below-99-or-unmeasured')
        # Raw text-line reconstruction cannot certify all information in a PDF.
        # These source-inspected substructures require their own explicit scores.
        verified=row.get('content_structure_metrics',{})
        for metric in ['table_structure','equation_structure','figure_ownership','source_text_integrity','cross_page_assembly']:
            entry=verified.get(metric,{})
            if not entry.get('source_review_complete') or not isinstance(entry.get('accuracy'),(int,float)) or not .99<=entry['accuracy']<=1:
                blockers.append(metric+'-unverified-or-below-99')
        row['certification_blockers']=blockers;row['document_99_percent']=not blockers
        if blockers:reasons.append(row['document']+': '+', '.join(blockers))
    return {'pass':bool(rows) and not reasons,'threshold':.99,'expected_documents':len(expected),
            'evaluated_documents':len(rows),'reasons':reasons,
            'definition':'Every expected source, every page and required structure; no aggregate, abstention-only or synthetic score substitutes for missing truth.'}


def scan(inventory,model,output):
    import fitz
    output.mkdir(parents=True,exist_ok=True);rows=json.loads(inventory.read_text(encoding='utf-8'))['files'];results=[]
    model_hash=hashlib.sha256(model.read_bytes()).hexdigest();started=time.time()
    pipeline_hash=hashlib.sha256(Path(s.__file__).read_bytes()).hexdigest()
    for i,item in enumerate(rows):
        cache=output/'cache'/(item['sha256']+'.json.gz');report=output/'documents'/(item['sha256']+'.json');cache.parent.mkdir(exist_ok=True);report.parent.mkdir(exist_ok=True)
        if report.exists():
            old=json.loads(report.read_text(encoding='utf-8'))
            if old.get('model_sha256')==model_hash and old.get('pipeline_sha256')==pipeline_hash:results.append(old);continue
        record={'source_sha256':item['sha256'],'path':item['path'],'model_sha256':model_hash,'pipeline_sha256':pipeline_hash,'pages':[],'status':'unreviewed'}
        try:
            if cache.exists():
                with gzip.open(cache,'rt',encoding='utf-8') as f:raw=json.load(f)
            else:raw=None
            if raw is None or raw.get('extraction_revision')!=s.EXTRACTION_REVISION:
                with fitz.open(item['path']) as d:pages=[s.raw_page(p,detect_tables=True) for p in d]
                raw={'pages':pages,'profile':s.document_profile(pages),'extraction_revision':s.EXTRACTION_REVISION}
                with gzip.open(cache,'wt',encoding='utf-8',compresslevel=5) as f:json.dump(raw,f,ensure_ascii=False,separators=(',',':'))
            for page in raw['pages']:
                result=s.reconstruct(page,raw['profile'],model_path=str(model))
                issues=Counter(x['code'] for x in result['issues']);encoding=[x['id'] for x in page['native_lines'] if any(ord(c)<32 and c not in '\t\r\n' or c=='�' for c in x['text'])]
                geometry=[x['id'] for x in page['lines'] if x['bbox'][0]<-1 or x['bbox'][1]<-1 or x['bbox'][2]>page['width']+1 or x['bbox'][3]>page['height']+1]
                record['pages'].append({'page':page['page'],'raw_sha256':page['raw_sha256'],'coverage':result['coverage'],'blocks':result['blocks'],'roles':result['line_roles'],'relations':result['relations'],
                                        'issue_counts':dict(issues),'encoding_review':encoding,'outside_page':geometry,'ocr_required':sum(len(x['text'].strip()) for x in page['lines'])<40})
            record['native_accounting_pass']=all(p['coverage']['pass'] for p in record['pages'])
        except Exception as e:record['error']=str(e);record['native_accounting_pass']=False
        report.write_text(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8');results.append(record)
        print(json.dumps({'processed':i+1,'total':len(rows),'pages':len(record['pages']),'native_accounting_pass':record['native_accounting_pass'],'elapsed_seconds':round(time.time()-started,1)}),flush=True)
        summary={'version':'1.0.2','model_sha256':model_hash,'processed_documents':len(results),'expected_documents':len(rows),'pages':sum(len(r['pages']) for r in results),'native_accounting_pass':all(r['native_accounting_pass'] for r in results),
                 'ocr_required_pages':sum(p['ocr_required'] for r in results for p in r['pages']),'encoding_review_pages':sum(bool(p['encoding_review']) for r in results for p in r['pages']),
                 'role_review_rows':sum(sum(x['review_required'] for x in p['roles']) for r in results for p in r['pages']),
                 'errors':[{'path':r['path'],'error':r['error']} for r in results if 'error' in r],
                 'correctness_accuracy':None,'reason':'Most corpus pages do not yet have source-inspected truth. Native accounting preserves PDF text layers but does not prove correct OCR, reading order, merge, equations, images or translation.'}
        (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary


def evaluate(annotations,model,output,inventory=None):
    data=json.loads(annotations.read_text(encoding='utf-8'));rows=[]
    provenance=s.load_model(str(model)).get('training',{})
    training_sources=set(provenance.get('real_train_source_sha256',[]))|set(provenance.get('real_train_source_family_sha256',[]))
    validation_sources=set(provenance.get('real_validation_source_sha256',[]))|set(provenance.get('real_validation_source_family_sha256',[]))
    specialist=s.load_model(str(model)).get('region_head',{}).get('training',{})
    training_sources.update(specialist.get('real_train_source_sha256',[]))
    training_sources.update(specialist.get('real_train_source_family_sha256',[]))
    validation_sources.update(specialist.get('real_validation_source_sha256',[]))
    validation_sources.update(specialist.get('real_validation_source_family_sha256',[]))
    for doc in data['documents']:
        if doc['split']=='test' and source_identities(doc)&(training_sources|validation_sources):
            raise ValueError('Test source participated in fitting or validation: '+doc['id'])
    for doc in data['documents']:
        true=[];pred=[];edges_true=set();edges_pred=set();coverage=[];errors=[];ambiguous=0;unresolved=0;row_count=0;native_row_count=0;order_correct=order_total=0;order_pages=0;ordered_rows=0;order_truth_valid=True;missing_groups=0;exact_groups=total_groups=eligible_groups=assembly_labeled_rows=0;damaged_text_rows=0;equation_counts=Counter()
        for page in doc['pages']:
            reconstructed=s.reconstruct(page,doc['profile'],model_path=str(model));lookup={x['id']:x for x in page['lines']};dec={x['line_id']:x for x in reconstructed['line_roles']}
            # Native whitespace remains in accounting, but is not a semantic
            # role or a prose edge. Mask both truth and prediction identically.
            semantic_lines=[x for x in page['lines'] if x['text'].strip()]
            native_row_count+=len(page['lines'])
            damaged_text_rows+=sum(s.native_text_damaged(x['text']) for x in semantic_lines)
            for line in semantic_lines:
                # Composite source rows (for example a section label and prose
                # printed on the same baseline) have no single defensible role.
                # Keep them in coverage accounting, but never score them as a
                # guessed label.
                if (line.get('_role') in s.ROLES and not line.get('_role_unresolved')
                        and not s.native_text_damaged(line['text'])):
                    true.append(line['_role']);pred.append(dec[line['id']]['assigned_role'])
                    if line['_role']!=dec[line['id']]['assigned_role']:errors.append({'line_id':line['id'],'expected':line['_role'],'actual':dec[line['id']]['assigned_role'],'text':line['text']})
            groups=reviewed_group_lines(page);row_count+=len(semantic_lines)
            predicted_groups={(block['role'],tuple(block['line_ids'])) for block in reconstructed['blocks']}
            for group in groups.values():
                if group[0].get('_role') in PROSE_ROLES:
                    total_groups+=1
                    if not any(line.get('_assembly_unresolved') or line.get('_pair_excluded') or
                               line.get('_role_unresolved') or '_group' not in line or
                               s.native_text_damaged(line['text']) for line in group):
                        eligible_groups+=1
                        exact_groups+=(group[0].get('_role'),tuple(line['id'] for line in group)) in predicted_groups
            # Unresolved source transcription cannot supply gold join edges.
            # Exclude both adjoining edges, report truth coverage separately,
            # and never turn an unreadable row into a false negative.
            blocked={x['id'] for x in page['lines'] if x.get('_pair_excluded') or
                     x.get('_assembly_unresolved') or x.get('_role_unresolved') or
                     '_group' not in x or x.get('_role') not in s.ROLES or
                     s.native_text_damaged(x['text']) or not x['text'].strip()}
            assembly_labeled_rows+=sum(x['id'] not in blocked for x in semantic_lines)
            missing_groups+=sum('_group' not in x for x in semantic_lines)
            unresolved+=sum(bool(x.get('_assembly_unresolved')) for x in semantic_lines)
            for line in semantic_lines:
                if line.get('_pair_excluded'):ambiguous+=1
            # Mask actual adjacent edges on both sides equally. Never manufacture
            # a positive edge across an excluded math fragment.
            for group in groups.values():
                if all(row.get('_role') in PROSE_ROLES for row in group):
                    edges_true.update((a['id'],b['id']) for a,b in zip(group,group[1:]) if a['id'] not in blocked and b['id'] not in blocked)
            for block in reconstructed['blocks']:
                if block['role'] in PROSE_ROLES:
                    edges_pred.update((a,b) for a,b in zip(block['line_ids'],block['line_ids'][1:]) if a not in blocked and b not in blocked)
            unresolved_spatial={x['id'] for x in page['lines'] if
                x.get('_assembly_unresolved') or x.get('_role_unresolved') or
                '_group' not in x or x.get('_role') not in s.ROLES}
            equation_counts.update(equation_region_counts(groups,reconstructed['blocks'],unresolved_spatial))
            if page.get('_order_regions'):
                order_pages+=1
                if page.get('_order_unresolved'):
                    order_truth_valid=False
                    continue
                # Order inside a merged region matters too. A block-index tie
                # must not falsely count two correctly joined native rows wrong.
                position={lid:i for i,lid in enumerate(lid for b in reconstructed['blocks'] for lid in b['line_ids'])}
                annotated=page['_order_regions']
                flat=[lid for region in annotated for lid in region]
                ids={x['id'] for x in semantic_lines}
                order_truth_valid &= len(flat)==len(set(flat)) and not (set(flat)-ids)
                ordered_rows+=len(ids.intersection(flat))
                for i,left in enumerate(annotated):
                    for right in annotated[i+1:]:
                        for a in left:
                            for b in right:
                                if a in position and b in position:
                                    order_total+=1;order_correct+=position[a]<position[b]
            coverage.append(reconstructed['coverage']['pass'])
        tp=len(edges_true&edges_pred);fp=len(edges_pred-edges_true);fn=len(edges_true-edges_pred)
        expected_pages=doc.get('source_page_count')
        selected={p['page'] for p in doc['pages']}
        row={'document':doc['id'],'source_sha256':doc.get('source_sha256'),'split':doc['split'],'pages':len(doc['pages']),
             'source_disjoint_from_fitting':not bool(source_identities(doc)&(training_sources|validation_sources))
                 if 'real_train_source_sha256' in provenance and doc.get('source_sha256') else None,
             'full_document_truth':bool(expected_pages and selected==set(range(1,expected_pages+1)) and len(selected)==len(doc['pages'])),
             'role_truth_coverage':len(true)/row_count if row_count else 0,'unresolved_role_rows':sum(bool(x.get('_role_unresolved')) for page in doc['pages'] for x in page['lines'] if x['text'].strip()),'unresolved_source_text_rows':damaged_text_rows,'missing_group_labels':missing_groups,
             'role_examples':len(true),'role_accuracy':sum(x==y for x,y in zip(true,pred))/max(1,len(true)),
             'join_true_positive':tp,'join_false_positive':fp,'join_false_negative':fn,
             'join_precision':tp/(tp+fp) if tp+fp else None,
             'join_recall':tp/(tp+fn) if tp+fn else None,
             'join_f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
             'join_metric_status':'measured' if tp+fp+fn else 'unmeasured-no-eligible-positive-or-predicted-edges',
             'join_metric_scope':'Ordered prose, code and note blocks; 2D equation/label/table regions are not positive prose edges. Incorrect prose merges remain false positives.',
             'equation_region_membership':{**equation_counts,
                 'exact_recall':equation_counts['exact_regions']/equation_counts['eligible_regions'] if equation_counts['eligible_regions'] else None,
                 'exact_precision':equation_counts['exact_regions']/equation_counts['predicted_eligible_regions'] if equation_counts['predicted_eligible_regions'] else None,
                 'scope':'Exact unordered source-row membership; damaged glyph maps do not invalidate inspected geometry. Not symbol transcription, equation topology or mathematical correctness.'},
             'prose_groups':total_groups,'exact_prose_groups':exact_groups,
             'exact_prose_group_accuracy':exact_groups/max(1,total_groups),
             'eligible_prose_groups':eligible_groups,'unscorable_prose_groups':total_groups-eligible_groups,
             'eligible_exact_prose_group_accuracy':exact_groups/eligible_groups if eligible_groups else None,
             'ambiguous_group_rows_excluded':ambiguous,'all_rows':row_count,'native_physical_rows':native_row_count,'whitespace_rows':native_row_count-row_count,'unresolved_assembly_rows':unresolved,'assembly_labeled_rows':assembly_labeled_rows,'assembly_truth_coverage':assembly_labeled_rows/max(1,row_count),
             'reading_order_truth_coverage':ordered_rows/row_count if row_count and order_truth_valid else 0,
             'content_structure_metrics':doc.get('content_structure_metrics',{}),
             'source_text_integrity_status':'source-review-required' if damaged_text_rows else 'no-control-or-replacement-glyphs-detected; source text still unverified',
             'assembly_metric_scope':'Page-local ordered native-row groups only; damaged native-text rows block adjacent-edge scoring; cross-page continuation requires separately reviewed evidence.',
             'native_accounting_pass':all(coverage),'reading_order_accuracy':order_correct/order_total if order_total else None,'reading_order_pairs':order_total,'reading_order_annotated_pages':order_pages,
             'reading_order_reason':'Explicit source-inspected cross-region precedence graph only; no in-region order or semantic certification.' if order_total else 'Requires separately authored ordered region graph; not inferred from role/group labels.',
             'role_errors':errors,'false_join_edges':sorted(edges_pred-edges_true),'missed_join_edges':sorted(edges_true-edges_pred)}
        rows.append(row)
    expected=[x['sha256'] for x in json.loads(inventory.read_text(encoding='utf-8'))['files']] if inventory else data.get('expected_source_identities',[])
    gate=certification_gate(rows,expected)
    result={'version':'1.0.2','evaluation_revision':'role-prose-spatial-coverage-v4',
            'evaluator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),
            'annotation_sha256':hashlib.sha256(annotations.read_bytes()).hexdigest(),'pipeline_sha256':hashlib.sha256(Path(s.__file__).read_bytes()).hexdigest(),
            'documents':rows,'all_documents_99_percent':gate['pass'],'certification':gate,
            'reason':'Source-inspected labeled-subset scores and complete-corpus certification are separate. Agent labels are not independent human gold.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return [{k:r[k] for k in ['document','split','role_accuracy','join_precision','join_recall','join_f1','native_accounting_pass']} for r in rows]


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('scan');q.add_argument('--inventory',type=Path,required=True);q.add_argument('--model',type=Path,required=True);q.add_argument('--output',type=Path,required=True)
    q=sub.add_parser('evaluate');q.add_argument('--annotations',type=Path,required=True);q.add_argument('--model',type=Path,required=True);q.add_argument('--output',type=Path,required=True);q.add_argument('--inventory',type=Path)
    a=p.parse_args();print(json.dumps(scan(a.inventory,a.model,a.output) if a.command=='scan' else evaluate(a.annotations,a.model,a.output,a.inventory),ensure_ascii=False))

if __name__=='__main__':main()
