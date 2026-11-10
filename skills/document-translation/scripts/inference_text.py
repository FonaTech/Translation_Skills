"""Source-supported typography for limited translation models. MIT.

No translations, lexical corrections, OCR, or inferred acronyms are supplied.
Original unit text stays immutable. Every case change has a same-document
lowercase witness; source identifiers and formula strings are never normalized.
"""
import re

REVISION = '1.0.3-source-typography-input-1'
WORD = re.compile(r'[A-Za-z]{4,}')
HEADING_MARKER = re.compile(r'^\s*(?:[IVXLCDM]+\.|[A-Z]\.|\d+(?:\.\d+)*[.)])(?=\s|[\x00-\x1f])')


def prepare(content):
    witnesses = {}
    for block in content.get('blocks', []):
        if (block.get('type') == 'heading' or
                block.get('structure', {}).get('semantic_role') in {'title', 'heading'}):
            continue
        document = block.get('source', {}).get('document_id')
        for unit in block.get('units', []):
            for word in WORD.finditer(unit['source']):
                if word.group().islower():
                    witnesses.setdefault(document, {}).setdefault(word.group(), {
                        'unit_id': unit['id'], 'start': word.start(), 'end': word.end(),
                        'source': word.group()})
    for block in content.get('blocks', []):
        heading = (block.get('type') == 'heading' or
                   block.get('structure', {}).get('semantic_role') in {'title', 'heading'})
        document = block.get('source', {}).get('document_id')
        for unit in block.get('units', []):
            unit.pop('inference_context', None)
            if not heading:
                continue
            marker = HEADING_MARKER.match(unit['source'])
            if marker:
                rec = {'start': marker.start(), 'end': marker.end(), 'source': marker.group(),
                       'kind': 'structural-heading-marker', 'evidence': 'decoded-source-heading'}
                known = unit.setdefault('protected_identifiers', [])
                if not any(rec['start'] < old['end'] and old['start'] < rec['end'] for old in known):
                    known.append(rec); known.sort(key=lambda r: r['start'])
            lower = {word.group().lower(): witnesses[document][word.group().lower()]
                     for word in WORD.finditer(unit['source']) if word.group().isupper()
                     and word.group().lower() in witnesses.get(document, {})}
            if lower:
                unit['inference_context'] = {'revision': REVISION, 'kind': 'source-heading-casing',
                    'lowercase_witnesses': lower, 'source_text_changed': False,
                    'semantic_certification': False}
    return content


def prompt_text(source, context=None):
    """Change case only for witnessed heading words; preserve every offset."""
    context = context or {}
    if context.get('revision') != REVISION or context.get('kind') != 'source-heading-casing':
        return source, []
    witnesses = context.get('lowercase_witnesses', {})
    changes = []
    def replace(match):
        word = match.group(); lower = word.lower()
        witness = witnesses.get(lower)
        if not word.isupper() or not witness or witness.get('source') != lower:
            return word
        normalized = lower.capitalize() if not source[:match.start()].strip() else lower
        changes.append({'start': match.start(), 'end': match.end(), 'before': word,
                        'after': normalized, 'witness': witness,
                        'operation': 'source-witnessed-heading-case-only'})
        return normalized
    result = WORD.sub(replace, source)
    assert len(result) == len(source) and result.casefold() == source.casefold()
    return result, changes
