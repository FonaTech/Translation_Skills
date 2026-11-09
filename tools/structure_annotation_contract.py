"""Source-authored annotation order, separate from inference geometry. MIT."""


def source_identities(document):
    """Include recorded originals of repaired, converted or OCR-derived copies."""
    parents=document.get('source_parent_sha256',[])
    if not isinstance(parents,list):raise ValueError('Source parent identities must be a list.')
    values=parents+([document['source_sha256']] if document.get('source_sha256') else [])
    for identity in values:
        if not isinstance(identity,str) or len(identity)!=64 or any(c not in '0123456789abcdef' for c in identity):
            raise ValueError('Invalid source lineage SHA-256.')
    return set(values)


def reviewed_group_lines(page):
    """Order labeled prose by reviewed regions, never PDF object serialization.

    Within a region preserve explicitly authored source-row order. Missing region
    evidence falls back to stored order; it cannot certify reading order.
    """
    lines = page['lines']
    regions = page.get('_order_regions', [])
    flat = [lid for region in regions for lid in region]
    if len(flat) != len(set(flat)):
        raise ValueError('Repeated source row in annotation reading order.')
    ids = {row['id'] for row in lines}
    if set(flat) - ids:
        raise ValueError('Unknown source row in annotation reading order.')
    ranks = {lid: rank for rank, lid in enumerate(flat)}
    groups = {}
    for row in lines:
        if row['text'].strip():
            groups.setdefault(row.get('_group', row['id']), []).append(row)
    if regions:
        for group in groups.values():
            group.sort(key=lambda row: ranks.get(row['id'], len(ranks)))
    return groups
