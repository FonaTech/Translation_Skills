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


def source_checks(text):
    normalized = unicodedata.normalize('NFKC', text)
    return {
        'numbers': re.findall(r'[+−-]?\d+(?:[.,]\d+)*(?:[eE][+−-]?\d+)?', normalized),
        'citation_anchors': re.findall(r'\[[^]\n]{1,100}\]', text),
        'literal_tokens': re.findall(r'(?<!\w)(?:N/A|NA|NULL|NaN|https?://[^\s]+|[\w.+-]+@[\w.-]+)(?!\w)', text),
        'scope_cues': re.findall(r'\b(?:not|no|never|only|unless|except|may|might|must|shall|should|approximately|at least|at most|less than|more than)\b', text, re.I),
        'risks': (['control-characters: inspect original before translation'] if any(ord(x)<32 and x not in '\n\t\r' for x in text) else [])
                 + (['long-unit: preserve the whole unit; do not abridge'] if len(text)>6000 else []),
        'meaning_check': ['actor/action/object', 'conditions/exceptions', 'negation/comparisons', 'uncertainty/claim scope', 'names/units/symbols', 'all selected source content'],
    }


def prepare(content, language, editions, include_all, split_text, title='', context_chars=1000):
    all_units = [(b, u) for b in content['blocks'] for u in b.get('units', [])]
    heading = {}
    items = []
    for index, (block, unit) in enumerate(all_units):
        did = block['source']['document_id']
        previous_heading = heading.get(did, '')
        if block['type'] == 'heading':
            heading[did] = unit['source']
        if not include_all and all(unit.get('translations', {}).get(language, {}).get(e) is not None for e in editions):
            continue
        neighbors = {}
        for label, offset in [('previous', -1), ('next', 1)]:
            j = index + offset
            if 0 <= j < len(all_units):
                nb, nu = all_units[j]
                if nb['source']['document_id'] == did:
                    neighbors[label] = {'id': nu['id'], 'source': clip_context(nu['source'], context_chars)}
        context = {'document_title': title, 'block_type': block['type'],
                   'document_page_or_element': block['source'], 'preceding_heading': previous_heading,
                   'neighbors_for_context_only': neighbors}
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
