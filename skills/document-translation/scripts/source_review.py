"""Host-agent source review exchange. Copyright 2026 Yufeng Zhan. MIT.

No review, correction or translation is manufactured by this module. Inputs
are source-hash-bound decisions made by the invoking model after inspection.
"""
import copy,json
from pathlib import Path
from translate import project,read,write,source_snap,safe,sha,now,units

def prepare(root):
    r,m,c=project(root)
    packet={'schema_version':'1.0.3','source_hash':source_snap(m,c),'reviewer':'','evidence':[],
        'contract':'Inspect selected source previews, native rows and crop ledgers. PDF processing uses native text/font/vector geometry only: no OCR or page/table transcription fallback. Return checked operations without author completions. Do not edit rendered files or write per-document repair code.',
        'operations':[],'issues':c.get('issues',[]),'blocks':[]}
    for b in c['blocks']:
        packet['blocks'].append({'id':b['id'],'type':b['type'],'source':b['source'],'typography':b.get('typography'),
            'structure':b.get('structure'),'presentation':b.get('presentation'),'asset':b.get('asset'),
            'caption_block_ids':b.get('caption_block_ids',[]),'crop_text':b.get('crop_text'),
            'units':[{'id':u['id'],'source':u['source'],'ocr_evidence':u.get('ocr_evidence')} for u in b.get('units',[])]})
    packet['source_previews']=[p.relative_to(r).as_posix() for p in sorted((r/'previews').glob('*.png'))]
    packet['ocr_evidence']=[p.relative_to(r).as_posix() for p in sorted((r/'reports/region-ocr').glob('*.json'))]
    packet['artwork_evidence']=[p.relative_to(r).as_posix() for p in sorted((r/'reports/region-artwork').glob('*.json'))]
    path=r/'tasks/source-review.json';write(path,packet);return path

def apply(root,path):
    r,m,original=project(root);packet=read(path)
    if set(packet)-{'schema_version','source_hash','reviewer','evidence','operations'}:raise ValueError('Return review metadata and operations only; source context is immutable.')
    if packet.get('source_hash')!=source_snap(m,original):raise ValueError('Stale source review packet.')
    if not str(packet.get('reviewer','')).strip():raise ValueError('Name the actual inspecting agent.')
    evidence={}
    for f in packet.get('evidence',[]):
        p=safe(r,f)
        if not p.is_file():raise ValueError('Missing inspected source evidence: '+f)
        evidence[f]=sha(p)
    if not evidence:raise ValueError('Source review requires inspected source evidence.')
    c=copy.deepcopy(original);blocks={b['id']:b for b in c['blocks']};lookup={u['id']:u for _,u in units(c)};changed=[]
    operations=packet.get('operations',[])
    if not isinstance(operations,list) or not operations:raise ValueError('No checked operations supplied.')
    for op in operations:
        if not isinstance(op,dict) or not isinstance(op.get('observation'),str) or len(op['observation'].strip())<12:raise ValueError('Each correction needs an actual source observation.')
        kind=op.get('op')
        if kind=='correct-unit':
            if set(op)-{'op','unit_id','before','after','observation'}:raise ValueError('Unexpected correction fields.')
            u=lookup.get(op.get('unit_id'))
            if u is None or u['source']!=op.get('before') or not isinstance(op.get('after'),str) or not op['after'].strip():raise ValueError('Unknown unit or changed source; no blind replacement.')
            if u.get('translations') or u.get('alignment'):raise ValueError('Correct source before translation; preserve existing work.')
            u.setdefault('source_corrections',[]).append({'before':u['source'],'observation':op['observation'],'evidence':evidence})
            u['source']=op['after']
        elif kind=='classify-block':
            if set(op)-{'op','block_id','type','role','level','observation'}:raise ValueError('Unexpected classification fields.')
            b=blocks.get(op.get('block_id'))
            if b is None or b['type'] not in {'paragraph','heading','reference'}:raise ValueError('Classify an existing text block.')
            if op.get('type') not in {'paragraph','heading','reference'} or op.get('role') not in {'body','metadata','bibliography','abstract','keywords','caption','note'}:raise ValueError('Unsupported classification.')
            b['type']=op['type'];b.setdefault('presentation',{})['role']=op['role']
            b.setdefault('structure',{}).update(semantic_role='heading' if b['type']=='heading' else 'reference' if b['type']=='reference' else op['role'])
            if b['type']=='heading':
                level=op.get('level',2)
                if not isinstance(level,int) or not 1<=level<=6:raise ValueError('Heading level must be 1..6.')
                b['level']=level
        elif kind=='asset-label-policy':
            if set(op)-{'op','block_id','policy','note','observation'}:raise ValueError('Unexpected asset fields.')
            b=blocks.get(op.get('block_id'))
            if b is None or not b.get('asset') or op.get('policy') not in {'retained-original','no-text','translated'} or not str(op.get('note','')).strip():raise ValueError('Asset policy needs an explicit source-based disposition and note.')
            if op['policy']=='translated' and not b.get('units'):raise ValueError('Translated labels need actual label units; do not falsely certify original pixels.')
            b.update(label_policy=op['policy'],label_note=op['note'])
        elif kind=='transcribe-page':
            if set(op)-{'op','document_id','page','evidence_file','regions','observation'}:raise ValueError('Unexpected page transcription fields.')
            did=op.get('document_id');pn=op.get('page');source=next((s for s in c['sources'] if s['id']==did),None)
            if source is None or type(pn) is not int or not 1<=pn<=int(source.get('page_count') or 1):raise ValueError('Unknown source page.')
            if Path(source['file']).suffix.lower()=='.pdf':raise ValueError('PDF OCR/transcription is disabled; retain original pages with unavailable native text.')
            scope=source.get('selection_scope')
            if isinstance(scope,dict) and pn not in scope.get('pages',[]):raise ValueError('Page is outside selected scope.')
            existing=[b for b in c['blocks'] if b['source']['document_id']==did and b['source'].get('page')==pn]
            if any(b.get('units') for b in existing):raise ValueError('Correct existing native/OCR units; never duplicate a readable page.')
            f=op.get('evidence_file');src=safe(r,source['file'])
            if src.suffix.lower()=='.pdf':
                expected=f'previews/{did}-p{pn:04d}.png'
                if f!=expected:raise ValueError('Use the original source-page preview, not a rendered translation.')
                import fitz
                with fitz.open(src) as pdf:width,height=pdf[pn-1].rect.width,pdf[pn-1].rect.height
            else:
                if f!=source['file']:raise ValueError('Raster transcription requires the original source image.')
                from PIL import Image
                with Image.open(src) as image:width,height=image.size
            if f not in evidence:raise ValueError('Inspect the exact source image before transcribing.')
            regions=op.get('regions')
            if not isinstance(regions,list) or not regions:raise ValueError('Supply observed regions in reading order; never infer missing text.')
            from translate import add_block
            created=[]
            for region in regions:
                if not isinstance(region,dict) or set(region)-{'text','bbox','type','role','level'}:raise ValueError('Invalid transcription region.')
                bb=region.get('bbox');text=region.get('text');typ=region.get('type','paragraph');role=region.get('role','body')
                if not isinstance(text,str) or not text.strip() or typ not in {'paragraph','heading','reference'} or role not in {'body','metadata','bibliography','abstract','keywords','caption','note','equation'}:raise ValueError('Transcribe literal visible text and its observed role.')
                if not isinstance(bb,list) or len(bb)!=4 or any(type(x) not in (int,float) or not __import__('math').isfinite(x) for x in bb) or not (0<=bb[0]<bb[2]<=width and 0<=bb[1]<bb[3]<=height):raise ValueError('Region must lie within the source image/page.')
                level=region.get('level',2)
                if type(level) is not int or not 1<=level<=6:raise ValueError('Heading level must be 1..6.')
                b=add_block(c,did,typ,{'page':pn,'bbox':bb,'transcription_evidence':f,'bbox_units':'PDF points; top-left' if src.suffix.lower()=='.pdf' else 'source image pixels; top-left'},[text],level=level,presentation={'role':role},structure={'semantic_role':role,'representation':'source-bound-host-agent-transcription'})
                created.append(b);blocks[b['id']]=b;lookup.update({u['id']:u for u in b['units']})
            for b in created:c['blocks'].remove(b)
            next_page=next((i for i,b in enumerate(c['blocks']) if b['source']['document_id']==did and b['source'].get('page',0)>pn),len(c['blocks']))
            c['blocks'][next_page:next_page]=created
            if src.suffix.lower()!='.pdf':
                # The input scan remains archived, rather than appearing again
                # as untranslated full-page prose beside its transcription.
                for b in existing:
                    if b.get('asset') and b['type']=='image':
                        c['blocks'].remove(b);c.setdefault('extraction_archive',[]).append({'reason':'source page transcribed by inspecting host agent','block':b,'evidence':evidence})
        elif kind=='transcribe-table':
            if set(op)-{'op','evidence_file','rows','header_rows','observation'}:raise ValueError('Unexpected table fields.')
            f=op.get('evidence_file');proposal=read(safe(r,f))
            if f not in evidence or proposal.get('kind')!='raster-table':raise ValueError('Inspect the source-bound table proposal first.')
            if proposal.get('block_id'):raise ValueError('Correct existing table cells instead of duplicating them.')
            if any(b.get('source',{}).get('ocr_evidence')==f for b in c['blocks']):raise ValueError('Source table is already transcribed.')
            rows=op.get('rows');header=op.get('header_rows',1)
            if not isinstance(rows,list) or not rows or any(not isinstance(row,list) or not row or any(not isinstance(cell,str) for cell in row) for row in rows):raise ValueError('Table transcription needs literal source cells, including empty strings.')
            if len({len(row) for row in rows})!=1 or type(header) is not int or not 0<=header<=len(rows):raise ValueError('Invalid source table grid.')
            cap=blocks.get(proposal.get('caption_block_id'))
            if cap is None:raise ValueError('Missing source table caption.')
            source=next((s for s in c['sources'] if s['id']==cap['source']['document_id']),None)
            if source is None:raise ValueError('Missing source table document.')
            if Path(source['file']).suffix.lower()=='.pdf':raise ValueError('PDF OCR/transcription is disabled; retain original table artwork.')
            if cap['source'].get('page')!=proposal.get('source_page'):raise ValueError('Table proposal and caption must refer to the same source page.')
            from translate import add_block
            b=add_block(c,cap['source']['document_id'],'table',{'page':proposal['source_page'],'bbox':proposal['bbox'],'ocr_evidence':f},[],rows=[],header_rows=header,caption_block_ids=[cap['id']],structure={'semantic_role':'table','representation':'source-bound-host-agent-grid'})
            for ri,row in enumerate(rows,1):
                ids=[]
                for ci,text in enumerate(row,1):
                    uid=f'{b["id"]}-R{ri:04d}C{ci:03d}';ids.append(uid);u={'id':uid,'source':text,'translations':{},'notes':[]};b['units'].append(u);lookup[uid]=u
                b['rows'].append(ids)
            c['blocks'].remove(b);c['blocks'].insert(c['blocks'].index(cap),b);blocks[b['id']]=b
        elif kind=='regroup-units':
            if set(op)-{'op','block_id','before_ids','groups','observation'}:raise ValueError('Unexpected regroup fields.')
            b=blocks.get(op.get('block_id'))
            if not b or b['type'] not in {'paragraph','heading','reference'} or op.get('before_ids')!=[u['id'] for u in b['units']]:raise ValueError('Regroup the exact current text block.')
            if any(u.get('translations') or u.get('alignment') for u in b['units']):raise ValueError('Regroup before translation.')
            groups=op.get('groups',[]);old=b['units']
            if not groups or any(not g or any(type(i) is not int for i in g) for g in groups) or [i for g in groups for i in g]!=list(range(len(old))):raise ValueError('Groups must cover every source unit once in order.')
            merged=[]
            for group in groups:
                u=copy.deepcopy(old[group[0]]);u['source']=' '.join(old[i]['source'] for i in group);u['source_segments']=[{'unit_id':old[i]['id'],'source':old[i]['source']} for i in group];merged.append(u)
            for u in old:lookup.pop(u['id'],None)
            b['units']=merged;lookup.update({u['id']:u for u in merged})
        elif kind=='order-blocks':
            if set(op)-{'op','document_id','page','before_ids','after_ids','observation'}:raise ValueError('Unexpected order fields.')
            positions=[i for i,b in enumerate(c['blocks']) if b['source']['document_id']==op.get('document_id') and b['source'].get('page')==op.get('page')]
            before=[c['blocks'][i]['id'] for i in positions];after=op.get('after_ids',[])
            if before!=op.get('before_ids') or len(after)!=len(set(after)) or set(after)!=set(before):raise ValueError('Reorder the exact page block set without omission.')
            for i,bid in zip(positions,after):c['blocks'][i]=blocks[bid]
        elif kind=='resolve-issue':
            if set(op)-{'op','issue_index','observation'}:raise ValueError('Unexpected issue fields.')
            i=op.get('issue_index')
            if not isinstance(i,int) or not 0<=i<len(c.get('issues',[])):raise ValueError('Unknown issue index.')
            issue=c['issues'][i]
            if issue.get('status')!='open':raise ValueError('Issue is already resolved.')
            issue.update(status='resolved',resolution=op['observation'],reviewer=packet['reviewer'],evidence=evidence)
        else:raise ValueError('Unsupported source-review operation: '+str(kind))
        changed.append(op)
    c.setdefault('extraction_corrections',[]).append({'operation':'host-agent-source-review','at':now(),'reviewer':packet['reviewer'],'before_source_hash':packet['source_hash'],'evidence':evidence,'operations':changed})
    from refinement import validate_blocks
    errors=validate_blocks(c)
    if errors:raise ValueError(str(errors))
    from structure_layout import write_map
    for source in c['sources']:
        if Path(source['file']).suffix.lower()=='.pdf':write_map(r,c,source)
    write(r/'content.json',c);return {'applied':len(changed),'source_hash':source_snap(m,c),'review_certified':False}

def run(a):
    print(json.dumps(apply(a.project,a.packet) if a.packet else {'task':str(prepare(a.project))},ensure_ascii=False))
