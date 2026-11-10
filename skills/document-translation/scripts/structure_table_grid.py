"""Constrained native table topology, with numerical cell-link inference.

Source rules, repeated columns and complete native ownership are hard gates.
The classifier can join wrapped cells, never create or rewrite their contents.
Copyright 2026 Yufeng Zhan. MIT.
"""
import statistics

REVISION = '1.0.3-constrained-table-grid-3'


def ruled_grid(page, members, box):
    if __package__:
        from .source_structure import text_baseline, union
        from . import table_learning
    else:
        from source_structure import text_baseline, union
        import table_learning
    size=max(1,statistics.median(r['size'] for r in members))
    cx=lambda r:sum(r['bbox'][::2])/2
    cy=lambda r:sum(r['bbox'][1::2])/2
    native_rules=[(left,y,right) for left,y,right in page.get('fraction_rules',[])
                  if box[1]-.8<=y<=box[3]+.8 and
                  min(right,box[2])-max(left,box[0])>(box[2]-box[0])*.35]
    rules=sorted({round(y,2) for left,y,right in native_rules
                  if min(right,box[2])-max(left,box[0])>=(box[2]-box[0])*.95})
    if len(rules)<3:return None
    # Partial row separators imply locally merged hierarchical sections. The
    # simple rectangular decoder must not mislabel them as ordinary data rows.
    if any(not any(abs(y-full)<.8 for full in rules) for _,y,_ in native_rules):return None
    divider=rules[1]
    headers=[r for r in members if cy(r)<divider]
    data=[r for r in members if cy(r)>=divider]
    if not headers or not data:return None
    def bands(records):
        result=[]
        for row in sorted(records,key=lambda r:(text_baseline(r),r['bbox'][0])):
            if result and abs(text_baseline(row)-statistics.median(text_baseline(x) for x in result[-1]))<=size*.42:
                result[-1].append(row)
            else:result.append([row])
        return result
    db=bands(data)
    dense=max(db,key=len);anchors=sorted(cx(r) for r in dense)
    if len(anchors)<2 or any(b-a<size*1.5 for a,b in zip(anchors,anchors[1:])):return None
    supporting=[band for band in db if len(band)==len(anchors) and
                all(abs(cx(r)-a)<=size*.9 for r,a in zip(sorted(band,key=cx),anchors))]
    recurring=len(supporting)>=2
    if recurring:
        anchors=[statistics.median(cx(sorted(band,key=cx)[i]) for band in supporting) for i in range(len(anchors))]
        boundaries=[box[0]]+[(a+b)/2 for a,b in zip(anchors,anchors[1:])]+[box[2]]
    else:
        edges=sorted({x for r in members for x in (r['bbox'][0],r['bbox'][2])})
        cuts=[(a+b)/2 for a,b in zip(edges,edges[1:]) if b-a>=size*1.1 and
              not any(r['bbox'][0]<(a+b)/2<r['bbox'][2] for r in members)]
        boundaries=[box[0]]+cuts+[box[2]]
        anchors=[(a+b)/2 for a,b in zip(boundaries,boundaries[1:])]
    count=len(anchors)
    if not 2<=count<=20:return None
    def column(row):
        return next((i for i,(a,b) in enumerate(zip(boundaries,boundaries[1:])) if a<=cx(row)<=b),None)
    # Run the learned head on actual adjacent source objects in every column.
    pairs=[]
    for ci in range(count):
        for records in (headers,data):
            col=sorted((r for r in records if column(r)==ci),key=text_baseline)
            pairs.extend((a,b) for a,b in zip(col,col[1:])
                         if .3*size<text_baseline(b)-text_baseline(a)<3*size)
    predicted,inference=table_learning.predict(pairs,page)
    if pairs and inference is None:return None
    accepted={(d['from'],d['to']):d['accepted'] for d in predicted}
    if recurring:
        value_bands=[]
        for band in db:
            cols=[column(r) for r in band]
            values=[r for r in band if column(r)!=0]
            if len(values)>=max(1,count-1) and len(cols)==len(set(cols)):
                value_bands.append(band)
        if len(value_bands)<2:return None
        logical=[]
        for band in value_bands:
            if logical:
                previous=logical[-1][-1]
                am={column(r):r for r in previous};bm={column(r):r for r in band}
                shared=set(am)&set(bm)-{0}
                join=(len(shared)>=max(1,count-1) and
                      all(accepted.get((am[c]['id'],bm[c]['id']),False) for c in shared))
            else:join=False
            if join:logical[-1].append(band)
            else:logical.append([band])
        centers=[statistics.median(cy(r) for band in group for r in band if column(r)!=0) for group in logical]
        row_edges=[box[1],divider]+[(a+b)/2 for a,b in zip(centers,centers[1:])]+[box[3]]
    else:
        row_edges=rules
        for top,bottom in zip(row_edges[1:],row_edges[2:]):
            stub=[r for r in data if column(r)==0 and top<=cy(r)<bottom]
            if len(stub)>1:return None
    header_rows=1
    grid=[[{'line_ids':[],'bbox':None} for _ in range(count)] for _ in range(len(row_edges)-1)]
    hb=bands(headers);lower=hb[-1]
    child_cols=sorted(column(r) for r in lower)
    parent=[]
    if recurring and len(lower)>=3 and None not in child_cols and len(set(child_cols))==len(child_cols) and child_cols==list(range(min(child_cols),max(child_cols)+1)):
        center=(anchors[child_cols[0]]+anchors[child_cols[-1]])/2
        parent=[r for r in headers if r not in lower and abs(cx(r)-center)<size*.6 and
                r['bbox'][1]<min(x['bbox'][1] for x in lower)-size*.4]
    if parent:
        header_rows=2;grid.insert(1,[{'line_ids':[],'bbox':None} for _ in range(count)])
    def put(ri,left,right,records,rowspan=1):
        if any(grid[rr][cc]['line_ids'] or grid[rr][cc].get('covered_by') is not None
               for rr in range(ri,ri+rowspan) for cc in range(left,right+1)):return False
        grid[ri][left].update(line_ids=[r['id'] for r in sorted(records,key=lambda r:(text_baseline(r),r['bbox'][0]))],
                             bbox=union([r['bbox'] for r in records]),colspan=right-left+1,rowspan=rowspan)
        for rr in range(ri,ri+rowspan):
            for cc in range(left,right+1):
                if (rr,cc)!=(ri,left):grid[rr][cc]['covered_by']=[ri,left]
        return True
    if parent:
        if not put(0,child_cols[0],child_cols[-1],parent):return None
        for row in lower:
            if not put(1,column(row),column(row),[row]):return None
    pending=[r for r in headers if not parent or r not in parent and r not in lower]
    header_groups={}
    for row in pending:
        ci=column(row)
        if ci is None:return None
        bb=row['bbox'];span=(ci,ci)
        # A centered parent may be narrower than the space between its children.
        # Score all contiguous source-supported spans, rather than merging those
        # children into a single data column to fit the parent text width.
        if recurring and not parent:
            candidates=[]
            for left in range(count):
                for right in range(left,count):
                    if boundaries[left]-size*1.5<=bb[0] and bb[2]<=boundaries[right+1]+size*1.5:
                        score=abs(cx(row)-(boundaries[left]+boundaries[right+1])/2)/size+.05*(right-left)
                        candidates.append((score,left,right))
            if candidates:
                score,left,right=min(candidates)
                if score<1.2:span=(left,right)
        if bb[0]<boundaries[span[0]]-size*1.5 or bb[2]>boundaries[span[1]+1]+size*1.5:return None
        header_groups.setdefault(span,[]).append(row)
    for (left,right),records in header_groups.items():
        if not put(0,left,right,records,rowspan=header_rows):return None
    for native in data:
        ci=column(native);ri=next((i for i,(top,bottom) in enumerate(zip(row_edges,row_edges[1:])) if top<=cy(native)<bottom),None)
        if ci is None or ri is None:return None
        ri+=header_rows-1;bb=native['bbox']
        if bb[0]<boundaries[ci]-.6 or bb[2]>boundaries[ci+1]+.6:return None
        cell=grid[ri][ci]
        if cell.get('covered_by') is not None:return None
        cell['line_ids'].append(native['id']);cell['bbox']=union([cell['bbox'],bb]) if cell['bbox'] else list(bb)
    lookup={r['id']:r for r in members}
    for row in grid[header_rows:]:
        for cell in row:
            native=sorted((lookup[lid] for lid in cell['line_ids']),key=text_baseline)
            if recurring and any(text_baseline(b)-text_baseline(a)>.3*size and not accepted.get((a['id'],b['id']),False)
                                 for a,b in zip(native,native[1:])):return None
    flat=[lid for row in grid for cell in row for lid in cell['line_ids']]
    if len(flat)!=len(set(flat)) or set(flat)!={r['id'] for r in members}:return None
    return {'cells':grid,'header_rows':header_rows,'column_widths':[b-a for a,b in zip(boundaries,boundaries[1:])],
            'evidence':{'revision':REVISION,'method':'numerical-cell-links-constrained-by-native-rules-and-columns',
                        'horizontal_rules':rules,'row_edges':row_edges,'column_edges':boundaries,
                        'supporting_dense_rows':len(supporting),'cell_link_inference':inference,
                        'cell_link_decisions':predicted,'semantic_certification':False}}
