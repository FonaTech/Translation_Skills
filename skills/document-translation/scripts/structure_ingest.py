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


def formula_crop_exclusions(page, region, result, bbox):
    """Isolate adjoining text/other equations using disjoint native ownership.

    Font boxes can overlap even when the displayed glyphs do not. Redacting an
    entire adjoining line can therefore delete formula symbols. A tiny rectangle
    inside each adjoining character and outside every owned glyph box removes
    that character in a temporary PDF only. Ambiguous ownership is left intact.
    """
    import fitz
    owned=set(region['native_line_ids'])
    native=page.get('native_lines',[])
    recognition=fitz.Rect(region['bbox']);crop=fitz.Rect(bbox)
    def glyphs(row):
        return [char for span in row.get('spans',[]) for char in span.get('chars',[])
                if (char.get('c','').strip() or structure.visible_math_controls({'spans':[{**span,'chars':[char]}]}))
                and not fitz.Rect(char['bbox']).is_empty]
    protected=[]
    for row in native:
        if row['id'] not in owned:continue
        boxes=[b for c in glyphs(row) for b in
               [c['bbox'],c.get('native_glyph',{}).get('ink_bbox')] if b] or [row['bbox']]
        protected.extend(fitz.Rect(b)+(-.2,-.2,.2,.2) for b in boxes)
    if not protected:return []
    decisions={d['line_id']:d for d in result.get('line_roles',[])}
    prose_ids=set()
    other_equation_ids=set()
    for block in result.get('blocks',[]):
        ids=set(block.get('native_line_ids',[]))
        if (block.get('semantic_role',block.get('role'))=='equation' and
                block.get('representation')=='source-spatial-region' and ids and
                ids.isdisjoint(owned)):
            other_equation_ids.update(ids)
    for row in page.get('lines',[]):
        decision=decisions.get(row['id'],{})
        if (decision.get('assigned_role') in {'body','abstract','keywords','caption','metadata','heading','title','reference','list'}
                and decision.get('predicted_role')!='equation'):
            prose_ids.update(row.get('native_line_ids',[row['id']]))
    exclusions=[]
    for row in native:
        box=fitz.Rect(row['bbox'])
        row_glyphs=glyphs(row)
        for char in row_glyphs:
            ink=char.get('native_glyph',{}).get('ink_bbox')
            if ink:box|=fitz.Rect(ink)
        separate_equation=row['id'] in other_equation_ids
        if row['id'] in owned or not (row['id'] in prose_ids or separate_equation) or not box.intersects(crop):continue
        # Only adjoining boundary text is eligible; text centered inside the
        # recognition rectangle remains evidence for a missed formula member.
        center=fitz.Point((box.x0+box.x1)/2,(box.y0+box.y1)/2)
        if recognition.contains(center) and not separate_equation:continue
        for char in row_glyphs:
            cb=fitz.Rect(char['bbox'])
            visible=fitz.Rect(char.get('native_glyph',{}).get('ink_bbox',char['bbox']))
            if not (cb.intersects(crop) or visible.intersects(crop)):continue
            pieces=[cb]
            for keep in protected:
                remaining=[]
                for piece in pieces:
                    hit=piece & keep
                    if hit.is_empty:remaining.append(piece);continue
                    for candidate in [(piece.x0,piece.y0,piece.x1,hit.y0),
                                      (piece.x0,hit.y1,piece.x1,piece.y1),
                                      (piece.x0,hit.y0,hit.x0,hit.y1),
                                      (hit.x1,hit.y0,piece.x1,hit.y1)]:
                        candidate=fitz.Rect(candidate)
                        if candidate.width>.12 and candidate.height>.12:remaining.append(candidate)
                pieces=remaining
                if not pieces:break
            if not pieces:continue
            clear=max(pieces,key=lambda b:b.width*b.height)
            x=(clear.x0+clear.x1)/2;y=(clear.y0+clear.y1)/2
            dx=min(.08,clear.width/4);dy=min(.08,clear.height/4)
            exclusions.append({'bbox':[x-dx,y-dy,x+dx,y+dy],
                'reason':('Adjoining separately owned equation character' if separate_equation else 'Adjoining non-equation native character')+'; exclusion is disjoint from every owned formula glyph box and known source outline.',
                'evidence':f'native-ledger:{page["raw_sha256"]}:{row["id"]}; formula-native-lines:'+','.join(sorted(owned))})
    return exclusions


def formula_provenance(decisions, model_id, model_sha256):
    """Separate raw neural proposals from seeds actually used by decoding."""
    member_ids={row['line_id'] for row in decisions}
    used={lid for row in decisions
          for lid in row.get('region_evidence',{}).get('seed_line_ids',[])}
    used.update(row['line_id'] for row in decisions
                if row.get('region_prediction',{}).get('class')=='math' and
                row.get('region_prediction',{}).get('applied') and
                row.get('assigned_role')=='equation')
    return {'kind':'display','model_id':model_id,'model_sha256':model_sha256,
            'line_decisions':decisions,
            'raw_role_prediction_line_ids':[row['line_id'] for row in decisions
                                            if row.get('predicted_role')=='equation'],
            'raw_region_prediction_line_ids':[row['line_id'] for row in decisions
                                              if row.get('region_prediction',{}).get('class')=='math'],
            'neural_seed_line_ids':sorted(used & member_ids),
            'role_fallback_pending_review':any(row.get('rule')=='source-math-region-pending-review'
                                                for row in decisions),
            'method':'numerical-role-and-region-model-with-source-geometry-constraints',
            'semantic_transcription':False}


def prepare(document, selected, model_path=None):
    path=Path(model_path) if model_path else structure.MODEL_PATH
    model=structure.load_model(str(path))
    if model is None:
        raise ValueError('Structure model is missing; select native extraction explicitly or supply --structure-model.')
    selected=set(selected)
    all_pages=[structure.raw_page(page,detect_tables=page.number in selected) for page in document]
    pages=[page for page in all_pages if page['page']-1 in selected]
    return {'version':'1.0.3','experimental':True,'model_id':model['id'],'model_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
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
        if semantic=='running-furniture':
            # The full native page and model decisions still include these rows.
            # Do not send page numbers/running titles to the translation model.
            from translate import read,write
            archive=Path(root)/'reports/page-furniture'/f'{document_id}.json'
            data=read(archive) if archive.exists() else {'version':'1.0.3','document_id':document_id,'regions':[]}
            decisions={r['line_id']:r for r in result['line_roles']}
            item={'source':source,'text':region['text'],'typography':typography,
                  'line_decisions':[decisions[lid] for lid in region['line_ids']],
                  'disposition':'source-page-furniture; archived outside translation and reading body'}
            data['regions']=[r for r in data['regions'] if r['source']['physical_row_ids']!=source['physical_row_ids']]+[item]
            write(archive,data)
            continue
        if region.get('representation') in {'source-table-cells','source-table-artwork'}:
            from structure_tables import append as append_cells, append_artwork
            append_table=append_cells if region['representation']=='source-table-cells' else append_artwork
            block=append_table(root,content,document_id,source,region,page,prepared['source_file'],add_block)
            for lid in region['line_ids']:created[lid]=block['id']
            if region['representation']=='source-table-artwork':continue
            content['issues'].append({'document_id':document_id,'block_id':block['id'],'page':page_number,
                'code':'structure-table-cell-review','status':'open',
                'message':'Source gutters and stub baselines propose cells. Compare complete cell membership, mathematical artwork, translations and row associations.'})
            continue
        extra={}
        if spatial:
            decisions=[row for row in result.get('line_roles',[]) if row['line_id'] in region['line_ids']]
            extra['formula_detection']=formula_provenance(
                decisions,prepared.get('model_id',result.get('model')),prepared['model_sha256'])
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
                exclusions=formula_crop_exclusions(page,region,result,bb)
                if exclusions:source['native_text_exclusions']=exclusions
                if original.rotation:
                    from vector_assets import source_crop_page
                    stem.parent.mkdir(parents=True,exist_ok=True);asset=stem.with_suffix('.png')
                    with source_crop_page(original,exclusions) as reviewed:
                        reviewed.get_pixmap(matrix=fitz.Matrix(3,3),clip=bb,alpha=False).save(asset)
                    extra.update(asset=asset.relative_to(root).as_posix(),asset_metadata={'representation':'source-rendered-png','bbox':list(bb),'visual_review':'pending'})
                else:
                    crop=export_crop(original,bb,stem,scale=3,native_text_exclusions=exclusions)
                    extra.update(asset=crop['vector'].relative_to(root).as_posix(),asset_fallback=crop['fallback'].relative_to(root).as_posix(),asset_metadata=crop['metadata'])
            # Use the same clipped artwork rectangle for extraction and PDF fidelity.
            # Retain the tight recognition rectangle separately as native evidence.
            source['recognition_bbox']=source['bbox']
            source['bbox']=list(bb)
            extra.update(width_mm=min(170,bb.width*25.4/72),
                         label_policy='retained-original',label_note='Original mathematical notation retained; inspect the source crop.',
                         native_spatial_transcript=region['text'])
        block=add_block(content,document_id,'equation' if spatial else 'reference' if role=='bibliography' else region['type'],source,
            [] if spatial else [region['text']] if literal or role=='bibliography' else split_text(region['text']),
            level=region['level'],typography=typography,presentation={'role':role},
            structure={'experimental':True,'review_required':True,'semantic_role':semantic,
                       'region_id':region.get('region_id'),'representation':region.get('representation'),
                       'proposal_uncertain':region['review_required'],'operations':region['operations']},**extra)
        if not spatial and not literal and role!='bibliography':
            from math_protection import attach_block
            attach_block(block,region,page,root,prepared['source_file'])
        for lid in region['line_ids']:created[lid]=block['id']
        if region['role'] in {'equation','table','label'}:
            content['issues'].append({'document_id':document_id,'block_id':block['id'],'page':page_number,
                'code':'structure-protected-review','status':'open',
                'message':'Source geometry retained. Inspect mathematical typography, cell positions or figure-label ownership; native accounting does not certify reconstruction.'})
    # Bind a source table caption only after all page blocks have stable IDs.
    for table in content['blocks']:
        if table['source']['document_id']!=document_id or table['source'].get('page')!=page_number or not (table['type']=='table' or table.get('source_table_fallback')):continue
        box=table['source']['bbox']
        captions=[b for b in content['blocks'] if b['source']['document_id']==document_id and
                  b['source'].get('page')==page_number and b.get('presentation',{}).get('role')=='caption' and
                  re.match(r'^\s*table\b',' '.join(u['source'] for u in b.get('units',[])),re.I) and
                  b['source'].get('bbox') and 0<=box[1]-b['source']['bbox'][3]<40 and
                  box[0]-40<=(b['source']['bbox'][0]+b['source']['bbox'][2])/2<=box[2]+40]
        if len(captions)==1:table['caption_block_ids']=[captions[0]['id']]
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
        json.dump({'version':'1.0.3','experimental':True,'model_sha256':prepared['model_sha256'],
            'pipeline_sha256':prepared['pipeline_sha256'],'page':page,'result':result},stream,ensure_ascii=False,allow_nan=False)
    content['issues'].append({'document_id':document_id,'page':page_number,'code':'structure-source-review','status':'open',
        'evidence':evidence.relative_to(root).as_posix(),
        'message':'Experimental role/join/order proposal. Compare the complete source page, including unresolved roles, equations, columns and tables. Native accounting is not correctness.'})
    warnings=[{'page':page_number,**issue} for issue in result['issues']]
    encoding=[x['id'] for x in page.get('native_lines',page['lines'])
              if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffd]',x['text'])]
    if encoding:
        warnings.append({'page':page_number,'code':'text-encoding-review','native_line_ids':encoding,
            'message':'Native control/replacement glyphs retained. Compare symbols with the source page; do not guess missing characters.'})
    return result,warnings
