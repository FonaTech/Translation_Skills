"""Source-bound table artwork and legacy raster-only OCR helpers. MIT.

PDF processing never calls an OCR engine. Preserve native cells or complete
source artwork and report unavailable text. Copyright 2026 Yufeng Zhan.
"""
from pathlib import Path
import csv,io,json,shutil,subprocess,sys

def recognize(image, language='en-US'):
    from PIL import Image
    failure='Apple Vision unavailable on this host.'
    if sys.platform=='darwin' and shutil.which('swift'):
        try:
            proc=subprocess.run(['swift',str(Path(__file__).with_name('vision_ocr.swift')),str(image),language],capture_output=True,text=True,timeout=120, encoding='utf-8')
            if proc.returncode==0:return {'engine':'apple-vision-cpu','items':json.loads(proc.stdout)}
            failure=proc.stderr[-1500:]
        except (subprocess.TimeoutExpired,ValueError) as error:failure=str(error)
    if shutil.which('tesseract'):
        proc=subprocess.run(['tesseract',str(image),'stdout','-l','eng' if language=='en-US' else language,'tsv'],capture_output=True,text=True,timeout=120,check=True, encoding='utf-8')
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

def outlined_table_candidates(page):
    """Caption binding still required; outlined glyphs are not native cells.

    Measure stroke tracks, excluding filled font outlines. Both row and column
    rules must cover a substantial part of the same vector envelope. Native
    tables remain on their existing parser path instead of being duplicated.
    """
    import fitz
    from vector_assets import inventory
    drawings=page.get_drawings();found=[]
    def tracks(segments):
        groups=[]
        for coordinate,start,end in sorted(segments):
            group=next((g for g in groups if abs(g[0]-coordinate)<=.7),None)
            if group is None:groups.append([coordinate,[(start,end)]])
            else:group[1].append((start,end))
        result=[]
        for coordinate,intervals in groups:
            total=0;last=-float('inf')
            for start,end in sorted(intervals):
                total+=max(0,end-max(last,start));last=max(last,end)
            result.append((coordinate,total))
        return result
    for region in inventory(page)['regions']:
        box=fitz.Rect(region['bbox']) & page.rect
        if box.width<40 or box.height<25 or box.get_area()>page.rect.get_area()*.85:continue
        # Outlined tables have no native text to translate. Do not silently
        # overlay an OCR copy on native text already represented by the IR.
        if len(page.get_text('text',clip=box).strip())>=8:continue
        horizontal=[];vertical=[]
        for drawing in drawings:
            for item in drawing.get('items',[]):
                if item[0]=='l' and drawing.get('fill') is None:
                    a,b=item[1:3]
                    if not (box+(-1,-1,1,1)).contains(a) or not (box+(-1,-1,1,1)).contains(b):continue
                    if abs(a.y-b.y)<.5 and abs(a.x-b.x)>=max(12,box.width*.1):
                        horizontal.append(((a.y+b.y)/2,min(a.x,b.x),max(a.x,b.x)))
                    if abs(a.x-b.x)<.5 and abs(a.y-b.y)>=4:
                        vertical.append(((a.x+b.x)/2,min(a.y,b.y),max(a.y,b.y)))
                elif item[0]=='re':
                    rect=fitz.Rect(item[1])
                    if not (box+(-1,-1,1,1)).contains(rect):continue
                    if rect.height<=1 and rect.width>=max(12,box.width*.1):
                        horizontal.append(((rect.y0+rect.y1)/2,rect.x0,rect.x1))
                    if rect.width<=1 and rect.height>=4:
                        vertical.append(((rect.x0+rect.x1)/2,rect.y0,rect.y1))
        h=[x for x,n in tracks(horizontal) if n>=box.width*.65]
        v=[x for x,n in tracks(vertical) if n>=box.height*.4]
        if len(h)>=3 and len(v)>=2 and max(h)-min(h)>=box.height*.6:
            found.append({'bbox':list(box+(-.5,-.5,.5,.5) & page.rect),
                          'source_kind':'outlined-vector-table','horizontal_tracks':len(h),'vertical_tracks':len(v)})
    return found


def grid_validation(rows,items):
    """Reject a flattened grid when source row/column ownership is ambiguous.

    OCR confidence measures recognition, not cell ownership. Empty cells may
    be intentional or vertically merged: retain artwork instead of filling or
    moving those values. The OCR proposal remains available in its evidence.
    """
    reasons=[]
    if len(rows)<2 or not rows or len(rows[0])<2:reasons.append('insufficient-grid')
    elif any(len(row)!=len(rows[0]) for row in rows):reasons.append('ragged-grid')
    else:
        if any(not cell['text'].strip() for row in rows for cell in row):
            reasons.append('empty-cell-or-merged-cell-ownership-unresolved')
        if any(len(cell.get('evidence',[]))>1 for row in rows for cell in row):
            reasons.append('multi-item-cell-needs-source-grid-validation')
        if any(float(item.get('confidence',0))<.97 for item in items):
            reasons.append('low-confidence-cell-text')
        for row in rows:
            baselines=[(c['evidence'][0]['bbox'][1]+c['evidence'][0]['bbox'][3])/2 for c in row if c.get('evidence')]
            heights=[c['evidence'][0]['bbox'][3]-c['evidence'][0]['bbox'][1] for c in row if c.get('evidence')]
            if baselines and max(baselines)-min(baselines)>max(1,min(heights)*.35):
                reasons.append('row-baseline-disagreement');break
    return {'pass':not reasons,'reasons':reasons,'semantic_verification':False}


def retain_pdf_tables(root,content,did,page,add_block):
    import fitz,re
    from vector_assets import visible_rasters
    from translate import write,sha
    root=Path(root);blocks=[b for b in content['blocks'] if b['source']['document_id']==did and b['source'].get('page')==page.number+1]
    captions=[b for b in blocks if b.get('presentation',{}).get('role')=='caption' and re.match(r'^\s*(?:table|表)\s*(?:[IVX]+|\d+)', ' '.join(u['source'] for u in b.get('units',[])),re.I)]
    boxes=[];records=[]
    artworks=[{**item,'source_kind':'raster-table'} for item in visible_rasters(page)['regions']]
    artworks+=outlined_table_candidates(page) if captions else []
    for cap in captions:
        cb=fitz.Rect(cap['source']['bbox']);candidates=[]
        for item in artworks:
            bb=fitz.Rect(item['bbox'])
            overlap=max(0,min(cb.x1,bb.x1)-max(cb.x0,bb.x0))/max(1,min(cb.width,bb.width))
            gap=min(abs(cb.y0-bb.y1),abs(bb.y0-cb.y1))
            above=-8<=cb.y0-bb.y1<=30
            below=0<=bb.y0-cb.y1<=75
            if overlap<=.7 or not (above or below):continue
            if any((fitz.Rect(owned)&bb).get_area()/max(1,bb.get_area())>.9 for owned in boxes):continue
            # A nearby caption must not reach across unrelated prose/captions.
            low,high=(cb.y1,bb.y0) if below else (bb.y1,cb.y0)
            barriers=[b for b in blocks if b is not cap and b.get('units') and b['source'].get('bbox') and
                low+.5<fitz.Rect(b['source']['bbox']).y0 and fitz.Rect(b['source']['bbox']).y1<high-.5 and
                min(bb.x1,b['source']['bbox'][2])-max(bb.x0,b['source']['bbox'][0])>min(bb.width,cb.width)*.4]
            if not barriers:candidates.append((gap,bb,item))
        if not candidates:continue
        candidates.sort(key=lambda x:x[0])
        if len(candidates)>1 and abs(candidates[0][0]-candidates[1][0])<2:continue
        _,bb,artwork=candidates[0];boxes.append(list(bb))
        if any((b['type']=='table' or b.get('source_table_fallback')) and fitz.Rect(b['source']['bbox']).intersects(bb) for b in blocks):continue
        stem=root/'reports/region-artwork'/f'{did}-p{page.number+1:04d}-{cap["id"]}';stem.parent.mkdir(parents=True,exist_ok=True)
        image=stem.with_suffix('.png');page.get_pixmap(matrix=fitz.Matrix(4,4),clip=bb,colorspace=fitz.csRGB,alpha=False).save(image)
        # An explicit policy boundary, independent of OS, installed tools or
        # historical project options. Never send a PDF crop to recognize().
        result={'engine':'disabled-for-pdf','items':[],
                'reason':'PDF native-only policy; source artwork retained without OCR.'}
        rows,items=[],[]
        evidence={'schema_version':'1.0.3','kind':'raster-table','source_kind':artwork['source_kind'],
                  'geometry_evidence':{k:v for k,v in artwork.items() if k.endswith('_tracks')},
                  'caption_block_id':cap['id'],'bbox':list(bb),'source_page':page.number+1,'image':image.relative_to(root).as_posix(),'image_sha256':sha(image),'engine':result['engine'],'items':items,'rows':rows,'review_status':'unreviewed','reason':result.get('reason'),'ocr_calls':0}
        evidence['grid_validation']={'pass':False,'reasons':['pdf-ocr-disabled'],'semantic_verification':False}
        write(stem.with_suffix('.json'),evidence)
        from figure_regions import export_region
        assets=export_region(page,bb,root/'assets'/f'{did}-p{page.number+1:04d}-{cap["id"]}-source-table',root)
        block=add_block(content,did,'image',{'page':page.number+1,'bbox':list(bb),
                'artwork_evidence':stem.with_suffix('.json').relative_to(root).as_posix()},[],**assets,
                width_mm=round(bb.width*25.4/72,2),caption_block_ids=[cap['id']],
                label_policy='retained-original',label_note='Source table artwork retained; native cell text unavailable.',
                structure={'semantic_role':'table','representation':'source-table-artwork','review_required':True},
                source_table_fallback=True)
        content['blocks'].remove(block);content['blocks'].insert(content['blocks'].index(cap),block)
        evidence.update(block_id=block['id'],disposition='source-table-artwork-retained',
                            next_action='Inspect native text and source geometry. Table artwork is preserved; its unavailable cell text has not been translated.')
        write(stem.with_suffix('.json'),evidence)
        content['issues'].append({'document_id':did,'page':page.number+1,'code':'source-table-text-unavailable','status':'open','evidence':stem.with_suffix('.json').relative_to(root).as_posix(),'message':'Complete source table artwork retained without OCR. Cell text is unavailable for native translation.'});records.append(evidence)
    return boxes,records


# Compatibility for existing project integrations. This alias also forbids OCR.
recover_tables=retain_pdf_tables
