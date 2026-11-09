"""Render model proposals on a source page, without using annotation truth.
Copyright 2026 Yufeng Zhan. MIT. Source content keeps its own rights.
"""
from pathlib import Path
import json, math

def render_overlay(page, blocks, proposals, output, scale=1.7):
    import fitz
    from PIL import Image, ImageDraw, ImageFont
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
    source=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
    header=76;canvas=Image.new('RGB',(source.width,source.height+header),'#f3f6fa');canvas.paste(source,(0,header))
    draw=ImageDraw.Draw(canvas)
    try:font=ImageFont.truetype('Arial.ttf',15);small=ImageFont.truetype('Arial.ttf',13)
    except OSError:font=ImageFont.load_default(size=15);small=ImageFont.load_default(size=13)
    draw.text((16,10),'AUTOMATIC SOURCE REGION PROPOSALS | page '+str(page.number+1),font=font,fill='#172b46')
    draw.text((16,36),'BLUE: linked artwork   GREEN: caption   ORANGE: unbound artwork   ARROW: predicted link',font=small,fill='#334155')
    byid={b['id']:b for b in blocks};ledger=[]
    def coords(bounds):
        r=fitz.Rect(bounds)*page.rotation_matrix
        return [r.x0*scale,r.y0*scale+header,r.x1*scale,r.y1*scale+header]
    def tag(box,label,color):
        x,y=box[:2];w=draw.textlength(label,font=small)+10
        y=max(header,y-20);x=max(0,min(x,canvas.width-w))
        draw.rectangle((x,y,x+w,y+19),fill=color);draw.text((x+5,y+1),label,font=small,fill='white')
    for b in blocks:
        if b.get('presentation',{}).get('role')!='caption' or not b.get('source',{}).get('bbox'):continue
        box=coords(b['source']['bbox']);draw.rectangle(box,outline='#15803d',width=3);tag(box,'CAP '+b['id'],'#15803d')
    for n,p in enumerate(proposals,1):
        box=coords(p['bbox']);linked=bool(p.get('caption_block_ids'));color='#2563eb' if linked else '#c2670a'
        draw.rectangle(box,outline=color,width=4);tag(box,('FIG ' if linked else 'ART ')+str(n),color)
        for cid in p.get('caption_block_ids',[]):
            if cid not in byid:raise ValueError('Unknown caption ID: '+cid)
            cap=coords(byid[cid]['source']['bbox']);start=((box[0]+box[2])/2,box[3]);end=((cap[0]+cap[2])/2,cap[1])
            draw.line((start,end),fill=color,width=3)
            angle=math.atan2(end[1]-start[1],end[0]-start[0]);points=[end]
            for delta in [-.48,.48]:points.append((end[0]-12*math.cos(angle+delta),end[1]-12*math.sin(angle+delta)))
            draw.polygon(points,fill=color)
        ledger.append({'number':n,'bbox':p['bbox'],'caption_block_ids':p.get('caption_block_ids',[]),'association_routes':p.get('association_routes',[]),'confidence':p.get('confidence'),'calibrated':False})
    canvas.save(output)
    result={'page':page.number+1,'source_page_size':[page.rect.width,page.rect.height],'scale':scale,'header_pixels':header,'proposal_source':'parser output only; no truth coordinates','regions':ledger,'review_status':'unreviewed'}
    output.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
