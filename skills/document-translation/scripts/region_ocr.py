"""Local source-bound OCR proposals. Copyright Yufeng Zhan. MIT.

OCR is never semantic attestation. The host agent can transcribe the review
packet when no local OCR engine exists, without a service or special-case code.
"""
from pathlib import Path
import csv,io,json,shutil,subprocess,sys

def recognize(image, language='en-US'):
    from PIL import Image
    failure='Apple Vision unavailable on this host.'
    if sys.platform=='darwin' and shutil.which('swift'):
        try:
            proc=subprocess.run(['swift',str(Path(__file__).with_name('vision_ocr.swift')),str(image),language],capture_output=True,text=True,timeout=120)
            if proc.returncode==0:return {'engine':'apple-vision-cpu','items':json.loads(proc.stdout)}
            failure=proc.stderr[-1500:]
        except (subprocess.TimeoutExpired,ValueError) as error:failure=str(error)
    if shutil.which('tesseract'):
        proc=subprocess.run(['tesseract',str(image),'stdout','-l','eng' if language=='en-US' else language,'tsv'],capture_output=True,text=True,timeout=120,check=True)
        with Image.open(image) as im:w,h=im.size
        items=[]
        for row in csv.DictReader(io.StringIO(proc.stdout),delimiter='\t'):
            if not row.get('text','').strip():continue
            x,y,bw,bh=[float(row[k]) for k in ('left','top','width','height')]
            items.append({'text':row['text'],'confidence':float(row['conf'])/100,'bbox':[x/w,1-(y+bh)/h,bw/w,bh/h],'bbox_units':'normalized bottom-left'})
        return {'engine':'tesseract','items':items}
    return {'engine':'host-agent-required','items':[],'reason':failure}

def grid(items,box):
    """Group OCR boxes by measured baseline and recurring column centers."""
    converted=[];x0,y0,x1,y1=box
    for item in items:
        x,y,w,h=item['bbox'];bb=[x0+x*(x1-x0),y0+(1-y-h)*(y1-y0),x0+(x+w)*(x1-x0),y0+(1-y)*(y1-y0)]
        converted.append({**item,'bbox':bb,'bbox_units':'PDF page points; top-left'})
    bands=[]
    for item in sorted(converted,key=lambda x:((x['bbox'][1]+x['bbox'][3])/2,x['bbox'][0])):
        b=item['bbox'];cy=(b[1]+b[3])/2
        match=next((row for row in bands if abs(cy-sum((r['bbox'][1]+r['bbox'][3])/2 for r in row)/len(row))<max(2,(b[3]-b[1])*.6)),None)
        if match is None:bands.append([item])
        else:match.append(item)
    for row in bands:row.sort(key=lambda x:x['bbox'][0])
    if not bands:return [],converted
    anchor=max(bands,key=len);centers=[(i['bbox'][0]+i['bbox'][2])/2 for i in anchor]
    rows=[]
    for band in bands:
        cells=[[] for _ in anchor]
        for item in band:cells[min(range(len(centers)),key=lambda i:abs((item['bbox'][0]+item['bbox'][2])/2-centers[i]))].append(item)
        rows.append([{'text':' '.join(i['text'] for i in cell),'evidence':cell} for cell in cells])
    return rows,converted

def recover_tables(root,content,did,page,add_block):
    import fitz,re
    from vector_assets import visible_rasters
    from translate import write,sha
    root=Path(root);blocks=[b for b in content['blocks'] if b['source']['document_id']==did and b['source'].get('page')==page.number+1]
    captions=[b for b in blocks if b.get('presentation',{}).get('role')=='caption' and re.match(r'^\s*(?:table|表)\s*(?:[IVX]+|\d+)', ' '.join(u['source'] for u in b.get('units',[])),re.I)]
    boxes=[];records=[]
    for cap in captions:
        cb=fitz.Rect(cap['source']['bbox']);candidates=[]
        for item in visible_rasters(page)['regions']:
            bb=fitz.Rect(item['bbox'])
            if -8<=cb.y0-bb.y1<=30 and max(0,min(cb.x1,bb.x1)-max(cb.x0,bb.x0))/max(1,min(cb.width,bb.width))>.7:candidates.append(bb)
        if not candidates:continue
        bb=min(candidates,key=lambda b:abs(cb.y0-b.y1));boxes.append(list(bb))
        if any(b['type']=='table' and fitz.Rect(b['source']['bbox']).intersects(bb) for b in blocks):continue
        stem=root/'reports/region-ocr'/f'{did}-p{page.number+1:04d}-{cap["id"]}';stem.parent.mkdir(parents=True,exist_ok=True)
        image=stem.with_suffix('.png');page.get_pixmap(matrix=fitz.Matrix(4,4),clip=bb,alpha=False).save(image)
        result=recognize(image);rows,items=grid(result['items'],list(bb))
        evidence={'schema_version':'1.0.2','kind':'raster-table','caption_block_id':cap['id'],'bbox':list(bb),'source_page':page.number+1,'image':image.relative_to(root).as_posix(),'image_sha256':sha(image),'engine':result['engine'],'items':items,'rows':rows,'review_status':'unreviewed','reason':result.get('reason')}
        write(stem.with_suffix('.json'),evidence)
        if len(rows)>=2 and len(rows[0])>=2:
            block=add_block(content,did,'table',{'page':page.number+1,'bbox':list(bb),'ocr_evidence':stem.with_suffix('.json').relative_to(root).as_posix()},[],rows=[],header_rows=1,caption_block_ids=[cap['id']],structure={'semantic_role':'table','representation':'source-bound-ocr-grid','review_required':True})
            for ri,row in enumerate(rows,1):
                ids=[]
                for ci,cell in enumerate(row,1):
                    uid=f'{block["id"]}-R{ri:04d}C{ci:03d}';ids.append(uid);block['units'].append({'id':uid,'source':cell['text'],'translations':{},'notes':[],'ocr_evidence':cell['evidence']})
                block['rows'].append(ids)
            content['blocks'].remove(block);content['blocks'].insert(content['blocks'].index(cap),block);evidence['block_id']=block['id'];write(stem.with_suffix('.json'),evidence)
        else:evidence['next_action']='host agent transcribes measured source table through source-review packet';write(stem.with_suffix('.json'),evidence)
        content['issues'].append({'document_id':did,'page':page.number+1,'code':'region-ocr-review','status':'open','evidence':stem.with_suffix('.json').relative_to(root).as_posix(),'message':'Verify every visible OCR cell against its source crop; missing engine routes to current host agent.'});records.append(evidence)
    return boxes,records
