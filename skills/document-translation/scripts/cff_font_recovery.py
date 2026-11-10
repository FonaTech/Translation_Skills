"""Bounded CFF/reference outline evidence, without generated source wording.

Reference fonts stay local. Ambiguous glyphs remain unresolved. Numeric shape
tolerances are engineering bounds, not calibrated Unicode accuracy.
Copyright 2026 Yufeng Zhan. MIT.
"""
from collections import defaultdict
from functools import lru_cache
import hashlib
import io
import math
import unicodedata

BOUNDS_TOLERANCE = 2.0  # Normalized units per 1000 em.
ADVANCE_TOLERANCE = 1.0
INK_MISS_MAX = .005
INK_DELTA_MAX = .06
CORRESPONDENCE_MIN = 16
CORRESPONDENCE_FRACTION = .95


def outline(glyph, glyphset, scale):
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    path = SVGPathPen(glyphset)
    bounds = BoundsPen(glyphset)
    matrix = (scale, 0, 0, scale, 0, 0)
    glyph.draw(TransformPen(path, matrix))
    glyph.draw(TransformPen(bounds, matrix))
    return {'path': path.getCommands(), 'bbox': bounds.bounds,
            'advance': glyph.width * scale}


def unicode_candidates(name, values):
    from fontTools.agl import toUnicode
    values = {cp for cp in values if 0 <= cp <= 0x10ffff and
              unicodedata.category(chr(cp)) not in {'Cc', 'Co', 'Cf', 'Cs'}}
    canonical = toUnicode(name)
    if len(canonical) == 1 and (ord(canonical) in values or any(
            unicodedata.normalize('NFKC', canonical) == unicodedata.normalize('NFKC', chr(cp))
            for cp in values)):
        return {ord(canonical)}
    return values


def reference_glyphs(data):
    from fontTools.ttLib import TTFont
    with TTFont(io.BytesIO(data)) as face:
        glyphset = face.getGlyphSet()
        by_name = defaultdict(set)
        for cp, name in (face.getBestCmap() or {}).items():
            by_name[name].add(cp)
        result = []
        for name, values in by_name.items():
            choices = unicode_candidates(name, values)
            if not choices:
                continue
            try:
                item = outline(glyphset[name], glyphset, 1000/face['head'].unitsPerEm)
            except (ValueError, TypeError, KeyError, AssertionError):
                continue
            result.append({**item, 'gid': face.getGlyphID(name), 'cps': sorted(choices)})
        return result


def reference_names(data):
    from fontTools.ttLib import TTFont
    with TTFont(io.BytesIO(data), lazy=True) as face:
        return {entry.toUnicode() for entry in face['name'].names if entry.nameID in {4, 6}}


@lru_cache(maxsize=12)
def local_reference(path, mtime, size):
    from pathlib import Path
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest(), reference_glyphs(data), reference_names(data)


def _raster(item, bounds):
    import fitz
    from PIL import Image
    left, bottom, right, top = bounds
    width, height = right-left, top-bottom
    # Both paths use one fixed physical grid (512 pixels/em). No registration,
    # independent resizing, glyph shift or text-dependent threshold is allowed.
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" '
           f'width="{math.ceil(width*.512)}" height="{math.ceil(height*.512)}" '
           f'viewBox="{left} {-top} {width} {height}">'
           f'<path d="{item["path"]}" transform="scale(1,-1)"/></svg>')
    with fitz.open(stream=svg.encode('utf-8'), filetype='svg') as document:
        pixmap = document[0].get_pixmap(alpha=False)
    return Image.frombytes('RGB', (pixmap.width, pixmap.height), pixmap.samples).convert('L')


def compare_outlines(source, reference):
    from PIL import ImageChops, ImageFilter, ImageStat
    a, b = source['bbox'], reference['bbox']
    if not a or not b:
        return None
    advance_delta = abs(source['advance']-reference['advance'])
    bounds_delta = max(abs(x-y) for x, y in zip(a, b))
    if advance_delta > ADVANCE_TOLERANCE or bounds_delta > BOUNDS_TOLERANCE:
        return None
    bounds = (min(a[0], b[0])-3, min(a[1], b[1])-3,
              max(a[2], b[2])+3, max(a[3], b[3])+3)
    if max(bounds[2]-bounds[0], bounds[3]-bounds[1]) > 4000:
        return None
    left, right = _raster(source, bounds), _raster(reference, bounds)
    aa = left.point(lambda value: 255 if value < 160 else 0)
    bb = right.point(lambda value: 255 if value < 160 else 0)
    def pixels(image):
        return image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata()
    ink = sum(v > 0 for v in pixels(aa)) + sum(v > 0 for v in pixels(bb))
    if not ink:
        return None
    missing = ImageChops.subtract(aa, bb.filter(ImageFilter.MaxFilter(3)))
    extra = ImageChops.subtract(bb, aa.filter(ImageFilter.MaxFilter(3)))
    miss = (sum(v > 0 for v in pixels(missing)) + sum(v > 0 for v in pixels(extra)))/ink
    delta = sum(ImageStat.Stat(ImageChops.difference(left, right)).sum)/(ink*255)
    if miss > INK_MISS_MAX or delta > INK_DELTA_MAX:
        return None
    return {'advance_delta': advance_delta, 'bounds_delta': bounds_delta,
            'unsupported_ink_fraction': miss, 'normalized_ink_delta': delta}


def choose_mappings(source, references):
    """Require per-glyph evidence; original CID correspondence needs a quorum.

    At least 16 nonempty glyphs and 95% of the complete embedded subset must
    corroborate a reference's CID/GID correspondence before it can resolve a
    homoglyph or blank-space ambiguity. This ratio is not an accuracy score.
    Unique outline candidates remain usable without that correspondence.
    """
    matches = defaultdict(list)
    correspondence = {}
    visible = [item for item in source if item['bbox']]
    for reference in references:
        rid = reference['sha256']
        supported = set()
        for item in source:
            for candidate in reference['glyphs']:
                if not item['bbox']:
                    if (not candidate['bbox'] and candidate['cps'] == [32] and
                            item['advance'] > 0 and
                            abs(item['advance']-candidate['advance']) <= ADVANCE_TOLERANCE):
                        metrics = {'empty_source_advance': True}
                    else:
                        continue
                else:
                    metrics = compare_outlines(item, candidate)
                    if metrics is None:
                        continue
                entry = {'reference_sha256': rid, 'reference_gid': candidate['gid'],
                         'unicode_candidates': candidate['cps'], **metrics}
                matches[item['cid']].append(entry)
                if item['bbox'] and candidate['gid'] == item['cid']:
                    supported.add(item['cid'])
        correspondence[rid] = {'nonempty_source_glyphs': len(visible),
                               'matching_cid_glyphs': len(supported),
                               'accepted': (len(supported) >= CORRESPONDENCE_MIN and
                                            len(supported)/max(1, len(visible)) >= CORRESPONDENCE_FRACTION)}
    mapping, glyph_evidence = {}, []
    for item in source:
        candidates = matches[item['cid']]
        correlated = [c for c in candidates if c['reference_gid'] == item['cid'] and
                      correspondence[c['reference_sha256']]['accepted']]
        choices = {cp for c in (correlated or candidates) for cp in c['unicode_candidates']}
        # An empty outline is never evidence for a letter or arbitrary Unicode
        # whitespace; only a corroborated ordinary-space CID may be recovered.
        if not item['bbox'] and not correlated:
            choices = set()
        if len(choices) == 1:
            value = next(iter(choices))
            if item['bbox'] or value == 32:
                mapping[item['cid']] = chr(value)
        glyph_evidence.append({'cid': item['cid'], 'selected': mapping.get(item['cid']),
                               'correspondence_used': bool(correlated), 'candidates': candidates})
    return mapping, {'correspondence': correspondence, 'glyphs': glyph_evidence,
                     'thresholds': {'bounds_per_1000_em': BOUNDS_TOLERANCE,
                                    'advance_per_1000_em': ADVANCE_TOLERANCE,
                                    'unsupported_ink_fraction': INK_MISS_MAX,
                                    'normalized_ink_delta': INK_DELTA_MAX,
                                    'correspondence_min_glyphs': CORRESPONDENCE_MIN,
                                    'correspondence_fraction': CORRESPONDENCE_FRACTION}}


def recover(data, embedded, local, font_key):
    """Read a supported Identity CFF and family-matched Unicode references."""
    from fontTools.cffLib import CFFFontSet
    fonts = CFFFontSet()
    fonts.decompile(io.BytesIO(data), None)
    if len(fonts.fontNames) != 1:
        return {}, None
    top = fonts[fonts.fontNames[0]]
    if (getattr(top, 'ROS', None) != ('Adobe', 'Identity', 0) or
            list(top.FontMatrix) != [.001, 0, 0, .001, 0, 0] or
            any(fd.rawDict.get('FontMatrix') for fd in getattr(top, 'FDArray', []))):
        return {}, None
    names = [name.decode('ascii') if isinstance(name, bytes) else name for name in fonts.fontNames]
    aliases = {font_key(name) for name in names}
    if getattr(top, 'FullName', None):
        aliases.add(font_key(top.FullName))
    references, known = [], set()
    for family, reference_data in embedded:
        digest = hashlib.sha256(reference_data).hexdigest()
        if family not in aliases or digest in known:
            continue
        try:
            if not aliases & {font_key(n) for n in reference_names(reference_data)}:
                continue
            glyphs = reference_glyphs(reference_data)
        except (ValueError, KeyError, AssertionError):
            continue
        references.append({'sha256': digest, 'glyphs': glyphs}); known.add(digest)
    for path in sorted(set(local)):
        if font_key(path.stem) not in aliases:
            continue
        try:
            stat = path.stat()
            digest, glyphs, names_in_reference = local_reference(str(path), stat.st_mtime_ns, stat.st_size)
            if not aliases & {font_key(n) for n in names_in_reference}:
                continue
        except (OSError, ValueError, KeyError, AssertionError):
            continue
        if digest not in known:
            references.append({'sha256': digest, 'glyphs': glyphs}); known.add(digest)
    if not references:
        return {}, None
    source = []
    for name in top.charset:
        if not name.startswith('cid') or not name[3:].isdigit():
            continue
        glyph = top.CharStrings[name]
        source.append({**outline(glyph, None, 1), 'cid': int(name[3:])})
    mapping, evidence = choose_mappings(source, references)
    return mapping, {'method': 'bounded-cff-reference-outlines-and-advance',
                      'trace_font_names': names, 'reference_sha256': sorted(known),
                      'source_font_sha256': hashlib.sha256(data).hexdigest(),
                      'unicode_review_required': True, 'semantic_certification': False, **evidence}
