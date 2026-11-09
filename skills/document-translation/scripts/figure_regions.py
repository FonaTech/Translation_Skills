"""Source-bound automatic figure crops and text evidence; proposals need review.
Copyright 2026 Yufeng Zhan. MIT. No translation or invented caption is produced.
"""
from pathlib import Path
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET

FIGURE_REFERENCE = re.compile(r'^\s*(?:fig(?:ure)?s?\.?)\s*[A-Z]?\d+(?:\.\d+)*[a-z]?\s*(?:\([a-z]\)\s*)?(?:illustrates?|shows?|demonstrates?|depicts?|presents?|is|was|are|were)\b', re.I)
FIGURE_START = re.compile(r'^\s*(?:(?:supplementary\s+)?(?:fig(?:ure)?s?\.?|f\s*i\s*g\s*u\s*r\s*e)\s*[A-Z]?\d+|[图圖図]\s*[A-Z]?\d+|(?:abbildung|abb\.|figura|рис\.)\s*\d+)', re.I)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def translation_eligible(block, blocks):
    """Only caption-linked automatic images enter the reading/translation IR.

    Manual crops, equations and original page images retain their explicit scope.
    No caption is invented and no native prose is removed by this figure filter.
    """
    if block.get('type') != 'image' or 'figure_region' not in block:
        return True
    source = block.get('source', {})
    captions = set(block.get('caption_block_ids', []))
    return any(b.get('id') in captions and b.get('units') and
               any(u.get('source', '').strip() for u in b['units']) and
               b.get('source', {}).get('document_id') == source.get('document_id') and
               b.get('source', {}).get('page') == source.get('page')
               for b in blocks)


def archive_unbound(root, content):
    """Migrate legacy automatic images to a separate, lossless audit archive.

    The caller saves content and refreshes the parser layout handoff after changes.
    Removed image blocks, their label units and existing translations remain in the
    archive; original prose/caption blocks and asset files are left intact.
    """
    from translate import read, write
    root = Path(root)
    excluded = [b for b in content['blocks'] if not translation_eligible(b, content['blocks'])]
    if not excluded:
        return []
    path = root/'reports'/'figure-regions'/'excluded-automatic-images.json'
    archive = read(path) if path.exists() else {'schema_version': '1.0.2', 'blocks': []}
    known = {b['id'] for b in archive['blocks']}
    archive['blocks'].extend(b for b in excluded if b['id'] not in known)
    archive.update(policy='caption-required-for-automatic-images',
                   reason='No nonempty same-page caption binding; excluded from translation and reading output, not declared non-figure.',
                   native_prose_removed=False)
    write(path, archive)
    ids = {b['id'] for b in excluded}
    content['blocks'] = [b for b in content['blocks'] if b['id'] not in ids]
    return [b['id'] for b in excluded]


def confirmed_table_boxes(raw):
    """A chart grid alone is not enough evidence to exclude a figure."""
    import fitz
    boxes=[t['bbox'] for t in raw.get('table_regions',[])]
    captions=[l for l in raw.get('lines',[]) if re.match(r'^\s*(?:table|表)\s*(?:[IVX]+|\d+)',l['text'],re.I) and not re.search(r'\b(?:shows?|is|are|presents?)\b',l['text'],re.I)]
    for bounds in raw.get('structure_regions',[]):
        bb=fitz.Rect(bounds)
        if any(0<=bb.y0-fitz.Rect(c['bbox']).y1<=75 and min(bb.x1,c['bbox'][2])>max(bb.x0,c['bbox'][0]) for c in captions):boxes.append(bounds)
    return boxes


def archive_crop(page, bbox, stem, root):
    """Archive visible native characters, font/position and nearby caption context.

    Empty/outlined/scanned text remains explicitly unknown; the image and source
    preview are the vision/OCR evidence. Text is never guessed from an outline.
    """
    import fitz
    root, stem, box = Path(root), Path(stem), fitz.Rect(bbox)
    lines, nearby = [], []
    raw = page.get_text('rawdict', flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES)
    for bi, block in enumerate(raw['blocks']):
        if block.get('type') != 0:
            continue
        for li, line in enumerate(block.get('lines', [])):
            spans, full = [], ''.join(''.join(c['c'] for c in s.get('chars', [])) for s in line['spans'])
            for span in line['spans']:
                selected = [c for c in span.get('chars', []) if box.intersects(fitz.Rect(c['bbox']))]
                if not selected:
                    continue
                kept = {k: v for k, v in span.items() if k != 'chars'}
                kept.update(text=''.join(c['c'] for c in selected), chars=selected,
                            crop_intersects_partial_span=len(selected) != len(span.get('chars', [])))
                spans.append(kept)
            lid = f'p{page.number+1:04d}-b{bi:04d}-l{li:04d}'
            if spans:
                lines.append({'native_line_id': lid, 'bbox': list(line['bbox']),
                              'direction': list(line.get('dir', [1, 0])), 'wmode': line.get('wmode', 0),
                              'text': ''.join(s['text'] for s in spans), 'spans': spans})
            elif full.strip():
                bb = fitz.Rect(line['bbox'])
                horizontal = min(bb.x1, box.x1) - max(bb.x0, box.x0)
                gap = max(0, bb.y0-box.y1, box.y0-bb.y1)
                if horizontal > 0 and gap < 100:
                    nearby.append({'native_line_id': lid, 'bbox': list(bb), 'text': full,
                                   'purpose': 'context only; not part of crop text'})
    evidence = {'schema_version': '1.0.2', 'page': page.number+1, 'bbox': list(box),
                'coordinate_space': 'PDF page points; native text coordinates', 'page_rotation': page.rotation,
                'lines': lines, 'plain_text': '\n'.join(x['text'] for x in lines),
                'nearby_context': nearby, 'native_text_status': 'available' if lines else 'none; inspect image or run OCR',
                'ocr_required_if_visible_text_missing': True, 'review_status': 'unreviewed',
                'contract': 'Native text can be incomplete or garbled. Keep the crop with this ledger. Caption candidates must be verified against the page; never generate absent wording.'}
    stem.parent.mkdir(parents=True, exist_ok=True)
    jp, tp = stem.with_suffix('.text.json'), stem.with_suffix('.text.txt')
    jp.write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    tp.write_text(evidence['plain_text']+'\n', encoding='utf-8')
    return {'file': jp.relative_to(root).as_posix(), 'sha256': digest(jp),
            'text_file': tp.relative_to(root).as_posix(), 'text_sha256': digest(tp),
            'native_line_count': len(lines), 'native_text_status': evidence['native_text_status'],
            'review_status': 'unreviewed'}


def export_region(page, box, stem, root, mode='auto', native_text_exclusions=None, raster_xrefs=None):
    import fitz
    from vector_assets import export_crop
    box, root, stem = fitz.Rect(box) & page.rect, Path(root), Path(stem)
    if box.is_empty or box.is_infinite or not all(math.isfinite(x) for x in box):
        raise ValueError('Invalid visible crop bounds.')
    vectors = any(fitz.Rect(d['rect']).intersects(box) for d in page.get_drawings())
    extra, path = {}, None
    if mode == 'svg' or mode == 'auto' and vectors and not page.rotation:
        try:
            exported = export_crop(page, box, stem, scale=3,native_text_exclusions=native_text_exclusions,raster_xrefs=raster_xrefs)
            path = exported['vector']
            extra.update(asset_fallback=exported['fallback'].relative_to(root).as_posix(), asset_fallback_sha256=digest(exported['fallback']), vector=exported['metadata'])
        except (ValueError, RuntimeError, ET.ParseError) as error:
            if mode == 'svg':
                raise
            extra['vector'] = {'representation': 'source-rendered-png', 'reason': str(error), 'visual_review': 'pending'}
    if path is None:
        path = stem.with_suffix('.png'); path.parent.mkdir(parents=True, exist_ok=True)
        from vector_assets import source_crop_page
        with source_crop_page(page,native_text_exclusions,raster_xrefs) as reviewed:
            reviewed.get_pixmap(matrix=fitz.Matrix(3, 3), clip=box, colorspace=fitz.csRGB, alpha=False).save(path)
        extra.setdefault('vector', {'representation': 'source-rendered-png', 'visual_review': 'pending'})
    extra.update(asset=path.relative_to(root).as_posix(), asset_sha256=digest(path),
                 crop_text=archive_crop(page, box, stem, root))
    return extra


def partition_rasters(page, raw, captions):
    """Split composite bitmaps only at caption-supported low-ink gutters."""
    import fitz
    from PIL import Image
    result=[]
    for bounds,kind in raw:
        box=fitz.Rect(bounds);cuts=[]
        peers=[c for c in captions if -12<=fitz.Rect(c['source']['bbox']).y0-box.y1<=65 and
               box.x0<=(c['source']['bbox'][0]+c['source']['bbox'][2])/2<=box.x1]
        peers.sort(key=lambda c:c['source']['bbox'][0])
        if len(peers)>1 and 'raster' in kind:
            pix=page.get_pixmap(matrix=fitz.Matrix(2,2),clip=box,colorspace=fitz.csRGB,alpha=False)
            im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples).convert('L')
            for left,right in zip(peers,peers[1:]):
                a,b=fitz.Rect(left['source']['bbox']),fitz.Rect(right['source']['bbox'])
                if abs(a.y0-b.y0)>max(12,min(a.height,b.height)*.4) or a.x1>b.x0+8:continue
                target=(a.x1+b.x0)/2;radius=min(18,box.width*.09);candidates=[]
                for x in range(max(1,int((target-radius-box.x0)*2)),min(im.width-1,int((target+radius-box.x0)*2))):
                    ink=sum(im.getpixel((x,y))<215 for y in range(im.height))/im.height
                    candidates.append((ink,abs(box.x0+x/2-target),x))
                if candidates:
                    ink,_,x=min(candidates)
                    if ink<.06:cuts.append(box.x0+x/2)
        edges=[box.x0]+sorted(set(cuts))+[box.x1]
        result.extend(([edges[i],box.y0,edges[i+1],box.y1],kind+('-caption-partition' if cuts else '')) for i in range(len(edges)-1))
    return result


def propose(page, blocks, table_boxes=()):
    """Combine PDF geometry and model caption/label proposals, conservatively.

    No semantic figure detector is claimed. Connected artwork and caption-local
    bands generate crops, including pure vectors and mixed raster/path figures.
    All proposals retain native units and require edge/caption inspection.
    """
    import fitz
    from vector_assets import inventory, visible_rasters
    import figure_learning
    learned=figure_learning.load_model()
    def rect(b): return fitz.Rect(b['source']['bbox'])
    tables = [fitz.Rect(x) for x in table_boxes]
    captions = [b for b in blocks if b.get('units') and b['source'].get('bbox') and
                (b.get('structure', {}).get('semantic_role') == 'caption' or
                 b.get('presentation', {}).get('role') == 'caption' or
                 FIGURE_START.match(' '.join(u['source'] for u in b['units']))) and
                FIGURE_START.match(' '.join(u['source'] for u in b['units'])) and not FIGURE_REFERENCE.match(' '.join(u['source'] for u in b['units']))]
    raster_evidence=visible_rasters(page)
    raw = [(list(x['bbox']), 'raster-footprint') for x in raster_evidence['regions']]
    raw += [(x['bbox'], 'vector-cluster') for x in inventory(page)['regions']]
    # Outlined font glyphs can be disconnected paths with no native text.
    # Keep small components for edge expansion, not as standalone artwork.
    cluster=getattr(page,'cluster_drawings',None)
    edge_components=list(cluster(x_tolerance=4,y_tolerance=4)) if callable(cluster) else []
    # A publisher frame may enclose both a plate and its caption. Separate
    # the caption at its source boundary before measuring figure association.
    framed=[]
    for bounds,kind in raw:
        bb=fitz.Rect(bounds)
        inside=[c for c in captions if bb.contains(rect(c)) and rect(c).y0>bb.y0+24 and rect(c).y1>=bb.y1-16]
        if kind=='vector-cluster' and len(inside)==1:
            bb.y1=rect(inside[0]).y0-3;kind+='-caption-frame'
        framed.append((list(bb),kind))
    raw=partition_rasters(page,framed,captions)
    # Outlined tables may have no native cells and escape table detection.
    # A reviewed caption role plus a nearby ruled vector envelope is enough
    # to keep this object out of a following figure, without reading its cells.
    table_captions=[b for b in blocks if b.get('units') and b['source'].get('bbox') and
        b.get('presentation',{}).get('role')=='caption' and
        re.match(r'^\s*(?:t\s*a\s*b\s*l\s*e|表)\s*(?:[IVX]+|\d+)', ' '.join(u['source'] for u in b['units']),re.I)]
    for bounds,kind in raw:
        bb=fitz.Rect(bounds)
        if 'raster' in kind and any(-8<=rect(c).y0-bb.y1<=24 and
            max(0,min(bb.x1,rect(c).x1)-max(bb.x0,rect(c).x0))/max(1,min(bb.width,rect(c).width))>.7 for c in table_captions):tables.append(bb)
    drawings=page.get_drawings() if table_captions else []
    for bounds,kind in raw:
        bb=fitz.Rect(bounds)
        if kind!='vector-cluster':continue
        titles=[c for c in table_captions if 0<=bb.y0-rect(c).y1<=75 and
                max(0,min(bb.x1,rect(c).x1)-max(bb.x0,rect(c).x0))/max(1,min(bb.width,rect(c).width))>.5]
        if not titles:continue
        rules=[];horizontal_segments=[];vertical_segments=[]
        for drawing in drawings:
            for item in drawing.get('items',[]):
                if item[0]=='l':
                    a,z=item[1],item[2]
                    if bb.contains(a) and bb.contains(z) and (abs(a.x-z.x)<.5 or abs(a.y-z.y)<.5):rules.append((a,z))
                elif item[0]=='re':
                    rr=fitz.Rect(item[1])
                    if (bb+(-1,-1,1,1)).contains(rr):
                        if rr.height<=1 and rr.width>bb.width*.15:horizontal_segments.append(rr)
                        if rr.width<=1 and rr.height>2:vertical_segments.append(rr)
        horizontal=sum(abs(a.y-z.y)<.5 and abs(a.x-z.x)>bb.width*.4 for a,z in rules)
        vertical=sum(abs(a.x-z.x)<.5 and abs(a.y-z.y)>bb.height*.4 for a,z in rules)
        horizontal+=len({round(r.y0) for r in horizontal_segments})
        # A vertical rule can be serialized once per cell instead of full height.
        tracks={}
        for r in vertical_segments:tracks.setdefault(round(r.x0),[]).append((r.y0,r.y1))
        for intervals in tracks.values():
            total=0;end=-float('inf')
            for start,stop in sorted(intervals):total+=max(0,stop-max(start,end));end=max(end,stop)
            vertical+=total>bb.height*.4
        if horizontal>=3 and vertical>=2:tables.append(bb)
    graphics = []
    for bounds, kind in raw:
        bb = fitz.Rect(bounds) & page.rect
        if bb.is_empty or bb.width < 24 or bb.height < 18 or kind=='vector-cluster' and bb.get_area() > page.rect.get_area()*.90:
            continue
        if any(t.contains(bb) or (t & bb).get_area()/max(1,bb.get_area())>.92 for t in tables):
            continue
        if any(sum(abs(a-b) for a,b in zip(bb, prior['box'])) < 3 for prior in graphics):
            continue
        owned=sorted({x['xref'] for x in raster_evidence['regions'] if x.get('xref') and
            (fitz.Rect(x['bbox'])&bb).get_area()/max(1,bb.get_area())>.98}) if 'raster' in kind else []
        graphics.append({'box': bb, 'kind': kind,'raster_xrefs':owned})
    # Tiled PDF images are serialization fragments, not separate figures.
    # Join touching strips before asking the association head about a plate.
    changed=True
    while changed:
        changed=False
        for i,a in enumerate(graphics):
            for j in range(i+1,len(graphics)):
                b=graphics[j];aa=a['box'];bb=b['box']
                xo=max(0,min(aa.x1,bb.x1)-max(aa.x0,bb.x0))/max(1,min(aa.width,bb.width))
                yo=max(0,min(aa.y1,bb.y1)-max(aa.y0,bb.y0))/max(1,min(aa.height,bb.height))
                xgap=max(0,aa.x0-bb.x1,bb.x0-aa.x1);ygap=max(0,aa.y0-bb.y1,bb.y0-aa.y1)
                if not ((xo>.65 and ygap<=1) or (yo>.65 and xgap<=1)):continue
                def owner(box):
                    candidates=[c for c in captions if -12<=rect(c).y0-box.y1<=60 and
                        max(0,min(rect(c).x1,box.x1)-max(rect(c).x0,box.x0))/max(1,min(rect(c).width,box.width))>.4]
                    return min(candidates,key=lambda c:abs(rect(c).y0-box.y1)+abs(rect(c).x0-box.x0)*.2)['id'] if candidates else None
                oa,ob=owner(aa),owner(bb)
                if not oa or not ob or oa!=ob:continue
                if (aa&bb).get_area()>min(aa.get_area(),bb.get_area())*.02 and oa!=ob:continue
                a['box']=aa|bb;a['raster_xrefs']=sorted(set(a['raster_xrefs']+b['raster_xrefs']));a['kind']='+'.join(sorted(set(a['kind'].split('+')+b['kind'].split('+'))));graphics.pop(j);changed=True;break
            if changed:break
    # A caption can wrap into the opposite column at the same baseline. This
    # source cue authorizes a full-width panel band without a document-specific
    # filename rule. Separate numbered captions at the same height stay separate.
    horizons={}
    for cap in captions:
        cb=rect(cap)
        same_row=[b for b in blocks if b is not cap and b['source'].get('bbox') and b.get('units') and
                  abs(rect(b).y0-cb.y0)<4 and rect(b).x0>=cb.x1-5 and
                  len(' '.join(u['source'] for u in b['units']))>45 and
                  not FIGURE_START.match(' '.join(u['source'] for u in b['units']))]
        horizons[cap['id']]=(0,page.rect.width) if same_row else (cb.x0-18,cb.x1+18)
    groups, unused = {}, []
    for g in graphics:
        bb = g['box']; ranked = []
        for cap in captions:
            cb = rect(cap)
            left,right=horizons[cap['id']]
            overlap = max(0, min(bb.x1, right)-max(bb.x0, left))/max(1,min(bb.width,right-left))
            if bb.y1<page.rect.height*.065 and cb.y0>page.rect.height*.12:
                continue
            side=(min(bb.y1,cb.y1)>max(bb.y0,cb.y0) and 0<=cb.x0-bb.x1<=24 and bb.width<page.rect.width*.3)
            # A detached part immediately below its own narrow caption has
            # stronger source ownership than a neighboring side caption.
            prior_owners=[c for c in captions if 0<=bb.y0-rect(c).y1<=18 and
                abs(bb.x0-rect(c).x0)<=8 and .7<=bb.width/max(1,rect(c).width)<=1.3]
            if prior_owners and cap not in prior_owners:continue
            if overlap < .18 and not side:continue
            below = cb.y0 >= bb.y1-8
            gap = cb.y0-bb.y1 if below else bb.y0-cb.y1
            if side:gap=cb.x0-bb.x1
            if gap < -12 or gap > page.rect.height*.45:
                continue
            # An independently numbered caption between artwork and candidate
            # is a source boundary, even when it is not narrative prose.
            if any(other is not cap and min(rect(other).x1,bb.x1)>max(rect(other).x0,bb.x0) and
                   min(cb.y1,bb.y1)<=rect(other).y0 and rect(other).y1<=max(cb.y0,bb.y0)
                   for other in captions):continue
            # Reject a caption across an intervening narrative paragraph.
            blockers = [b for b in blocks if b['type']=='paragraph' and b.get('units') and b['source'].get('bbox') and
                        b.get('presentation',{}).get('role','body') in {'body','abstract'} and
                        len(' '.join(u['source'] for u in b['units']))>100 and
                        min(cb.y1,bb.y1)<=rect(b).y0 and rect(b).y1<=max(cb.y0,bb.y0) and
                        min(rect(b).x1,bb.x1)>max(rect(b).x0,bb.x0)]
            if not blockers:
                cost=gap + (0 if below or side or cap in prior_owners else page.rect.height*.08)+(1-overlap)*20
                if learned:
                    evidence_page={'width':page.rect.width,'height':page.rect.height}
                    cp={'bbox':list(cb),'text':' '.join(u['source'] for u in cap['units'])}
                    source_rows=[{'bbox':b['source']['bbox'],'text':' '.join(u['source'] for u in b.get('units',[]))} for b in blocks if b['source'].get('bbox')]
                    probability=figure_learning.predict(learned['link_head'],[figure_learning.link_features(list(bb),cp,evidence_page,source_rows,g['kind'])])[0]
                    # A complete cross-column caption can lie outside the
                    # association head's narrow-caption training geometry. A
                    # nearby plate in its unobstructed band remains admissible;
                    # the caption/prose barriers above still apply.
                    close_band=(below and 0<=gap<=min(48,page.rect.height*.07)
                        and overlap>=.65 and bb.x0>=left and bb.x1<=right)
                    if probability<learned['link_threshold'] and not (side and gap<=12) and cap not in prior_owners and not close_band:continue
                    if probability<learned['link_threshold'] and close_band:g['association_route']='bounded-caption-band'
                    cost+=(1-probability)*min(40,page.rect.height*.05)
                ranked.append((cost, cap))
        if ranked:
            score, cap = min(ranked, key=lambda x:x[0]); groups.setdefault(cap['id'], {'caption':cap,'graphics':[]})['graphics'].append(g)
        else:
            unused.append(g)
    # A component far from the caption may be adjacent to an already bound
    # panel. Attach only within the same column envelope and without any
    # intervening caption or narrative. Record this geometry-assisted route.
    for _ in range(len(unused)):
        attached=[]
        for component in unused:
            bb=component['box'];matches=[]
            if bb.y1<page.rect.height*.065:continue
            for group in groups.values():
                cb=rect(group['caption']);envelope=fitz.Rect(group['graphics'][0]['box'])
                for member in group['graphics'][1:]:envelope|=member['box']
                overlap=max(0,min(bb.x1,envelope.x1)-max(bb.x0,envelope.x0))/max(1,min(bb.width,envelope.width))
                gap=max(0,envelope.y0-bb.y1,bb.y0-envelope.y1)
                vertical_overlap=max(0,min(bb.y1,envelope.y1)-max(bb.y0,envelope.y0))/max(1,min(bb.height,envelope.height))
                horizontal_gap=max(0,bb.x0-envelope.x1,envelope.x0-bb.x1)
                column_connected=overlap>=.65 and gap<=min(45,page.rect.height*.055)
                caption_horizon=horizons[group['caption']['id']]
                cross_column_tail=caption_horizon[1]-caption_horizon[0]>page.rect.width*.9
                max_row_gap=page.rect.width*.2 if cross_column_tail else min(60,page.rect.width*.11)
                row_connected=(vertical_overlap>=.65 and horizontal_gap<=max_row_gap and
                    (cb.width>page.rect.width*.58 or cross_column_tail) and
                    bb.x0>=caption_horizon[0] and bb.x1<=caption_horizon[1])
                if not (column_connected or row_connected) or bb.y1>cb.y0+2:continue
                union=bb|envelope
                barriers=[b for b in blocks if b is not group['caption'] and b.get('units') and b['source'].get('bbox') and
                    min(rect(b).x1,union.x1)>max(rect(b).x0,union.x0) and
                    min(bb.y1,envelope.y1)<=rect(b).y0 and rect(b).y1<=max(bb.y0,envelope.y0) and
                    (b.get('presentation',{}).get('role')=='caption' or FIGURE_START.match(' '.join(u['source'] for u in b['units'])) or b.get('presentation',{}).get('role','body') in {'body','abstract'} and len(' '.join(u['source'] for u in b['units']))>100)]
                if not barriers:matches.append((gap,group))
            if len(matches)==1:
                group=matches[0][1];component['association_route']='adjacent-to-bound-panel';group['graphics'].append(component);attached.append(component)
        if not attached:break
        unused=[g for g in unused if g not in attached]
    proposals = []
    part_groups=[]
    for group in groups.values():
        cap=group['caption'];sides={}
        for g in group['graphics']:
            key='after' if g['box'].y0>=rect(cap).y1 else 'before'
            sides.setdefault(key,[]).append(g)
        part_groups.extend({'caption':cap,'graphics':gs} for gs in sides.values())
    for group in part_groups + [{'caption':None,'graphics':[g]} for g in unused]:
        cap, gs = group['caption'], group['graphics'];bb=fitz.Rect(gs[0]['box'])
        for g in gs[1:]: bb |= g['box']
        outlined=[]
        if cap:
            original=fitz.Rect(bb); cb=rect(cap)
            for _ in range(4):
                changed=False
                for component in edge_components:
                    cr=fitz.Rect(component)
                    if list(cr) in outlined or bb.contains(cr):continue
                    if cr.width>=24 and cr.height>=18:continue
                    if cr.width>original.width*.65 or cr.height>original.height*.75:continue
                    if cr.y1>=cb.y0-1 or cr.y0<original.y0-8:continue
                    if not (bb+(-18,-8,18,18)).intersects(cr):continue
                    if any(t.intersects(cr) for t in tables):continue
                    bb|=cr;outlined.append(list(cr));changed=True
                if not changed:break
        # Include native figure labels within a local margin. Never absorb prose
        # solely because it is near artwork; source units remain in the IR.
        included=[]
        for b in blocks:
            if b is cap or not b['source'].get('bbox'):
                continue
            br=rect(b); semantic=b.get('structure',{}).get('semantic_role')
            text=' '.join(u['source'] for u in b.get('units',[])).strip()
            section_heading=bool(re.match(r'^(?:[IVXLCDM]+\.|\d+(?:\.\d+)*\.?)\s+[A-Z]',text) and sum(c.isalpha() for c in text)>12 and (text.upper()==text or b.get('typography',{}).get('bold')))
            if section_heading:continue
            panel_marker=bool(re.fullmatch(r'\(?[a-z]\)?',' '.join(u['source'] for u in b.get('units',[])).strip()))
            short_table_label=semantic=='table' and b['type']!='table' and sum(len(u['source']) for u in b.get('units',[]))<85 and not FIGURE_START.match(' '.join(u['source'] for u in b.get('units',[])))
            if any(t.contains(br) for t in tables):continue
            if (semantic=='label' or panel_marker or short_table_label) and (bb+(-12,-12,12,12)).intersects(br):
                if cap and br.y1>rect(cap).y0+1:continue
                bb |= br;included.append(b['id'])
        padding=0 if all('raster' in g['kind'] for g in gs) and not included and not outlined else 2
        bb = (bb+(-padding,-padding,padding,padding)) & page.rect
        # Preserve the complete owned plate even where its transparent image
        # footprint overlaps another plate. Isolate PDF image identities instead
        # of clipping at a neighbor's rectangle, which can amputate real panels.
        owned=sorted({x for g in gs for x in g.get('raster_xrefs',[])})
        raster_xrefs=owned if owned and all('raster' in g['kind'] for g in gs) else None
        exclusions=[]
        for other in blocks:
            if not other.get('source',{}).get('bbox') or other.get('presentation',{}).get('role')!='caption':continue
            if bb.intersects(rect(other)):
                exclusions.append({'bbox':list(rect(other)&page.rect),'reason':'Adjoining native caption is translated separately; artwork preserved.', 'evidence':'source block '+other['id']+'; native caption role and overlap with PDF crop'})
        if bb.width<24 or bb.height<18:continue
        proposals.append({'bbox':list(bb),'caption_block_ids':[cap['id']] if cap else [],
                          'raster_xrefs':raster_xrefs,
                          'native_text_exclusions':exclusions,
                          'evidence_kinds':sorted({g['kind'] for g in gs}),
                          'association_routes':sorted({g.get('association_route','learned-caption-association' if cap else 'unbound-source-artwork') for g in gs}),
                          'contained_label_block_ids':included,
                          'outlined_edge_components':outlined,
                          'confidence':.78 if cap and len(gs)>1 else .70 if cap else .42,
                          'confidence_kind':'trained association with geometry constraints; uncalibrated' if learned else 'uncalibrated geometry heuristic',
                          'association_model_id':learned['id'] if learned else None,
                          'raster_boundary_method':raster_evidence['method'],
                          'raster_boundary_warnings':raster_evidence['warnings'],
                          'trigger':'no standalone bitmap' if all(g['kind']=='vector-cluster' for g in gs) else 'source composite crop preserves masks, paths and nearby labels',
                          'review_required':True})
    # Prefer complete caption-bound crops over component footprints.
    proposals=[p for i,p in enumerate(proposals) if not any(i!=j and fitz.Rect(q['bbox']).contains(fitz.Rect(p['bbox'])) and
            fitz.Rect(q['bbox']).get_area()>fitz.Rect(p['bbox']).get_area() and q['caption_block_ids'] for j,q in enumerate(proposals))]
    order={b['id']:i for i,b in enumerate(blocks)}
    return sorted(proposals,key=lambda p:(min((order[x] for x in p['caption_block_ids']),default=len(blocks)),p['bbox'][1],p['bbox'][0]))


def append_page(root, content, did, page, add_block, table_boxes=()):
    from translate import write
    root=Path(root);blocks=[b for b in content['blocks'] if b['source']['document_id']==did and b['source'].get('page')==page.number+1]
    proposals=propose(page,blocks,table_boxes)
    records=[]
    for i,p in enumerate(proposals,1):
        bb=p['bbox'];stem=root/'assets'/f'{did}-p{page.number+1:04d}-figure-{i:03d}'
        assets=export_region(page,bb,stem,root,native_text_exclusions=p.get('native_text_exclusions'),raster_xrefs=p.get('raster_xrefs'))
        candidate={'type':'image','source':{'document_id':did,'page':page.number+1},
                   'figure_region':p,'caption_block_ids':p['caption_block_ids']}
        if not translation_eligible(candidate,blocks):
            records.append({**p,**assets,'block_id':None,
                            'translation_eligible':False,'disposition':'audit-only-no-caption'})
            continue
        block=add_block(content,did,'image',{'page':page.number+1,'bbox':bb,'native_text_exclusions':p.get('native_text_exclusions',[]),'raster_xrefs':p.get('raster_xrefs')},[],**assets,
              width_mm=round((bb[2]-bb[0])*25.4/72,2),label_policy='unreviewed',
              caption_block_ids=p['caption_block_ids'],figure_region={**p,'status':'proposed'},
              figure_group_id=p['caption_block_ids'][0] if p['caption_block_ids'] else None,
              presentation={'span':'all' if bb[2]-bb[0]>page.rect.width*.58 else 'column'})
        if p['caption_block_ids']:
            content['blocks'].remove(block);index=next(i for i,b in enumerate(content['blocks']) if b['id'] in p['caption_block_ids']);content['blocks'].insert(index,block)
        records.append({**p,'block_id':block['id'],'asset':block['asset'],'crop_text':block['crop_text'],
                        'translation_eligible':True,'disposition':'caption-linked-reading-candidate'})
    # Figure-native labels belong to the graphic, not to a second prose list.
    # Move only complete, source-contained protected blocks; retain their
    # original IDs/text/typography and all current translations in an owned
    # source-label archive. A retained-label exception is reviewed explicitly.
    # Ordinary prose/captions and partially intersecting blocks remain untouched.
    owners={}
    for record in records:
        if not record.get('block_id'):continue
        image=next(b for b in content['blocks'] if b['id']==record['block_id'])
        candidates=set(record.get('contained_label_block_ids',[]))
        candidates.update(b['id'] for b in blocks if b['type'] not in {'table','heading','reference'} and
            (b.get('structure',{}).get('semantic_role') in {'label','table','equation'} or
             sum(len(u['source']) for u in b.get('units',[]))<=85))
        for bid in candidates:
            candidate=next((b for b in blocks if b['id']==bid),None)
            if candidate is None or candidate.get('presentation',{}).get('role')=='caption':continue
            if (candidate.get('structure',{}).get('semantic_role') not in {'label','table','equation'} and
                sum(len(u['source']) for u in candidate.get('units',[]))>85):continue
            if candidate['type']=='table' or not candidate.get('source',{}).get('bbox'):continue
            if not __import__('fitz').Rect(record['bbox']).contains(__import__('fitz').Rect(candidate['source']['bbox'])):continue
            owners.setdefault(bid,[]).append(image)
    moved=[]
    for bid,images in owners.items():
        if len(images)!=1:continue
        candidate=next(b for b in content['blocks'] if b['id']==bid);image=images[0]
        image.setdefault('source_label_blocks',[]).append(candidate)
        content['blocks'].remove(candidate);moved.append(bid)
        for issue in content.get('issues',[]):
            if issue.get('block_id')==bid and issue.get('code')=='structure-protected-review':
                issue.update(block_id=image['id'],original_block_id=bid,source_label_owner=image['id'])
    folder=root/'reports'/'figure-regions';folder.mkdir(parents=True,exist_ok=True)
    ledger=folder/f'{did}-p{page.number+1:04d}.json'
    write(ledger,{'schema_version':'1.0.2','document_id':did,'page':page.number+1,'proposals':records,
                 'admission_policy':'caption-required-for-automatic-images',
                 'native_units_removed':False,'native_label_blocks_rehomed':moved,'review_status':'unreviewed',
                 'limits':'Not all arbitrary figures can be detected. Inspect disconnected panels, captions and outlined labels. Scans need visual/OCR region detection.'})
    return records
