"""Compare browser-decoded figures with original PDF crops before rendering.

Color fidelity is mechanical evidence, never semantic or aesthetic certification.
Failing retained-original assets use an opaque RGB crop from the original PDF.
"""
from pathlib import Path
import argparse
import base64
import json
import os

GATE_VERSION = 'source-appearance-1.0.3-raster-completeness-2'
PDF_COMPARISON_VERSION = 'physical-page-grid-3-live-source-fonts'


def compare_pdf_region(source_page, source_bbox, output_page, output_bbox, reference, candidate, native_text_exclusions=None, raster_xrefs=None, source_frame=None, output_frame=None, render_cache=None):
    """Render declared source/output regions on the same physical pixel grid.

    Independently clipped pixmaps round their edges to different device pixels.
    Resizing those crops compares padding and sampling phase as well as artwork.
    Place the source crop at the declared output rectangle on an empty page,
    then render both pages with identical clips, resolution and RGB settings.
    No offset search, content matching or threshold adjustment is performed.
    An optional cache must be scoped to one verification of immutable documents.
    It stores display lists, not rendered pixels; every crop is still compared.
    """
    import fitz
    source_bbox, output_bbox = fitz.Rect(source_bbox), fitz.Rect(output_bbox)
    if source_bbox.is_empty or not source_page.rect.contains(source_bbox):
        raise ValueError('Invalid source comparison region.')
    if output_bbox.is_empty or not output_page.rect.contains(output_bbox):
        raise ValueError('Invalid output comparison region.')
    # Preserve the enclosing native object's transform for a glyph check.
    # Re-fitting a tiny glyph independently can quantize font hinting differently
    # from the same glyph inside its enclosing source object. Sampling remains
    # on the declared output grid, with the original comparison thresholds.
    if (source_frame is None)!=(output_frame is None):
        raise ValueError('Both physical comparison frames are required.')
    source_frame=fitz.Rect(source_frame) if source_frame is not None else source_bbox
    output_frame=fitz.Rect(output_frame) if output_frame is not None else output_bbox
    if source_frame.is_empty or not source_page.rect.contains(source_frame) or not source_frame.contains(source_bbox):
        raise ValueError('Invalid source comparison frame.')
    if output_frame.is_empty or not output_page.rect.contains(output_frame) or not (output_frame+(-.001,-.001,.001,.001)).contains(output_bbox):
        raise ValueError('Invalid output comparison frame.')
    from vector_assets import check_raster_completeness
    check_raster_completeness(source_page, source_frame, raster_xrefs)
    # Up to 576 dpi retains small line art; cap large figure memory.
    scale = min(8, 1536 / max(output_bbox.width, output_bbox.height))
    from contextlib import ExitStack
    def expected_display_list(stack):
        expected=stack.enter_context(fitz.open())
        try:
            page = expected.new_page(width=output_page.rect.width, height=output_page.rect.height)
            from vector_assets import source_crop_page
            with source_crop_page(source_page,native_text_exclusions,raster_xrefs) as reviewed:
                page.show_pdf_page(output_frame, reviewed.parent, reviewed.number,
                                   clip=source_frame, keep_proportion=False)
            return page.get_displaylist()
        except BaseException:
            expected.close()
            raise
    # A verification-scoped cache reuses immutable display lists, never rendered
    # pixels, clip coordinates, sampling phases or tolerances. Thousands of
    # glyphs on a page still receive separate full-resolution pixel checks.
    # Embedded Type 3 fonts can be lazily resolved from the temporary document.
    # A display list outliving that document silently drops all such text.
    # Retain cached documents alongside their lists until this verification ends.
    with ExitStack() as live:
        if render_cache is None:
            expected_list=expected_display_list(live);output_list=output_page.get_displaylist()
        else:
            expected_key=('source',id(source_page.parent),source_page.number,tuple(source_frame),
                tuple(output_frame),tuple(output_page.rect),
                json.dumps(native_text_exclusions or [],sort_keys=True),tuple(raster_xrefs or []))
            output_key=('output',id(output_page.parent),output_page.number)
            if expected_key not in render_cache:
                cache_stack=ExitStack()
                try:
                    display=expected_display_list(cache_stack)
                except BaseException:
                    cache_stack.close();raise
                render_cache[expected_key]=(display,cache_stack)
            if output_key not in render_cache:render_cache[output_key]=output_page.get_displaylist()
            expected_list=render_cache[expected_key][0];output_list=render_cache[output_key]
        for display,destination in [(expected_list,reference),(output_list,candidate)]:
            display.get_pixmap(clip=output_bbox,matrix=fitz.Matrix(scale,scale),
                               colorspace=fitz.csRGB,alpha=False).save(destination)
    return {**compare_images(reference, candidate),
            'comparison_method': PDF_COMPARISON_VERSION,
            'render_scale': scale, 'source_bbox': list(source_bbox),
            'source_frame':list(source_frame),'output_frame':list(output_frame)}


def close_render_cache(cache):
    """Release verification-owned source documents and lists deterministically."""
    for key,value in cache.items():
        if key[0]=='source':value[1].close()
    cache.clear()


def compare_images(reference, candidate):
    from PIL import Image, ImageChops, ImageFilter, ImageStat
    with Image.open(reference) as im:
        a = im.convert('RGB')
    with Image.open(candidate) as im:
        b = im.convert('RGBA')
    white = Image.new('RGBA', b.size, 'white')
    white.alpha_composite(b)
    b = white.convert('RGB')
    original_size = a.size
    a.thumbnail((768, 768), Image.Resampling.LANCZOS)
    b = b.resize(a.size, Image.Resampling.LANCZOS)
    # Require an interior white neighborhood to tolerate dark-line antialiasing.
    source_white = a.convert('L').filter(ImageFilter.MinFilter(5))
    target_gray = b.convert('L')
    count = a.width * a.height
    def pixels(im):
        return im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata()
    new_black = sum(x >= 225 and y <= 55 for x, y in zip(pixels(source_white), pixels(target_gray))) / count
    delta = ImageChops.difference(a.filter(ImageFilter.GaussianBlur(.7)), b.filter(ImageFilter.GaussianBlur(.7)))
    mae = sum(ImageStat.Stat(delta).mean) / 3
    major = sum(max(x) >= 85 for x in pixels(delta)) / count
    return {'pass': mae <= 12 and major <= .08 and new_black <= .002,
            'mean_absolute_rgb_error': round(mae, 6),
            'major_color_difference_fraction': round(major, 8),
            'new_black_on_source_white_fraction': round(new_black, 8),
            'reference_pixels': list(original_size), 'comparison_pixels': list(a.size),
            'thresholds': {'mean_absolute_rgb_error_max': 12,
                           'major_color_difference_fraction_max': .08,
                           'new_black_on_source_white_fraction_max': .002}}


def browser_raster(page, asset, destination, width, height):
    p = Path(asset)
    mime = {'.svg': 'image/svg+xml', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}.get(p.suffix.lower(), 'image/jpeg')
    uri = 'data:' + mime + ';base64,' + base64.b64encode(p.read_bytes()).decode()
    data = page.evaluate('''async ({uri,w,h})=>{
      const img=new Image();img.src=uri;await img.decode();
      if(!img.naturalWidth||!img.naturalHeight)throw Error('Undecodable figure');
      const c=document.createElement('canvas');c.width=w;c.height=h;
      const x=c.getContext('2d');x.fillStyle='white';x.fillRect(0,0,w,h);
      x.drawImage(img,0,0,w,h);return c.toDataURL('image/png').split(',')[1];
    }''', {'uri': uri, 'w': width, 'h': height})
    Path(destination).write_bytes(base64.b64decode(data))


def verify_project(path, browser=None):
    import fitz
    from PIL import Image
    from playwright.sync_api import sync_playwright
    from translate import project, safe, sha, write, digest
    from vector_assets import export_crop, embedded_raster_colors, source_crop_page, check_raster_completeness
    r, m, c = project(path)
    from structure_layout import read_map
    for source in c['sources']:
        if source.get('layout_ir'): read_map(r,source,c)
    before_content = digest(c)
    sources = {s['id']: s for s in c['sources']}
    out = r / 'reports/asset-fidelity'
    out.mkdir(parents=True, exist_ok=True)
    records = []
    exe = browser or os.environ.get('TRANSLATION_BROWSER')
    if not any(b.get('asset') for b in c['blocks']):
        report = {'gate_version': GATE_VERSION, 'assets': [], 'verified_source_crops': 0,
                  'native_review_required': 0, 'asset_repairs': 0, 'content_changed': False, 'meaning_verified': False}
        write(r / 'reports/asset-fidelity.json', report)
        return report
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, **({'executable_path': exe} if exe else {}))
        tab = br.new_page()
        tab.set_content('<!doctype html><title>Source figure comparison</title>')
        for b in [x for x in c['blocks'] if x.get('asset')]:
            asset = safe(r, b['asset'])
            source = sources[b['source']['document_id']]
            pdf = safe(r, source['file'])
            rec = {'block': b['id'], 'source_sha256': source['sha256'],
                   'source_page': b['source'].get('page'), 'bbox': b['source'].get('bbox'),
                   'original_asset': b['asset'], 'original_asset_sha256': sha(asset),
                   'native_text_exclusions': b['source'].get('native_text_exclusions',[]),
                   'raster_xrefs': b['source'].get('raster_xrefs')}
            if sha(pdf) != source['sha256']:
                raise ValueError('Figure source hash mismatch: ' + b['id'])
            if b.get('label_policy') == 'translated' or pdf.suffix.lower() != '.pdf' or not rec['bbox'] or not rec['source_page']:
                if asset.suffix.lower() == '.svg' and any(x['components'] not in (1, 3) for x in embedded_raster_colors(asset.read_bytes())):
                    raise ValueError('Unsafe SVG needs a source-bound re-export: ' + b['id'])
                rec['status'] = 'requires-native-source-visual-review'
                rec['reason'] = 'Intentional label edits or no comparable original-PDF geometry; do not overwrite with source pixels.'
                records.append(rec)
                continue
            with fitz.open(pdf) as doc:
                pg = doc[rec['source_page'] - 1]
                requested = fitz.Rect(rec['bbox'])
                if requested.is_empty or requested.is_infinite:
                    raise ValueError('Invalid figure source crop: ' + b['id'])
                # PDF image transforms can extend beyond the visible page.
                # Match the original page clipping instead of inventing pixels
                # outside the page or rejecting valid partially clipped artwork.
                bb = requested & pg.rect
                if bb.is_empty:
                    raise ValueError('Figure is completely outside the source page: ' + b['id'])
                rec['effective_visible_bbox'] = list(bb)
                rec['raster_completeness'] = check_raster_completeness(pg, bb, rec['raster_xrefs'])
                scale = min(2.5, 2400 / max(bb.width, bb.height))
                ref = out / (b['id'] + '-source.png')
                with source_crop_page(pg,rec['native_text_exclusions'],rec['raster_xrefs']) as reviewed:
                    reviewed.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=bb, colorspace=fitz.csRGB, alpha=False).save(ref)
                with Image.open(ref) as im:
                    width, height = im.size
                # Keep the original PDF image sampling/transform until print.
                # A previously rasterized crop introduces a second resampling
                # phase even at high DPI; native SVG also preserves mask context.
                if (asset.suffix.lower()=='.png' and not pg.rotation and
                    b.get('vector',{}).get('representation')=='source-rendered-png'):
                    try:
                        crop=export_crop(pg,bb,asset.with_suffix(''),scale=8,
                            native_text_exclusions=rec['native_text_exclusions'],raster_xrefs=rec['raster_xrefs'])
                        asset=crop['vector'];b['asset']=asset.relative_to(r).as_posix()
                        b['asset_sha256']=sha(asset);b['asset_fallback']=crop['fallback'].relative_to(r).as_posix()
                        b['asset_fallback_sha256']=sha(crop['fallback']);b['vector']=crop['metadata']
                        rec['native_image_sampling_restored']=True
                    except (ValueError,RuntimeError):pass
                if asset.suffix.lower()=='.png':
                    required_scale=min(8,4096/max(bb.width,bb.height))
                    with Image.open(asset) as raster:upgrade=raster.width<bb.width*required_scale*.98 or raster.height<bb.height*required_scale*.98
                    if upgrade:
                        with source_crop_page(pg,rec['native_text_exclusions'],rec['raster_xrefs']) as reviewed:
                            reviewed.get_pixmap(matrix=fitz.Matrix(required_scale,required_scale),clip=bb,colorspace=fitz.csRGB,alpha=False).save(asset)
                        b['asset_sha256']=sha(asset)
                        if b.get('asset_fallback')==b['asset']:b['asset_fallback_sha256']=sha(asset)
                        rec['resolution_upgrade_from_source']=True
                candidate = out / (b['id'] + '-browser.png')
                try:
                    browser_raster(tab, asset, candidate, width, height)
                    initial = compare_images(ref, candidate)
                except Exception as exc:
                    initial = {'pass': False, 'decoder_error': str(exc)}
                rec['initial_metrics'] = initial
                current = initial
                if asset.suffix.lower() == '.svg':
                    risky = any(x['components'] not in (1, 3) for x in embedded_raster_colors(asset.read_bytes()))
                    if risky or 'color_normalization' not in b.get('vector', {}):
                        try:
                            result = export_crop(pg, bb, asset.with_suffix(''), scale=scale,native_text_exclusions=rec['native_text_exclusions'],raster_xrefs=rec['raster_xrefs'])
                            b['vector'] = result['metadata']
                            b['asset_sha256'] = sha(asset)
                            b['asset_fallback'] = result['fallback'].relative_to(r).as_posix()
                            b['asset_fallback_sha256'] = sha(result['fallback'])
                            browser_raster(tab, asset, candidate, width, height)
                            current = compare_images(ref, candidate)
                            rec['reexported_from_source'] = True
                        except (ValueError, RuntimeError) as exc:
                            current = {'pass': False, 'export_error': str(exc)}
                rec['candidate_metrics'] = current
                if not current['pass']:
                    if b.get('label_policy') == 'translated':
                        raise ValueError('Intentional label edits require explicit source-relative visual review: ' + b['id'])
                    fallback = safe(r, b.get('asset_fallback', 'assets/' + b['id'] + '-source-rgb.png'))
                    if fallback.suffix.lower() != '.png':
                        raise ValueError('Source fallback must be PNG.')
                    fallback.parent.mkdir(parents=True, exist_ok=True)
                    fallback.write_bytes(ref.read_bytes())
                    prior = b['asset']
                    b['asset'] = fallback.relative_to(r).as_posix()
                    b['asset_sha256'] = sha(fallback)
                    if b.get('asset_fallback'):
                        b['asset_fallback_sha256'] = sha(fallback)
                    b.setdefault('vector', {}).update(representation='verified-source-raster-fallback',
                        retained_vector_asset=prior if asset.suffix.lower() == '.svg' else None,
                        reason='Browser/source appearance comparison failed; use opaque RGB source crop.')
                    browser_raster(tab, fallback, candidate, width, height)
                    rec['action'] = 'source-rendered-RGB-PNG-fallback'
                else:
                    rec['action'] = 'keep-source-matching-asset'
                final = compare_images(ref, candidate)
                if not final['pass']:
                    raise ValueError('Figure fidelity remains unsafe after fallback: ' + b['id'])
                if b.get('asset_fallback') and safe(r, b['asset_fallback']) != safe(r, b['asset']):
                    fp = safe(r, b['asset_fallback'])
                    fallback_browser = out / (b['id'] + '-fallback-browser.png')
                    try:
                        browser_raster(tab, fp, fallback_browser, width, height)
                        fm = compare_images(ref, fallback_browser)
                    except Exception as exc:
                        fm = {'pass': False, 'decoder_error': str(exc)}
                    rec['fallback_initial_metrics'] = fm
                    if not fm['pass']:
                        fp.write_bytes(ref.read_bytes())
                        b['asset_fallback_sha256'] = sha(fp)
                        browser_raster(tab, fp, fallback_browser, width, height)
                        rec['fallback_repaired'] = True
                    rec['fallback_final_metrics'] = compare_images(ref, fallback_browser)
                    if not rec['fallback_final_metrics']['pass']:
                        raise ValueError('Figure compatibility fallback is unsafe: ' + b['id'])
                rec.update(status='mechanical-source-appearance-pass', final_metrics=final,
                           asset=b['asset'], asset_sha256=sha(safe(r, b['asset'])),
                           reference=ref.relative_to(r).as_posix(), reference_sha256=sha(ref),
                           browser_render=candidate.relative_to(r).as_posix(), browser_sha256=sha(candidate))
                b['asset_fidelity'] = {'gate_version': GATE_VERSION, 'asset_sha256': rec['asset_sha256'],
                    'source_sha256': source['sha256'], 'page': rec['source_page'], 'bbox': rec['bbox'],
                    'mechanical_pass': True, 'visual_review': 'pending',
                    'fallback_sha256': sha(safe(r, b['asset_fallback'])) if b.get('asset_fallback') else None}
                records.append(rec)
        br.close()
    changed = before_content != digest(c)
    if changed:
        # Legitimate source-bound reexports can change asset hashes. Refresh
        # only after this gate's own repairs, never conceal unrelated IR edits.
        from structure_layout import write_map
        for source in c['sources']:
            if Path(source.get('file','')).suffix.lower()=='.pdf':write_map(r,c,source)
        write(r / 'content.json', c)
    report = {'gate_version': GATE_VERSION, 'assets': records,
              'verified_source_crops': sum(x['status'] == 'mechanical-source-appearance-pass' for x in records),
              'native_review_required': sum(x['status'] != 'mechanical-source-appearance-pass' for x in records),
              'asset_repairs': sum(x.get('action') == 'source-rendered-RGB-PNG-fallback' for x in records),
              'content_changed': changed, 'meaning_verified': False}
    write(r / 'reports/asset-fidelity.json', report)
    return report


def verify_rendered_figures(project_path, browser_page, pdf_path, edition, page_selector='#edPages>.ed-page'):
    """Compare source crops with the actual PDF pixels at DOM figure positions.

    This catches colors, opacity, clipping or CSS effects introduced after an
    otherwise safe asset was embedded. Failures require source/layout inspection.
    """
    import fitz
    from translate import project, read, safe, sha, write
    r, m, c = project(project_path)
    report = read(r / 'reports/asset-fidelity.json')
    references = {x['block']: x for x in report.get('assets', [])
                  if x.get('status') == 'mechanical-source-appearance-pass'}
    # page.pdf() temporarily enables print CSS, then restores the previous
    # media. Screen geometry can differ (e.g. collapsed block margins after
    # a column band), even when the PDF artwork itself is unchanged. Measure
    # in the same print media used by the PDF; never relax color thresholds
    # or search for a visually similar crop to hide a positioning defect.
    browser_page.emulate_media(media='print')
    dom = browser_page.evaluate('''selector=>[...document.querySelectorAll(selector)].map((p,i)=>{
      const r=p.getBoundingClientRect();return {page:i+1,w:r.width,h:r.height,images:
      [...p.querySelectorAll('figure[data-block] > img, figure[data-block] > picture > img')].map(im=>{
        const b=im.getBoundingClientRect(),cs=getComputedStyle(im);let nw=im.naturalWidth,nh=im.naturalHeight;
        // HTMLImageElement rounds SVG intrinsic dimensions to integers. Object
        // fit uses the fractional SVG ratio; rounding it shifts the PDF crop.
        if(im.src.startsWith('data:image/svg+xml')){
          const comma=im.src.indexOf(','),head=im.src.slice(0,comma),raw=im.src.slice(comma+1);
          const svg=new DOMParser().parseFromString(head.includes(';base64')?atob(raw):decodeURIComponent(raw),'image/svg+xml').documentElement;
          const vb=svg.getAttribute('viewBox')?.trim().split(/[ ,]+/).map(Number);
          if(vb?.length===4&&vb[2]>0&&vb[3]>0){nw=vb[2];nh=vb[3];}
        }
        return {
          block:im.closest('figure').dataset.block,x:b.x-r.x,y:b.y-r.y,w:b.width,h:b.height,
          nw,nh,fit:cs.objectFit,position:cs.objectPosition};
      })};})''', page_selector)
    output = r / 'reports/asset-fidelity' / edition
    output.mkdir(parents=True, exist_ok=True)
    records = []
    seen = set()
    sources = {s['id']: s for s in c['sources']}
    blocks = {b['id']: b for b in c['blocks']}
    with fitz.open(pdf_path) as doc:
        for item in dom:
            if item['page'] > len(doc):
                raise ValueError('Figure DOM/PDF page mismatch.')
            pg = doc[item['page'] - 1]
            for im in item['images']:
                if im['block'] not in references:
                    continue
                seen.add(im['block'])
                rec = {'block': im['block'], 'page': item['page']}
                x, y, w, h = [im[k] for k in ['x', 'y', 'w', 'h']]
                if min(w, h, im['nw'], im['nh']) <= 0:
                    rec.update(pass_=False, error='Figure has no visible geometry.')
                    rec['pass'] = False
                    records.append(rec)
                    continue
                # Current source-first layouts use centered contain, otherwise
                # require explicit visual review rather than guessing a crop.
                if im['fit'] in {'contain', 'scale-down'}:
                    factor = min(w / im['nw'], h / im['nh'])
                    if im['fit'] == 'scale-down':
                        factor = min(1, factor)
                    vw, vh = im['nw'] * factor, im['nh'] * factor
                    if abs(vw-w) > .5 or abs(vh-h) > .5:
                        if im['position'] not in {'50% 50%', 'center center', 'center'}:
                            records.append({**rec, 'pass': False, 'error': 'Noncentered object-fit requires inspected crop geometry.'})
                            continue
                        x += (w-vw)/2
                        y += (h-vh)/2
                        w, h = vw, vh
                elif im['fit'] in {'cover', 'none'}:
                    records.append({**rec, 'pass': False, 'error': 'Figure may crop source artwork; inspect object-fit.'})
                    continue
                # Chromium prints at 96 CSS px / 72 PDF pt with scale=1.
                # Its rounded MediaBox is not an independent x/y scale.
                bb = fitz.Rect(x * .75, y * .75, (x+w) * .75, (y+h) * .75)
                if not pg.rect.contains(bb):
                    records.append({**rec, 'pass': False, 'error': 'Figure extends beyond the PDF page.'})
                    continue
                dest = output / (im['block'] + '-p' + str(item['page']) + '.png')
                expected = dest.with_name(dest.stem + '-expected.png')
                block = blocks[im['block']]
                source = sources[block['source']['document_id']]
                source_file = safe(r, source['file'])
                if sha(source_file) != source['sha256']:
                    raise ValueError('Figure source hash mismatch: ' + im['block'])
                with fitz.open(source_file) as source_pdf:
                    source_page = source_pdf[block['source']['page'] - 1]
                    source_bbox = fitz.Rect(block['source']['bbox']) & source_page.rect
                    metrics = compare_pdf_region(source_page, source_bbox, pg, bb, expected, dest,block['source'].get('native_text_exclusions'),block['source'].get('raster_xrefs'))
                records.append({**rec, **metrics, 'pdf_bbox': list(bb),
                                'reference_sha256': references[im['block']]['reference_sha256'],
                                'expected_crop': expected.relative_to(r).as_posix(),
                                'expected_sha256': sha(expected),
                                'rendered_crop': dest.relative_to(r).as_posix(), 'rendered_sha256': sha(dest)})
    missing = sorted(set(references) - seen)
    result = {'edition': edition, 'pdf_sha256': sha(pdf_path), 'media': 'print',
              'comparison_method': PDF_COMPARISON_VERSION, 'figures': records,
              'missing_figures': missing, 'pass': not missing and all(x.get('pass') for x in records),
              'meaning_verified': False}
    write(r / 'reports' / ('figure-pdf-' + edition + '.json'), result)
    return result


def release_errors(r, m, c):
    """Bind the mandatory figure gate to current source/asset bytes and bounds."""
    from translate import read, safe, sha
    errors = []
    blocks = [b for b in c['blocks'] if b.get('asset')]
    if not blocks:
        return errors
    manifest = r / 'reports/asset-fidelity.json'
    if not manifest.exists():
        return [{'code': 'asset-fidelity-report-missing'}]
    report = read(manifest)
    records = {x['block']: x for x in report.get('assets', [])}
    if report.get('gate_version') != GATE_VERSION or set(records) != {b['id'] for b in blocks}:
        return [{'code': 'asset-fidelity-coverage-stale'}]
    sources = {x['id']: x for x in c['sources']}
    for b in blocks:
        rec = records[b['id']]
        source = sources[b['source']['document_id']]
        if rec.get('source_sha256') != source['sha256'] or rec.get('source_page') != b['source'].get('page') or rec.get('bbox') != b['source'].get('bbox') or rec.get('native_text_exclusions',[]) != b['source'].get('native_text_exclusions',[]) or rec.get('raster_xrefs') != b['source'].get('raster_xrefs'):
            errors.append({'code': 'asset-fidelity-source-stale', 'block': b['id']})
        if rec.get('status') == 'requires-native-source-visual-review':
            # The existing all-page visual evidence contract still applies.
            # Do not turn this branch into a mechanical appearance pass.
            if rec.get('original_asset_sha256') != sha(safe(r, b['asset'])):
                errors.append({'code': 'native-asset-review-stale', 'block': b['id']})
            continue
        if not rec.get('final_metrics', {}).get('pass') or rec.get('asset') != b['asset'] or rec.get('asset_sha256') != sha(safe(r, b['asset'])):
            errors.append({'code': 'asset-fidelity-failed-or-stale', 'block': b['id']})
        for file_key, hash_key in [('reference', 'reference_sha256'), ('browser_render', 'browser_sha256')]:
            fp = safe(r, rec.get(file_key, 'missing'))
            if not fp.is_file() or sha(fp) != rec.get(hash_key):
                errors.append({'code': 'asset-fidelity-evidence-stale', 'block': b['id'], 'kind': file_key})
        if b.get('asset_fallback') and sha(safe(r, b['asset_fallback'])) != b.get('asset_fidelity', {}).get('fallback_sha256'):
            errors.append({'code': 'asset-fidelity-fallback-stale', 'block': b['id']})
    return errors


def rendered_release_errors(r, m, c):
    """Require source-relative checks of every delivered edition's PDF figures."""
    from translate import read, safe, sha
    if not any(b.get('asset') for b in c['blocks']):
        return []
    manifest = r / 'reports/asset-fidelity.json'
    if not manifest.exists():
        return [{'code': 'pdf-figure-source-evidence-missing'}]
    references = {x['block']: x for x in read(manifest).get('assets', [])
                  if x.get('status') == 'mechanical-source-appearance-pass'}
    expected = set(references)
    errors = []
    for language in m['target_languages']:
        for edition in m['editions'] + ['alignment']:
            name = language + '-' + edition
            file = r / 'reports' / ('figure-pdf-' + name + '.json')
            pdf = r / 'outputs' / (name + '.pdf')
            if not file.exists() or not pdf.exists():
                errors.append({'code': 'pdf-figure-evidence-missing', 'edition': name})
                continue
            report = read(file)
            if report.get('media') != 'print' or report.get('comparison_method') != PDF_COMPARISON_VERSION or not report.get('pass') or report.get('pdf_sha256') != sha(pdf) or report.get('missing_figures') or {x['block'] for x in report.get('figures', [])} != expected:
                errors.append({'code': 'pdf-figure-evidence-failed-or-stale', 'edition': name})
            for image in report.get('figures', []):
                reference = references.get(image['block'], {})
                if image.get('reference_sha256') != reference.get('reference_sha256'):
                    errors.append({'code': 'pdf-figure-source-reference-stale', 'edition': name, 'block': image['block']})
                crop = safe(r, image.get('rendered_crop', 'missing'))
                if not image.get('pass') or not crop.is_file() or sha(crop) != image.get('rendered_sha256'):
                    errors.append({'code': 'pdf-figure-crop-failed-or-stale', 'edition': name, 'block': image['block']})
                crop = safe(r, image.get('expected_crop', 'missing'))
                if image.get('comparison_method') != PDF_COMPARISON_VERSION or not crop.is_file() or sha(crop) != image.get('expected_sha256'):
                    errors.append({'code': 'pdf-figure-expected-crop-stale', 'edition': name, 'block': image['block']})
    return errors


if __name__ == '__main__':
    from runtime_encoding import configure_utf8
    configure_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project')
    parser.add_argument('--browser')
    args = parser.parse_args()
    report = verify_project(args.project, args.browser)
    print(json.dumps({k: v for k, v in report.items() if k != 'assets'}, indent=2))
