"""Hash-bound parser-to-layout handoff. Geometry is evidence, not certification.
Copyright 2026 Yufeng Zhan. MIT.
"""
from collections import Counter
from pathlib import Path


def blocks_fingerprint(content, document_id):
    from translate import digest
    keys=('id','type','source','typography','structure','caption_block_ids','crop_text','footnote','footnote_refs','rows','header_rows','asset','asset_sha256','asset_fallback','asset_fallback_sha256')
    return digest([{**{k:b[k] for k in keys if k in b},'units':[{k:u[k] for k in ('id','source','source_segments') if k in u} for u in b.get('units',[])]} for b in content['blocks'] if b['source']['document_id']==document_id])


def write_map(root, content, source):
    from translate import write, sha
    import fitz
    root=Path(root);pages=[]
    with fitz.open(root/source['file']) as document:
        scope=source.get('selection_scope');numbers=scope.get('pages',[]) if isinstance(scope,dict) else range(1,len(document)+1)
        for number in numbers:
            page=document[number-1];blocks=[b for b in content['blocks'] if b['source']['document_id']==source['id'] and b['source'].get('page')==number]
            prose=[b for b in blocks if b['type']=='paragraph' and b.get('presentation',{}).get('role','body') in {'body','abstract'} and b.get('source',{}).get('bbox') and sum(len(u['source']) for u in b.get('units',[]))>=80]
            centers=[]
            for b in prose:
                x0,y0,x1,y1=b['source']['bbox']
                if (x1-x0)>page.rect.width*.62:continue
                center=next((a for a in centers if abs(a[0]-x0)<page.rect.width*.07),None)
                if center:center[1]+=1
                else:centers.append([x0,1])
            bands=sorted(x for x,n in centers if n>=2)
            columns=len(bands) if 1<=len(bands)<=3 else None
            records=[]
            for order,b in enumerate(blocks,1):
                bb=b['source'].get('bbox');column=None
                if bb and bands and bb[2]-bb[0]<page.rect.width*.62:column=min(range(len(bands)),key=lambda i:abs(bands[i]-bb[0]))+1
                hint={'order':order,'column':column,'source_bbox':bb,'page_width_pt':page.rect.width,'page_height_pt':page.rect.height}
                b['layout_hint']=hint
                records.append({'block_id':b['id'],'type':b['type'],'semantic_role':b.get('structure',{}).get('semantic_role',b.get('presentation',{}).get('role','body')),
                    'typography':b.get('typography',{}),'caption_block_ids':b.get('caption_block_ids',[]),
                    'crop_text':b.get('crop_text'),'footnote':b.get('footnote'),**hint})
            pages.append({'page':number,'width_pt':page.rect.width,'height_pt':page.rect.height,'columns':columns,
                          'column_evidence':'at least two model-proposed narrative regions per left-edge band' if columns else 'insufficient; retain native source profile',
                          'blocks':records})
    file=root/'reports/source-layout'/f"{source['id']}.json"
    write(file,{'schema_version':'1.0.2','document_id':source['id'],'source_sha256':source['sha256'],
                'structure_model':source.get('structure',{}),'blocks_fingerprint':blocks_fingerprint(content,source['id']),'pages':pages,'review_status':'unreviewed',
                'contract':'Layout consumes ordered blocks, hierarchy, typography, column bands, crops and caption links. Reflow translated text; inspect and refine renders before template fallback.'})
    source['layout_ir']={'file':file.relative_to(root).as_posix(),'sha256':sha(file),'review_status':'unreviewed'}
    return source['layout_ir']


def read_map(root, source, content=None):
    from translate import read,safe,sha
    record=source.get('layout_ir')
    if not record:return None
    path=safe(root,record['file'])
    if not path.is_file() or sha(path)!=record['sha256']:raise ValueError('Parser layout handoff missing or changed; regenerate and review.')
    data=read(path)
    if data['source_sha256']!=source['sha256']:raise ValueError('Parser layout handoff belongs to a different source.')
    if content is None and (Path(root)/'content.json').is_file():content=read(Path(root)/'content.json')
    if content is not None and data.get('blocks_fingerprint')!=blocks_fingerprint(content,source['id']):
        raise ValueError('Parser layout handoff is stale after source-block edits; regenerate and review.')
    return data
