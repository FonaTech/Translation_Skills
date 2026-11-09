"""Experimental structure-head adapter with an immutable native evidence ledger.

New PDF projects use this path by default; explicit native extraction remains available. It proposes extraction
units; neither translations nor extraction/semantic review are manufactured.
Copyright 2026 Yufeng Zhan. MIT.
"""
from pathlib import Path
import gzip
import hashlib
import json
import re

import source_structure as structure


def prepare(document, selected, model_path=None):
    path=Path(model_path) if model_path else structure.MODEL_PATH
    model=structure.load_model(str(path))
    if model is None:
        raise ValueError('Structure model is missing; select native extraction explicitly or supply --structure-model.')
    selected=set(selected)
    all_pages=[structure.raw_page(page,detect_tables=page.number in selected) for page in document]
    pages=[page for page in all_pages if page['page']-1 in selected]
    return {'version':'1.0.2','experimental':True,'model_id':model['id'],'model_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'pipeline_sha256':hashlib.sha256(Path(structure.__file__).read_bytes()).hexdigest(),
            'model_path':path,'pages':{p['page']:p for p in pages},'profile':structure.document_profile(all_pages),
            'source_file':str(document.name),'profile_scope':'entire-original-document','source_page_count':len(all_pages)}


def append_page(root, content, document_id, page_number, prepared, order, add_block, split_text):
    page=prepared['pages'][page_number]
    result=structure.reconstruct(page,prepared['profile'],order=order,model_path=str(prepared['model_path']))
    created={}
    for region in result['blocks']:
        typography=region['typography'];semantic=region.get('semantic_role',region['role'])
        role='bibliography' if region['role']=='reference' else 'note' if semantic=='footnote' else region['role']
        # Semantic classes include title/heading/table/label; presentation has a smaller contract.
        # Headings render by block type and level. Preserve the semantic decision in structure.
        if role not in {'body','metadata','bibliography','abstract','keywords','caption','equation','note'}:role='body'
        literal=semantic=='code';spatial=semantic=='equation' and region.get('representation')=='source-spatial-region'
        source={'page':page_number,'bbox':region['bbox'],'physical_row_ids':region['line_ids'],
                'native_line_ids':region['native_line_ids'],'raw_sha256':page['raw_sha256'],
                'structure_model_sha256':prepared['model_sha256']}
        extra={}
        if literal:
            extra['format']='code'
            extra['source_lines']=region.get('source_lines',[])
        if spatial:
            # Keep 2D symbols/fractions as source-matching artwork. A flat native
            # transcript is audit evidence, never a claimed reconstructed formula.
            import fitz
            from vector_assets import export_crop
            source_file=prepared.get('source_file')
            if not source_file:raise ValueError('A spatial equation needs its original PDF for faithful cropping.')
            stem=Path(root)/'assets'/f'{document_id}-p{page_number:04d}-equation-{len(created)+1:04d}'
            with fitz.open(source_file) as pdf:
                original=pdf[page_number-1];bb=fitz.Rect(region['bbox'])+(-2,-2,2,2);bb&=original.rect
                if original.rotation:
                    stem.parent.mkdir(parents=True,exist_ok=True);asset=stem.with_suffix('.png')
                    original.get_pixmap(matrix=fitz.Matrix(3,3),clip=bb,alpha=False).save(asset)
                    extra.update(asset=asset.relative_to(root).as_posix(),asset_metadata={'representation':'source-rendered-png','bbox':list(bb),'visual_review':'pending'})
                else:
                    crop=export_crop(original,bb,stem,scale=3)
                    extra.update(asset=crop['vector'].relative_to(root).as_posix(),asset_fallback=crop['fallback'].relative_to(root).as_posix(),asset_metadata=crop['metadata'])
            extra.update(width_mm=min(170,(region['bbox'][2]-region['bbox'][0]+4)*25.4/72),
                         label_policy='retained-original',label_note='Original mathematical notation retained; inspect the source crop.',
                         native_spatial_transcript=region['text'])
        block=add_block(content,document_id,'equation' if spatial else 'reference' if role=='bibliography' else region['type'],source,
            [] if spatial else [region['text']] if literal or role=='bibliography' else split_text(region['text']),
            level=region['level'],typography=typography,presentation={'role':role},
            structure={'experimental':True,'review_required':True,'semantic_role':semantic,
                       'region_id':region.get('region_id'),'representation':region.get('representation'),
                       'proposal_uncertain':region['review_required'],'operations':region['operations']},**extra)
        for lid in region['line_ids']:created[lid]=block['id']
        if region['role'] in {'equation','table','label'}:
            content['issues'].append({'document_id':document_id,'block_id':block['id'],'page':page_number,
                'code':'structure-protected-review','status':'open',
                'message':'Source geometry retained. Inspect mathematical typography, cell positions or figure-label ownership; native accounting does not certify reconstruction.'})
    # Resolve actual line anchors into stable block IDs for editor/export users.
    for relation in result.get('region_relations',[]):
        if relation['type']!='footnote-reference':continue
        note=next((b for b in content['blocks'] if b['source']['document_id']==document_id and
                   b['source'].get('page')==page_number and b.get('structure',{}).get('region_id')==relation['region_id']),None)
        if note is None:continue
        anchors=[{**a,'block_id':created[a['line_id']]} for a in relation['anchors'] if a['line_id'] in created]
        note['footnote']={'marker':relation['marker'],'anchors':anchors,'status':relation['status']}
        if relation['status']=='source-marker-matched':
            for a in anchors:
                parent=next(b for b in content['blocks'] if b['id']==a['block_id'])
                parent.setdefault('footnote_refs',[]).append({'note_block_id':note['id'],'marker':relation['marker'],'source_line_id':a['line_id']})
    folder=Path(root)/'reports'/'source-structure';folder.mkdir(parents=True,exist_ok=True)
    evidence=folder/f'{document_id}-p{page_number:04d}.json.gz'
    with gzip.open(evidence,'wt',encoding='utf-8') as stream:
        json.dump({'version':'1.0.2','experimental':True,'model_sha256':prepared['model_sha256'],
            'pipeline_sha256':prepared['pipeline_sha256'],'page':page,'result':result},stream,ensure_ascii=False,allow_nan=False)
    content['issues'].append({'document_id':document_id,'page':page_number,'code':'structure-source-review','status':'open',
        'evidence':evidence.relative_to(root).as_posix(),
        'message':'Experimental role/join/order proposal. Compare the complete source page, including unresolved roles, equations, columns and tables. Native accounting is not correctness.'})
    warnings=[{'page':page_number,**issue} for issue in result['issues']]
    encoding=[x['id'] for x in page.get('native_lines',page['lines'])
              if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]',x['text'])]
    if encoding:
        warnings.append({'page':page_number,'code':'text-encoding-review','native_line_ids':encoding,
            'message':'Native control/replacement glyphs retained. Compare symbols with the source page; do not guess missing characters.'})
    return result,warnings
