"""Bounded, resumable task packets for the invoking language-model loop.

This module only prepares source material. No function translates or certifies it.
Copyright 2026 Yufeng Zhan. MIT.
"""
import re
import unicodedata


def clip_context(text, limit):
    if len(text) <= limit:
        return text
    half = max(1, (limit - 40) // 2)
    return text[:half] + ' [context clipped; not source content] ' + text[-half:]


def cue_context(text, pattern, *, radius=90, limit=16):
    """Expose exact source spans; these are review prompts, never repairs."""
    result = []
    for match in re.finditer(pattern, text, re.I):
        start, end = max(0, match.start() - radius), min(len(text), match.end() + radius)
        result.append({'cue': match.group(), 'offset': [match.start(), match.end()],
                       'context_offset': [start, end], 'context': text[start:end]})
        if len(result) >= limit:
            break
    return result


def source_checks(text):
    normalized = unicodedata.normalize('NFKC', text)
    return {
        'numbers': re.findall(r'[+−-]?\d+(?:[.,]\d+)*(?:[eE][+−-]?\d+)?', normalized),
        'citation_anchors': re.findall(r'\[[^]\n]{1,100}\]', text),
        'literal_tokens': re.findall(r'(?<!\w)(?:N/A|NA|NULL|NaN|https?://[^\s]+|[\w.+-]+@[\w.-]+)(?!\w)', text),
        'scope_cues': re.findall(r'\b(?:not|no|never|only|unless|except|may|might|must|shall|should|approximately|at least|at most|less than|more than|all|every|entire|respectively|compared to|compared with|first|one of the first|essential|necessary|validate[sd]?|support[sed]*)\b', text, re.I),
        'study_cues': re.findall(r'\b(?:simulat\w*|experiment\w*|measur\w*|propos\w*|present\w*|implement\w*|theoretic\w*)\b', text, re.I),
        'comparative_cues': re.findall(r'\b(?:more|less|lower|higher|greater|smaller|larger|similar|different|compared|relative|than|whereas|respectively|first|earliest)\b', text, re.I),
        'explicit_abbreviation_context': re.findall(r'[^.;\n]{1,100}\([A-Za-z][A-Za-z0-9 /-]{1,24}\)', text),
        'claim_scope_context': cue_context(
            text, r'\b(?:can|could|may|might|would|will|shall|must|should|never|not|only|unless|except|respectively|propos\w*|plan\w*|intend\w*|simulat\w*|experiment\w*|validat\w*)\b'),
        'quantity_context': cue_context(
            text, r'(?<!\w)[+−-]?\d+(?:[.,]\d+)*(?:[eE][+−-]?\d+)?(?:\s*(?:%|[A-Za-zμµτΩ°][A-Za-z0-9μµτΩ°²³/−-]*))?',
            radius=55, limit=24),
        'context_contract': 'Exact excerpts with zero-based offsets into this source unit. Preserve the subject, modality, quantity sign/unit and respective mapping. A capability to validate is not an experiment already performed; a proposed or planned circuit is not a fabricated implementation. These bounded English-oriented prompts are incomplete and never authorize source correction.',
        'possible_boundary_fragment': {
            'starts_lowercase': bool(re.match(r'^\s*[a-z]', text)),
            'ends_hyphen': bool(re.search(r'[-‐‑]\s*$', text)),
            'ends_without_terminal': bool(text.strip()) and not bool(re.search(r'[.!?。！？:：;；][\]”’"\')]*\s*$', text)),
            'source_prefix': text[:96],
            'source_suffix': text[-96:],
            'meaning': 'Heuristic inspection prompts only. Map every visible prefix/suffix word to this unit. Verify source pages; never omit an unfinished noun phrase or borrow/move words across unchanged IDs.',
        },
        'risks': (['control-characters: inspect original before translation'] if any(ord(x)<32 and x not in '\n\t\r' for x in text) else [])
                 + (['long-unit: preserve the whole unit; do not abridge'] if len(text)>6000 else []),
        'meaning_check': ['actor/action/object', 'conditions/exceptions', 'negation/comparisons', 'uncertainty/claim scope', 'names/units/symbols', 'all selected source content'],
    }


def prepare(content, language, editions, include_all, split_text, title='', context_chars=1000):
    from figure_regions import translation_eligible
    active_blocks = [b for b in content['blocks'] if translation_eligible(b, content['blocks'])]
    all_units = [(b, u) for b in active_blocks for u in b.get('units', [])]
    heading = {}
    items = []
    for index, (block, unit) in enumerate(all_units):
        did = block['source']['document_id']
        previous_heading = heading.get(did, '')
        if block['type'] == 'heading':
            heading[did] = unit['source']
        # A stored empty target is still pending for nonempty source. Literal
        # blanks, zero and N/A are not interchangeable. Do not let resume hide
        # incomplete work supplied by a partial packet or an older extractor.
        targets = unit.get('translations', {}).get(language, {})
        source_has_text = bool(unit['source'].strip())
        complete = all(isinstance(targets.get(e), str) and
                       (bool(targets[e].strip()) or not source_has_text)
                       for e in editions)
        if not include_all and complete:
            continue
        neighbors = {}
        for label, offset in [('previous', -1), ('next', 1)]:
            j = index + offset
            if 0 <= j < len(all_units):
                nb, nu = all_units[j]
                if nb['source']['document_id'] == did:
                    neighbors[label] = {'id': nu['id'], 'source': clip_context(nu['source'], context_chars)}
        # Page furniture or a figure can intervene between fragments. Supply a
        # separate, bounded prose context without silently joining source units.
        narrative = {}
        for label, step in [('previous', -1), ('next', 1)]:
            for distance in range(1, 33):
                j = index + step * distance
                if not 0 <= j < len(all_units):
                    break
                nb, nu = all_units[j]
                if nb['source']['document_id'] != did:
                    break
                role = nb.get('presentation', {}).get('role', nb.get('role', 'body'))
                if nb['type'] == 'paragraph' and role in {'body', 'abstract'} and nu['source'].strip():
                    narrative[label] = {'id': nu['id'], 'locator': nb['source'],
                                        'source': clip_context(nu['source'], context_chars)}
                    break
        context = {'document_title': title, 'block_type': block['type'],
                   'document_page_or_element': block['source'], 'contributing_source_segments': unit.get('source_segments', []), 'preceding_heading': previous_heading,
                   'neighbors_for_context_only': neighbors,
                   'narrative_neighbors_for_context_only': narrative,
                   'layout_hint':block.get('layout_hint'),
                   'related_figures':[{'block_id':f.get('id'),'asset':f.get('asset'),'crop_text':f.get('crop_text'),'caption_block_ids':f.get('caption_block_ids',[]),'proposal':f.get('figure_region')} for f in active_blocks if f.get('crop_text') and (block.get('id') in f.get('caption_block_ids',[]) or f['source'].get('document_id')==did and f['source'].get('page')==block['source'].get('page') and block.get('structure',{}).get('semantic_role')=='label')]}
        items.append({'id': unit['id'], 'source': unit['source'], 'type': block['type'], 'locator': block['source'],
                      'context': context, 'source_checks': source_checks(unit['source']),
                      'source_sentences': [{'index': i, 'source': s} for i, s in enumerate(split_text(unit['source']), 1)],
                      **{e: unit.get('translations', {}).get(language, {}).get(e, '') for e in editions}})
    return items


def batches(items, max_units, max_chars):
    current = []
    count = 0
    for item in items:
        size = len(item['source'])
        # Keep an oversized unit intact and explicitly visible; never truncate it.
        different_document = current and current[-1]['locator']['document_id'] != item['locator']['document_id']
        if current and (len(current)>=max_units or count+size>max_chars or different_document):
            yield current
            current, count = [], 0
        current.append(item)
        count += size
    if current:
        yield current
