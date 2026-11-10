"""Separate page furniture from prose after learned role/region inference.

Repeated text must also agree in physical margin position. Metadata, references
and source footnotes remain reading content unless this narrower gate succeeds.
Copyright 2026 Yufeng Zhan. MIT.
"""
import re

REVISION='1.0.3-margin-ownership-1'


def key(row):
    return re.sub(r'\d+','#',row['text'].strip().casefold())


def edge(row,page):
    box=row['bbox'];height=page['height']
    if box[3]<height*.1:return 'header'
    if box[1]>height*.91:return 'footer'
    return None


def tracks(pages):
    groups={}
    for page in pages:
        for row in page['lines']:
            side=edge(row,page)
            if not side or len(row['text'].strip())>180:continue
            groups.setdefault((key(row),side),[]).append({
                'page':page['page'],'bbox':[round(v/(page['width'] if i%2==0 else page['height']),6)
                                           for i,v in enumerate(row['bbox'])]})
    return [{'text_key':text,'side':side,'occurrences':items}
            for (text,side),items in sorted(groups.items()) if len({x['page'] for x in items})>=2]


def classify(row,page,profile,decision):
    side=edge(row,page)
    if not side:return None
    text=row['text'].strip();box=row['bbox'];size=max(1,row['size'])
    if not text or len(text)>180 or decision.get('content_integrity'):return None
    # A marginally positioned document may consist entirely of its actual body.
    # Repetition alone must never empty such a page or move a prose continuation
    # into the furniture archive.
    interior=[r for r in page['lines'] if r['id']!=row['id'] and
              page['height']*.1<=r['bbox'][1] and r['bbox'][3]<=page['height']*.91 and
              len(r['text'].strip())>=25]
    if not interior:return None
    if len(text.split())>=5 and re.search(r'[.!?。！？]\s*$',text):return None
    if any(r['id']!=row['id'] and r['native_block']==row['native_block'] and
           r.get('font')==row.get('font') and abs(r['size']-size)<size*.1 and
           abs(r['bbox'][0]-box[0])<size*1.5 and
           0<abs(r['bbox'][1]-box[1])<size*1.8 and len(r['text'].split())>=5 for r in page['lines']):return None
    if decision.get('semantic_role') in {'footnote','code','equation'} or decision.get('assigned_role') in {'caption','table','reference','equation'}:return None
    if re.search(r'(?:symbol|math|cmsy|cmmi|cmex)',row.get('font',''),re.I):return None
    for table in page.get('table_regions',[]):
        b=table['bbox']
        if b[0]<=sum(box[::2])/2<=b[2] and b[1]<=sum(box[1::2])/2<=b[3]:return None
    # Repeated physical slots, rather than merely the occurrence of a common
    # word or number, distinguish furniture from recurring body/caption text.
    normalized=[v/(page['width'] if i%2==0 else page['height']) for i,v in enumerate(box)]
    for track in profile.get('furniture_tracks',[]):
        if track['text_key']!=key(row) or track['side']!=side:continue
        peers=[x for x in track['occurrences'] if x['page']!=page['page'] and
               abs(x['bbox'][1]-normalized[1])<.015 and
               min(abs(x['bbox'][0]-normalized[0]),
                   abs(sum(x['bbox'][::2])-sum(normalized[::2]))/2)<.035]
        if peers and size<=profile['body_size']*1.35:
            return {'kind':side,'rule':'repeated-physical-margin-slot','repeat_pages':sorted({x['page'] for x in peers}),
                    'raw_model_role':decision.get('predicted_role'),'revision':REVISION}
    if (re.fullmatch(r'\(?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?\)?',text,re.I) and
        (box[3]<page['height']*.055 or box[1]>page['height']*.945) and
        size<=profile['body_size']*1.35):
        return {'kind':side,'rule':'isolated-outer-margin-page-number',
                'raw_model_role':decision.get('predicted_role'),'revision':REVISION}
    return None
