"""Source-bound PDF vector crops, safe SVG validation, provisional inventory.

Detected regions are evidence for the invoking agent, not verified figures.
No OCR, chart interpretation, text substitution or semantic review is inferred.
"""
from pathlib import Path
from contextlib import contextmanager
import base64
import re
import xml.etree.ElementTree as ET

SVG_NS = 'http://www.w3.org/2000/svg'
SVG_TAGS = set('svg g defs path rect circle ellipse line polyline polygon use clipPath mask linearGradient radialGradient stop pattern image text tspan title desc symbol'.split())
RASTER_URI = re.compile(r'^data:image/(?:png|jpeg|gif|webp);base64,[a-z0-9+/=\s]+$', re.I)


def validate_svg(data):
    """Reject active/external SVG content instead of altering a figure."""
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    if len(data.encode('utf-8')) > 32 * 1024 * 1024:
        raise ValueError('SVG exceeds the 32 MiB supported asset bound.')
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)', data, re.I):
        raise ValueError('SVG must not contain DTD/entity declarations.')
    root = ET.fromstring(data)
    if root.tag != '{' + SVG_NS + '}svg':
        raise ValueError('Expected an SVG root in the SVG namespace.')
    for element in root.iter():
        if not element.tag.startswith('{' + SVG_NS + '}') or element.tag.split('}', 1)[-1] not in SVG_TAGS:
            raise ValueError('Unsupported or active SVG element: ' + str(element.tag))
        for key, value in element.attrib.items():
            name = key.split('}', 1)[-1].lower()
            if name.startswith('on') or name in {'src', 'base'}:
                raise ValueError('Active or external SVG attribute: ' + name)
            internal = re.fullmatch(r'#[A-Za-z_][\w:.-]*', value)
            raster = element.tag.endswith('}image') and RASTER_URI.fullmatch(value)
            if name == 'href' and not (internal or raster):
                raise ValueError('SVG references must be internal or embedded raster data.')
            if re.search(r'@import|expression\s*\(|javascript:|<\s*/?\s*script', value, re.I):
                raise ValueError('Active SVG attribute value.')
            for target in re.findall(r'url\s*\(([^)]*)\)', value, re.I):
                if not re.fullmatch(r'#[A-Za-z_][\w:.-]*', target.strip().strip("\"'")):
                    raise ValueError('External SVG paint/clip reference.')
    return root


def embedded_raster_colors(data):
    """Inspect embedded image samples rather than trusting their data-URI MIME."""
    import fitz
    root = validate_svg(data)
    records = []
    for element in root.iter('{' + SVG_NS + '}image'):
        uri = element.get('{http://www.w3.org/1999/xlink}href') or element.get('href', '')
        if not uri.startswith('data:'):
            continue
        pix = fitz.Pixmap(base64.b64decode(uri.split(',', 1)[1]))
        records.append({'colorspace': pix.colorspace.name if pix.colorspace else 'stencil',
                        'components': pix.colorspace.n if pix.colorspace else 0,
                        'alpha': bool(pix.alpha), 'width': pix.width, 'height': pix.height})
    return records


def normalize_pdf_rasters(page):
    """Decode risky colors in PDF context before SVG serialization.

    A raw CMYK JPEG embedded by the SVG exporter can have sample polarity that
    differs from the PDF image. Standalone JPEG conversion is already too late.
    Keep PDF Decode, soft masks, paths and legitimately dark artwork intact.
    """
    import fitz
    doc = page.parent
    records = []
    seen = set()
    for info in page.get_images(full=True):
        xref, smask = info[:2]
        if xref in seen:
            continue
        seen.add(xref)
        pix = fitz.Pixmap(doc, xref)
        if not pix.colorspace:
            continue
        decode = doc.xref_get_key(xref, 'Decode')
        if pix.colorspace.n in (1, 3) and decode[0] == 'null' and not smask:
            continue
        source_space = pix.colorspace.name
        if smask:
            if pix.alpha:
                pix = fitz.Pixmap(pix, 0)
            pix = fitz.Pixmap(pix, fitz.Pixmap(doc, smask))
        rgb = fitz.Pixmap(fitz.csRGB, pix)
        page.replace_image(xref, pixmap=rgb)
        records.append({'source_colorspace': source_space, 'output_colorspace': 'DeviceRGB',
                        'source_decode': decode[1], 'soft_mask_preserved': bool(smask),
                        'width': rgb.width, 'height': rgb.height,
                        'method': 'PDF-context decoded pixels to lossless RGB PNG'})
    return records


@contextmanager
def source_crop_page(page, native_text_exclusions=None, raster_xrefs=None):
    """Remove only inspected adjoining native text in a temporary copy.

    Image pixels and vector paths remain unchanged. This is never automatic
    label removal: each rectangle requires an observation and source evidence.
    """
    import fitz
    exclusions=native_text_exclusions or []
    if not exclusions and raster_xrefs is None:
        yield page
        return
    if not isinstance(exclusions,list):raise ValueError('Native text exclusions require a list.')
    for item in exclusions:
        if not isinstance(item,dict) or set(item)!={'bbox','reason','evidence'} or not all(isinstance(item[k],str) and item[k].strip() for k in ('reason','evidence')):
            raise ValueError('Each native text exclusion needs bbox, reason and inspected evidence.')
        box=fitz.Rect(item['bbox'])
        if box.is_empty or box.is_infinite or not page.rect.contains(box):raise ValueError('Invalid native text exclusion bounds.')
    with fitz.open() as temporary:
        temporary.insert_pdf(page.parent,from_page=page.number,to_page=page.number)
        reviewed=temporary[0]
        if raster_xrefs is not None:
            # Xrefs change during insert_pdf. Map by the source image digest,
            # never by insertion order or a document-specific object number.
            allowed=set(raster_xrefs)
            known={x[0] for x in page.get_images(full=True)}
            if not allowed or not allowed<=known:raise ValueError('Unknown owned raster identity.')
            def pixels(doc,xref):
                import hashlib
                p=fitz.Pixmap(doc,xref)
                return (p.width,p.height,p.n,hashlib.sha256(p.samples).hexdigest())
            keep={pixels(page.parent,x) for x in allowed}
            for item in reviewed.get_images(full=True):
                if pixels(temporary,item[0]) not in keep:reviewed.delete_image(item[0])
        for item in exclusions:reviewed.add_redact_annot(fitz.Rect(item['bbox']),fill=False,cross_out=False)
        reviewed.apply_redactions(images=0,graphics=0,text=0)
        yield reviewed


def export_crop(page, bbox, stem, scale=2.5, native_text_exclusions=None, raster_xrefs=None):
    with source_crop_page(page,native_text_exclusions,raster_xrefs) as reviewed:
        result=_export_crop(reviewed,bbox,stem,scale)
    result['metadata']['source_page']=page.number+1
    if native_text_exclusions:result['metadata']['native_text_exclusions']=native_text_exclusions
    if raster_xrefs is not None:result['metadata']['raster_xrefs']=raster_xrefs
    return result


def _export_crop(page, bbox, stem, scale=2.5):
    """Keep drawing paths in SVG and provide a separate raster export route."""
    import fitz
    stem = Path(stem)
    bb = fitz.Rect(bbox)
    if bb.is_empty or bb.is_infinite or not page.rect.contains(bb):
        raise ValueError('Crop must be nonempty, finite and within the source page.')
    if page.rotation:
        raise ValueError('Normalize and visually verify rotated pages before SVG cropping; use PNG otherwise.')
    stem.parent.mkdir(parents=True, exist_ok=True)
    temporary = fitz.open()
    try:
        isolated = temporary.new_page(width=bb.width, height=bb.height)
        isolated.show_pdf_page(isolated.rect, page.parent, page.number, clip=bb)
        color_records = normalize_pdf_rasters(isolated)
        svg = isolated.get_svg_image(text_as_path=True)
        root = validate_svg(svg)
        raster_colors = embedded_raster_colors(svg)
        if any(x['components'] not in (1, 3) for x in raster_colors):
            raise ValueError('Unsafe SVG raster colorspace remains; use a source-rendered PNG.')
        fallback = stem.with_suffix('.png')
        page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=bb, alpha=False).save(fallback)
        vector = stem.with_suffix('.svg')
        vector.write_text(svg, encoding='utf-8')
        return {'vector': vector, 'fallback': fallback, 'metadata': {
            'representation': 'svg-with-raster-fallback', 'source_page': page.number + 1,
            'bbox': list(bb), 'text_as_path': True,
            'svg_paths': len(list(root.iter('{' + SVG_NS + '}path'))),
            'embedded_rasters': len(list(root.iter('{' + SVG_NS + '}image'))),
            'raster_colors': raster_colors, 'color_normalization': color_records,
            'reference_renderer': 'source PDF, RGB, alpha=False',
            'visual_review': 'pending',
            'limits': 'Font outlines are preserved graphics, not editable or automatically translated text.'}}
    finally:
        temporary.close()


def visible_rasters(page):
    """Intersect image transforms with the renderer's active clip stack.

    A PDF image transform includes pixels hidden by clipping. Bounding boxes
    from get_image_info alone therefore cannot establish visible figure edges.
    Unsupported runtimes return explicit, review-required footprint evidence.
    """
    import fitz
    infos=page.get_image_info(xrefs=True)
    masks={x[0]:x[1] for x in page.get_images(full=True)}
    warnings=[]
    try:
        m=fitz.mupdf
        class ImageClips(m.FzDevice2):
            def __init__(self):
                super().__init__();self.rows=[]
                for name in ['fill_image','clip_path','clip_stroke_path','clip_image_mask','pop_clip']:
                    getattr(self,'use_virtual_'+name)()
            def fill_image(self,ctx,image,ctm,alpha,params):
                r=m.fz_transform_rect(m.FzRect(0,0,1,1),m.FzMatrix(ctm))
                s=self.fz_device_current_scissor()
                self.rows.append({'transform_bbox':[r.x0,r.y0,r.x1,r.y1],
                    'clip_bbox':[s.x0,s.y0,s.x1,s.y1],'opacity':alpha})
            def clip_path(self,*args):pass
            def clip_stroke_path(self,*args):pass
            def clip_image_mask(self,*args):pass
            def pop_clip(self,*args):pass
        dev=ImageClips()
        m.fz_run_page(page.this,dev,m.FzMatrix(),m.FzCookie());m.fz_close_device(dev)
        rows=dev.rows;method='renderer-active-clip-stack'
    except (AttributeError,RuntimeError,TypeError) as error:
        rows=[{'transform_bbox':list(x['bbox']),'clip_bbox':list(page.rect),'opacity':1} for x in infos]
        warnings.append('Active clip tracing unavailable: '+str(error));method='unverified-image-footprints'
    regions=[]
    for row in rows:
        original=fitz.Rect(row['transform_bbox']);box=original & fitz.Rect(row['clip_bbox']) & page.rect
        info=min(infos,key=lambda x:sum(abs(a-b) for a,b in zip(original,x['bbox'])),default={})
        xref=info.get('xref',0);mask=masks.get(xref)
        invisible=row['opacity']<=0
        if mask:
            try:invisible=invisible or not any(fitz.Pixmap(page.parent,mask).samples)
            except RuntimeError:warnings.append('Soft-mask visibility requires review for image '+str(xref))
        if invisible or box.is_empty or box.is_infinite:continue
        regions.append({**row,'bbox':list(box),'xref':xref,'soft_mask':bool(mask),
            'clipped':sum(abs(a-b) for a,b in zip(original,box))>.1,'review_required':True})
    return {'regions':regions,'method':method,'warnings':warnings,
        'limits':'Scissor bounds enclose nonrectangular clips; image content and caption ownership still need source inspection.'}


def inventory(page):
    """Find connected path regions; disconnected panels need page inspection."""
    drawings = page.get_drawings()
    result = {'page': page.number + 1, 'vector_paths': len(drawings),
              'raster_images': len(page.get_image_info()), 'regions': [],
              'status': 'provisional; inspect complete figure boundaries against the page',
              'limits': 'Rules can resemble figures; disconnected panels and text outlines may not group.'}
    cluster = getattr(page, 'cluster_drawings', None)
    if not drawings or not callable(cluster):
        result['method'] = 'path-count-only'
        return result
    regions = cluster(drawings=drawings, x_tolerance=4, y_tolerance=4)
    result['method'] = 'connected-drawing-regions'
    result['regions'] = [{'bbox': list(bb), 'review': 'unreviewed'} for bb in regions if bb.width >= 24 and bb.height >= 18]
    return result
