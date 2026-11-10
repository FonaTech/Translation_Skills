"""Source-constrained native table cells after learned row classification.

Never infer cell contents. Require a captioned source rectangle, recurring
separate text columns and a complete, unique row assignment. Mathematical
cells retain their isolated source artwork; prose cells remain translatable.
Copyright 2026 Yufeng Zhan. MIT.
"""
import re
import statistics

REVISION = '1.0.3-native-table-cells-2'


def ruled_grid(page, members, box):
    if __package__:
        from .structure_table_grid import ruled_grid as decode
    else:
        from structure_table_grid import ruled_grid as decode
    return decode(page,members,box)


def groups(page, rows, decisions):
    if __package__:
        from .source_structure import captioned_table_boxes, text_baseline, union
    else:
        from source_structure import captioned_table_boxes, text_baseline, union
    result=[];claimed=set()
    for box in captioned_table_boxes(page):
        members=[r for r in rows if r['id'] not in claimed and
                 box[0]-.5<=r['bbox'][0] and r['bbox'][2]<=box[2]+.5 and
                 box[1]-.5<=r['bbox'][1] and r['bbox'][3]<=box[3]+.5]
        if any(r not in members and box[0]<=(r['bbox'][0]+r['bbox'][2])/2<=box[2] and
               box[1]<=(r['bbox'][1]+r['bbox'][3])/2<=box[3] for r in rows):continue
        if len(members)<6 or sum(decisions[r['id']]['assigned_role']=='table' for r in members)<len(members)*.8:continue
        ruled=ruled_grid(page,members,box)
        if ruled:
            result.append({'id':'table-'+members[0]['id'],'kind':'table','representation':'source-table-cells',
                           'bbox':box,'members':members,**ruled})
            claimed.update(r['id'] for r in members)
            continue
        # A rejected ruled table cannot silently enter the weaker decoder.
        if any(box[1]-.8<=y<=box[3]+.8 and min(right,box[2])-max(left,box[0])>=(box[2]-box[0])*.95
               for left,y,right in page.get('fraction_rules',[])):continue
        size=max(1,statistics.median(r['size'] for r in members))
        # A repeated empty vertical gutter must separate all cell text boxes.
        # Script fragments can introduce additional left edges, but cannot
        # introduce a gutter through a longer expression or wrapped cell.
        cuts=[]
        edges=sorted({x for r in members for x in [r['bbox'][0],r['bbox'][2]]})
        for left,right in zip(edges,edges[1:]):
            if right-left<size*1.1:continue
            cut=(left+right)/2
            if any(r['bbox'][0]<cut<r['bbox'][2] for r in members):continue
            a=[r for r in members if r['bbox'][2]<=cut];b=[r for r in members if r['bbox'][0]>=cut]
            if len(a)>=3 and len(b)>=3:cuts.append((right-left,cut))
        if not cuts:continue
        boundaries=[box[0]]+sorted(c for _,c in cuts)+[box[2]]
        columns=[[r for r in members if boundaries[i]<=sum(r['bbox'][::2])/2<boundaries[i+1]]
                 for i in range(len(boundaries)-1)]
        if any(len(c)<3 for c in columns):continue
        # Only a repeated one-line stub column establishes row boundaries.
        # A wrapped/merged stub is ambiguous and remains explicitly unresolved.
        stub=sorted(columns[0],key=text_baseline)
        if any(text_baseline(b)-text_baseline(a)<size*.8 for a,b in zip(stub,stub[1:])):continue
        # Symbol fonts can place the text origin near the top of a radical.
        # Physical glyph rectangles, rather than that font-specific baseline,
        # keep a radical/raised exponent in the same row as its source cell.
        starts=[r['bbox'][1]-size*.25 for r in stub]
        cells=[[[] for _ in columns] for _ in stub]
        for ci,column in enumerate(columns):
            for row in column:
                y=(row['bbox'][1]+row['bbox'][3])/2
                ri=max((i for i,start in enumerate(starts) if y>=start),default=0)
                cells[ri][ci].append(row)
        # Header labels must be separate, aligned native source objects.
        if any(not c or abs(text_baseline(c[0])-text_baseline(stub[0]))>size*.7 for c in cells[0]):continue
        flat=[r['id'] for row in cells for cell in row for r in cell]
        if len(flat)!=len(set(flat)) or set(flat)!={r['id'] for r in members}:continue
        grid=[]
        for row in cells:
            grid.append([{'line_ids':[r['id'] for r in sorted(cell,key=lambda x:(round(text_baseline(x)/max(1,size*.4)),x['bbox'][0]))],
                          'bbox':union([r['bbox'] for r in cell]) if cell else None}
                         for cell in row])
        result.append({'id':'table-'+members[0]['id'],'kind':'table','representation':'source-table-cells',
                       'bbox':box,'members':members,'cells':grid,'header_rows':1,
                       'column_widths':[b-a for a,b in zip(boundaries,boundaries[1:])],
                       'evidence':{'revision':REVISION,'method':'learned-table-rows-with-empty-source-gutters-and-stub-baselines',
                                   'semantic_certification':False}})
        claimed.update(flat)
    return result


def unresolved_groups(page, rows, decisions, resolved):
    """Own a rejected table as one artwork region, never independent prose."""
    if __package__:
        from .source_structure import captioned_table_boxes
    else:
        from source_structure import captioned_table_boxes
    claimed={r['id'] for region in resolved for r in region['members']}
    result=[]
    for box in captioned_table_boxes(page):
        members=[r for r in rows if box[0]-.5<=r['bbox'][0] and r['bbox'][2]<=box[2]+.5 and
                 box[1]-.5<=r['bbox'][1] and r['bbox'][3]<=box[3]+.5]
        if len(members)<6 or any(r['id'] in claimed for r in members):continue
        if sum(decisions[r['id']]['assigned_role']=='table' for r in members)<len(members)*.8:continue
        result.append({'id':'table-artwork-'+members[0]['id'],'kind':'table','representation':'source-table-artwork',
                       'bbox':box,'members':members})
        claimed.update(r['id'] for r in members)
    return result


def append(root, content, document_id, source, region, page, source_file, add_block):
    from pathlib import Path
    import fitz
    if __package__:
        from . import math_protection as math
    else:
        import math_protection as math
    if __package__:
        from .source_structure import union
    else:
        from source_structure import union
    if __package__:
        from .translate import sha
    else:
        from translate import sha
    if __package__:
        from .vector_assets import export_crop
    else:
        from vector_assets import export_crop
    if __package__:
        from .structure_ingest import formula_crop_exclusions
    else:
        from structure_ingest import formula_crop_exclusions
    block=add_block(content,document_id,'table',source,[],rows=[],header_rows=region['header_rows'],
        column_widths=region['column_widths'],typography=region['typography'],
        presentation={'role':'body'},structure={'experimental':True,'review_required':True,
            'semantic_role':'table','region_id':region['region_id'],'representation':'source-table-cells',
            'cell_evidence':region['cell_evidence']})
    lookup={r['id']:r for r in page['lines']}
    for ri,row in enumerate(region['cells']):
        ids=[]
        for ci,cell in enumerate(row):
            if cell.get('covered_by') is not None:
                ids.append(None);continue
            uid=f'{block["id"]}-R{ri+1:04d}C{ci+1:03d}';ids.append(uid)
            native=[lookup[lid] for lid in cell['line_ids']]
            text='\n'.join(math.line_candidates(r)[0].strip() for r in native)
            unit={'id':uid,'source':text,'translations':{},'notes':[],
                  'source_cell':{'row':ri+1,'column':ci+1,**cell}}
            block['units'].append(unit)
            if not text:continue
            # A conditional function definition is mathematical notation too.
            # Retain its source operators/connectives as part of the complete
            # isolated expression. Ordinary descriptive prose stays available
            # to the translation model, with its inline notation fenced below.
            words=re.findall(r'[A-Za-z]{3,}',text)
            operators=math.FUNCTIONS|{'if','then','else','otherwise','and','or'}
            pure=(ri>=block['header_rows'] and
                  (bool(re.fullmatch(r'[\d\s.,+−-]+',text)) or
                   not any(w.casefold() not in operators for w in words) and
                   any(math.SYMBOL.search(r['text']) or math.MATHFONT.search(r['font']) for r in native)))
            if pure:
                math.attach(unit,[{'start':0,'end':len(text),'kind':'formula','evidence':['isolated-source-table-cell']}])
                record=unit['protected_math'][0]
                box=fitz.Rect(cell['bbox'])
                owned=[lid for r in native for lid in r.get('native_line_ids',[r['id']])]
                crop_region={'bbox':list(box),'native_line_ids':owned}
                decisions={'line_roles':[{'line_id':r['id'],'assigned_role':'body','predicted_role':'table'} for r in page['lines']]}
                exclusions=formula_crop_exclusions(page,crop_region,decisions,box)
                with fitz.open(source_file) as document:
                    original=document[page['page']-1]
                    crop=export_crop(original,box,Path(root)/'assets'/('table-formula-'+uid),scale=3,native_text_exclusions=exclusions)
                record.update(page=page['page'],bbox=list(box),body_size_pt=statistics.median(r['size'] for r in native),
                    em_width=box.width/statistics.median(r['size'] for r in native),
                    em_height=box.height/statistics.median(r['size'] for r in native),
                    representation='isolated-source-table-formula',native_text_exclusions=exclusions,
                    asset=crop['vector'].relative_to(root).as_posix(),
                    asset_sha256=sha(crop['vector']),asset_fallback=crop['fallback'].relative_to(root).as_posix(),
                    asset_fallback_sha256=sha(crop['fallback']))
            else:
                subregion={'text':text,'line_ids':cell['line_ids']}
                math.attach_block({**block,'units':[unit]},subregion,page,root,source_file)
        block['rows'].append(ids)
    return block


def append_artwork(root, content, document_id, source, region, page, source_file, add_block):
    """Preserve complete ambiguous table, native transcript and exact ownership."""
    import json
    import fitz
    from pathlib import Path
    if __package__:
        from .vector_assets import export_crop
        from .translate import sha
    else:
        from vector_assets import export_crop
        from translate import sha
    root=Path(root);stem=root/'assets'/('source-table-'+region['region_id'])
    with fitz.open(source_file) as doc:
        crop=export_crop(doc[page['page']-1],fitz.Rect(region['bbox']),stem,scale=3)
    native=[r for r in page['lines'] if r['id'] in set(region['line_ids'])]
    evidence=root/'reports/native-tables'/(region['region_id']+'.json');evidence.parent.mkdir(parents=True,exist_ok=True)
    evidence.write_text(json.dumps({'revision':REVISION,'source':source,'native_rows':native,
        'disposition':'artwork-retained; cell topology unresolved; not translated','ocr_calls':0},ensure_ascii=False,indent=2),encoding='utf-8')
    block=add_block(content,document_id,'image',source,[],
        asset=crop['vector'].relative_to(root).as_posix(),asset_sha256=sha(crop['vector']),
        asset_fallback=crop['fallback'].relative_to(root).as_posix(),asset_fallback_sha256=sha(crop['fallback']),
        asset_metadata=crop['metadata'],width_mm=min(185,(region['bbox'][2]-region['bbox'][0])*25.4/72),
        label_policy='retained-original',source_table_fallback=True,native_spatial_transcript=region['text'],
        structure={'semantic_role':'table','region_id':region['region_id'],'representation':'source-table-artwork',
                   'native_text_archive':evidence.relative_to(root).as_posix(),'review_required':True})
    content['issues'].append({'document_id':document_id,'block_id':block['id'],'page':page['page'],
        'code':'source-table-topology-unresolved','status':'open','evidence':evidence.relative_to(root).as_posix(),
        'message':'Complete table artwork and native rows retained. Ambiguous cell topology is not flattened into prose or claimed translated.'})
    return block
