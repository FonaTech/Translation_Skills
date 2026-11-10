"""Validate merged-cell ownership independently of the table assembler. MIT."""


def errors(block):
    rows=block.get('rows',[]);units={u['id']:u for u in block.get('units',[])}
    if not any(v is None for row in rows for v in row) and not any(
        any(u.get('source_cell',{}).get(k,1)!=1 for k in ['colspan','rowspan']) for u in units.values()):return []
    problem=lambda reason:[{'code':'table-cell-topology','block':block['id'],'reason':reason}]
    width=max(map(len,rows),default=0);occupied={}
    if not rows or any(len(row)!=width for row in rows):return problem('Merged-cell grid must be rectangular.')
    header=block.get('header_rows',1)
    for ri,row in enumerate(rows):
        for ci,uid in enumerate(row):
            if uid is None:continue
            if uid not in units:return problem('Unknown owning unit.')
            cell=units[uid].get('source_cell',{})
            rs,cs=cell.get('rowspan',1),cell.get('colspan',1)
            if any(type(v) is not int or v<1 for v in (rs,cs)):return problem('Invalid span.')
            if ri+rs>len(rows) or ci+cs>width:return problem('Span exceeds grid bounds.')
            if ri<header<ri+rs:return problem('A cell crosses header/data ownership.')
            for rr in range(ri,ri+rs):
                for cc in range(ci,ci+cs):
                    if (rr,cc) in occupied:return problem('Overlapping cell owners.')
                    if (rr,cc)!=(ri,ci) and rows[rr][cc] is not None:return problem('Covered location must have no independent unit.')
                    occupied[(rr,cc)]=uid
    if len(occupied)!=len(rows)*width:return problem('Unowned covered location.')
    return []
