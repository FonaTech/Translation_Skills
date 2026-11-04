"""Reconstruct physical lines inside an explicitly verified PDF region.

Use only after inspecting the page: a region must contain one reading column.
This does not infer semantic reading order or rewrite source content.
"""
def physical_lines(page, bbox, tolerance=1.2):
    import fitz
    region=fitz.Rect(bbox)
    fragments=[]
    for block in page.get_text('dict',clip=region)['blocks']:
        for line in block.get('lines',[]):
            for span in line['spans']:
                text=span['text']
                if text.strip():
                    fragments.append({'x':span['bbox'][0], 'y':span.get('origin',(0,span['bbox'][3]))[1],
                                      'right':span['bbox'][2], 'text':text})
    rows=[]
    for span in sorted(fragments,key=lambda s:(s['y'],s['x'])):
        row=next((r for r in reversed(rows) if abs(r['y']-span['y'])<=tolerance),None)
        if row is None:
            row={'y':span['y'],'spans':[]};rows.append(row)
        row['spans'].append(span)
    result=[]
    for row in rows:
        parts=sorted(row['spans'],key=lambda s:s['x']);text='';right=None
        for s in parts:
            if right is not None and s['x']-right>.8 and text and not text.endswith(' ') and not s['text'].startswith(' '):text+=' '
            text+=s['text'];right=s['right']
        result.append({'x':parts[0]['x'],'y':row['y'],'text':text})
    return result
