"""Source-evidenced visible/hidden reading layers, retaining native accounting.

No recognition or inferred wording replaces the visible native source. Exact
duplicates can share a row. A geometrically coincident conflicting hidden row
can remain an explicit alternate to an unchanged visible primary, never a
semantic correction. Copyright Yufeng Zhan. MIT.
"""
from collections import defaultdict
from difflib import SequenceMatcher
import re


def _identity(name):
    return re.sub(r'^[A-Z]{6}\+', '', name).casefold().replace(' ', '')


def annotate_visibility(page, lines):
    if not hasattr(page, 'get_texttrace'):
        return
    positions = defaultdict(set)
    for trace in page.get_texttrace():
        kind = 'invisible' if trace.get('type', 0) >= 3 or trace.get('opacity', 1) <= 0 else 'visible'
        for _, _, origin, _ in trace['chars']:
            positions[(_identity(trace['font']), round(origin[0], 2), round(origin[1], 2))].add(kind)
    for line in lines:
        for span in line.get('spans', []):
            for char in span.get('chars', []):
                origin = char.get('origin', [])
                if len(origin) != 2:
                    continue
                choices = positions.get((_identity(span.get('font', '')), round(origin[0], 2), round(origin[1], 2)), set())
                # PyMuPDF records zero alpha on an invisible raw span even
                # where a visible span has the same font and exact origin.
                alpha = span.get('alpha')
                if alpha == 0 and 'invisible' in choices:
                    char['source_visibility'] = 'invisible'
                elif alpha is not None and alpha > 0 and 'visible' in choices:
                    char['source_visibility'] = 'visible'
                elif len(choices) == 1:
                    char['source_visibility'] = next(iter(choices))


def _signature(row, allow_outlines=False):
    characters = []
    counts = defaultdict(int)
    for span in row.get('spans', []):
        if not span.get('chars'):
            return None, None
        for char in span['chars']:
            text = char.get('c', '')
            if text.isspace():
                continue
            glyph = char.get('native_glyph', {})
            if (char.get('unicode_unresolved') and glyph.get('empty_outline') and
                    char.get('bbox', [0, 0, 0, 0])[2] > char['bbox'][0]):
                # Source-proven blank advance is ignored for duplicate
                # comparison only; its original code and geometry survive.
                continue
            if char.get('unicode_unresolved') or any(ord(c) < 32 or c == '\ufffd' for c in text):
                if not allow_outlines or not glyph.get('svg') or glyph.get('empty_outline'):
                    return None, None
                # Comparison placeholder only. It never enters source text,
                # translations, or a claim that the glyph has been decoded.
                text = '\ufffd'
            characters.append(text)
            counts[char.get('source_visibility', 'unknown')] += 1
    text = ''.join(characters)
    if not text:
        return None, None
    total = sum(counts.values())
    for kind in ['visible', 'invisible']:
        other = 'invisible' if kind == 'visible' else 'visible'
        if counts[kind] >= total*.8 and not counts[other]:
            return text, kind
    return None, None


def _coincident(a, b):
    if __package__:
        from .source_structure import text_baseline
    else:
        from source_structure import text_baseline
    if a.get('direction', [1, 0]) != b.get('direction', [1, 0]):
        return False
    aa, bb = a['bbox'], b['bbox']
    size = min(a['size'], b['size'])
    width_ratio = (aa[2]-aa[0])/max(.01, bb[2]-bb[0])
    overlap = max(0, min(aa[2], bb[2])-max(aa[0], bb[0]))/max(.01, min(aa[2]-aa[0], bb[2]-bb[0]))
    return (.85 <= width_ratio <= 1.15 and overlap >= .95 and
            abs(text_baseline(a)-text_baseline(b)) <= max(1.5, size*.3) and
            abs((aa[1]+aa[3]-bb[1]-bb[3])/2) <= max(1.5, size*.3))


def deduplicate(rows):
    """Select a unique unchanged visible reading row; archive hidden evidence.

    Exact short rows include captions, list heads and equation/page numbers.
    Conflicts require long similar native text and coincident source geometry.
    Similarity identifies a candidate layer pair, not a semantic confidence.
    Missing outline evidence and ambiguous visible owners stay separate.
    """
    signatures = {row['id']: _signature(row) for row in rows}
    descriptions = {row['id']: _signature(row, allow_outlines=True) for row in rows}
    visible = [row for row in rows if descriptions[row['id']][1] == 'visible']
    removed, records = set(), []
    for row in rows:
        text, kind = descriptions[row['id']]
        if kind != 'invisible' or abs(row.get('direction', [1, 0])[1]) > .05:
            continue
        choices = []
        for candidate in visible:
            if not _coincident(candidate, row):
                continue
            original = signatures[row['id']][0]
            target = signatures[candidate['id']][0]
            exact = original is not None and original == target
            other = descriptions[candidate['id']][0]
            matcher = SequenceMatcher(None, text, other, autojunk=False)
            similarity = matcher.ratio() if not exact else 1
            # A short math symbol cannot establish a competing prose layer.
            # Keep an unresolved outline primary only when substantial known
            # source wording outside it corroborates the layer correspondence.
            known = min(len(text.replace('\ufffd', '')), len(other.replace('\ufffd', '')))
            primary_known = len(other.replace('\ufffd', ''))
            matching_known = sum(len(other[m.b:m.b+m.size].replace('\ufffd', ''))
                                 for m in matcher.get_matching_blocks())
            known_fraction = matching_known/max(1, primary_known)
            outline_bound_alternate = ('\ufffd' in other and primary_known >= 20 and
                primary_known >= len(other)*.75 and known_fraction >= .95)
            if exact or known >= 20 and similarity >= .9 or outline_bound_alternate:
                choices.append((candidate, exact, similarity, known_fraction))
        if len(choices) != 1:
            continue
        owner, exact, similarity, known_fraction = choices[0]
        native_ids = row.get('native_line_ids', [row['id']])
        proof = {'native_line_ids': native_ids[:], 'text': row['text'], 'bbox': row['bbox'][:],
                 'method': ('identical-nonspace-visible-and-invisible-source-rows' if exact else
                            'visible-native-primary-with-conflicting-hidden-alternate'),
                 'visible_owner': owner['id'], 'source_wording_changed': False,
                 'comparison_ignores_only_whitespace_and_source_proven_empty_advances': exact}
        if not exact:
            proof.update(visible_text=owner['text'], conflict_resolved=False,
                         candidate_text_similarity=similarity,
                         primary_known_source_fraction=known_fraction,
                         similarity_is_semantic_confidence=False,
                         review_required=True)
        owner['native_line_ids'] = list(dict.fromkeys(owner.get('native_line_ids', [owner['id']])+native_ids))
        owner.setdefault('duplicate_text_layers' if exact else 'alternate_text_layers', []).append(proof)
        removed.add(row['id']); records.append(proof)
    return [row for row in rows if row['id'] not in removed], records
