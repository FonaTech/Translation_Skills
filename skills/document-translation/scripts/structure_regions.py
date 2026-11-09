"""Learned contextual refinements and source-preserving region relationships.

Copyright 2026 Yufeng Zhan. MIT. No generated text, OCR or formula transcription.
The specialist is optional; existing role/link checkpoints retain their contract.
"""
from __future__ import annotations
import math
import re
import statistics

REVISION = '1.0.1-region-context-2'
CLASSES = ['retain', 'code', 'footnote', 'math', 'prose', 'heading', 'index', 'contents', 'label']
FEATURES = ['size_ratio','width','top','left','length','letters','digits','spaces','mono_fraction',
            'bold','italic','math_font_fraction','math_symbols','bad_glyph_fraction','code_syntax',
            'code_cluster','raised_leading_marker','note_chain','note_distance','equation_band',
            'equation_number','math_stack_overlap','prose_tail','long_prose','prose_above',
            'prose_below','same_font_above','same_font_below','previous_gap','next_gap',
            'left_alignment_above','left_alignment_below','native_long_prose','page_index',
            'page_contents','trailing_page_number','numbered_heading','heading_font_contrast',
            'marginal','graphic_membership','caption_prefix','reference_prefix','list_marker',
            'footer_repetition','font_body_overlap','small_span_fraction','baseline_spread',
            'block_width','block_mean_length','line_indent','terminal','code_punctuation','source_list_chain','source_figure_band','heading_following_block','repeated_margin']
CODE = re.compile(r'^\s*(?:module\b|endmodule\b|always\s*@|begin\s*:|end\s*;?$|(?:input|output|reg|wire)\s+\[|'
                  r'(?:def|class|import|from|return|for|while|if|else|elif|try|except)\b|#include\b|'
                  r'(?:\w+[.:/-]*)?[>#%$]\s+\w|(?:set|read_hdl|read_verilog|create_clock|report_timing)\s+|'
                  r'(?:const|let|var|function)\s+\w|\w+\s*\([^)]*\)\s*\{)')
EQUATION_NUMBER = re.compile(r'^\(\s*\d+(?:[.\-]\d+)*[a-z]?\s*\)$')
MATHFONT = re.compile(r'math|symbol|cmsy|cmex|cmmi|mtex|mtsy|mtmi', re.I)
MONO = re.compile(r'courier|mono|consolas|menlo|inconsolata|liberationmono', re.I)
MATH = set('=±∑∫√∞∂∇≈≠≤≥×÷∈∝∼∏∧∨⊂⊆⊗ΣΠψΨφΦαβγδεθλμρσΩℏ≡⟨⟩')
BAD = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]')

def box_union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]

def baseline(row):
    spans = [s for s in row.get('spans', []) if s.get('text', '').strip()]
    return statistics.median(s.get('origin', [0, row['bbox'][3]])[1] for s in spans) if spans else row['bbox'][3]

def fraction(row, pattern):
    spans = row.get('spans', [])
    return sum(len(s.get('text', '').strip()) for s in spans if pattern.search(s.get('font', ''))) / max(1, sum(len(s.get('text', '').strip()) for s in spans))

def leading_marker(row):
    spans = sorted([s for s in row.get('spans', []) if s.get('text', '').strip()], key=lambda s: s['bbox'][0])
    if len(spans) < 2:
        return None
    first = spans[0]; rest = [s for s in spans[1:] if len(s.get('text', '').strip()) >= 2]
    text = first.get('text', '').strip()
    if not rest or not re.fullmatch(r'\d{1,3}|[*†‡]', text):
        return None
    main = max(rest, key=lambda s: len(s['text']))
    if (first.get('size', row['size']) <= main.get('size', row['size']) * .94 and
            main.get('origin', [0, 0])[1] - first.get('origin', [0, 0])[1] > row['size'] * .15):
        return text
    return None

def context(page, profile):
    """Measure relations once per page, without annotations or learned predictions."""
    rows = [r for r in page['lines'] if r['text'].strip()]
    size = max(1, profile['body_size']); width = page['width']; height = page['height']
    by_id = {r['id']: r for r in rows}
    data = {r['id']: {'mono': fraction(r, MONO), 'mathfont': fraction(r, MATHFONT),
                     'marker': leading_marker(r), 'code_group': None, 'note_group': None,
                     'math_group': None} for r in rows}
    # Code syntax is corroborated by a *dominant* monospaced font, then propagated
    # only through adjacent same-font monospaced rows (including literal end/}).
    monos = sorted([r for r in rows if data[r['id']]['mono'] >= .75 and not BAD.search(r['text'])], key=lambda r: (r['bbox'][1], r['bbox'][0]))
    adjacency = {r['id']: set() for r in monos}
    for i, a in enumerate(monos):
        for b in monos[i+1:]:
            if b['bbox'][1] - a['bbox'][3] > max(a['size'], b['size']) * 2.2:
                break
            if (abs(math.log(max(.1, a['size']) / max(.1, b['size']))) < .12 and
                    abs(a['bbox'][0] - b['bbox'][0]) < size * 7 and
                    b['bbox'][1] > a['bbox'][1] + size * .3 and
                    not any(x['id'] not in {a['id'], b['id']} and data[x['id']]['mono'] < .5 and
                            a['bbox'][3] < x['bbox'][1] < b['bbox'][1] and
                            min(a['bbox'][2], x['bbox'][2]) > max(a['bbox'][0], x['bbox'][0]) for x in rows)):
                adjacency[a['id']].add(b['id']); adjacency[b['id']].add(a['id'])
    seen = set()
    for row in monos:
        if row['id'] in seen:
            continue
        stack = [row['id']]; group = []
        while stack:
            lid = stack.pop()
            if lid in seen:
                continue
            seen.add(lid); group.append(lid); stack.extend(adjacency[lid] - seen)
        if any(CODE.search(by_id[lid]['text']) for lid in group):
            gid = 'code:' + min(group)
            for lid in group:
                data[lid]['code_group'] = gid
    notes = [r for r in rows if not BAD.search(r['text']) and data[r['id']]['marker'] and r['size'] < size * .94 and
             len(r['text'].strip()) > 15 and not data[r['id']]['code_group']]
    for row in rows:
        if BAD.search(row['text']):
            continue
        candidates = []
        for seed in notes:
            if row['bbox'][1] < seed['bbox'][1] - .5 or row['bbox'][1] - seed['bbox'][3] > size * 18:
                continue
            if (abs(math.log(max(.1, row['size']) / max(.1, seed['size']))) > .12 or
                    abs(row['bbox'][0] - seed['bbox'][0]) > seed['size'] * 1.3 or
                    row['bbox'][2] > max(seed['bbox'][2], seed['bbox'][0] + width * .34) + size):
                continue
            chain = sorted([x for x in rows if seed['bbox'][1] - .5 <= x['bbox'][1] <= row['bbox'][1] + .5 and
                            abs(x['bbox'][0] - seed['bbox'][0]) < size and
                            abs(x['size'] - seed['size']) < size * .12], key=lambda x: x['bbox'][1])
            if (any(data[x['id']]['marker'] and x['id'] != seed['id'] for x in chain) or
                    any(b['bbox'][1] - a['bbox'][3] > seed['size'] * 1.5 for a, b in zip(chain, chain[1:]))):
                continue
            candidates.append(seed)
        if candidates:
            seed = max(candidates, key=lambda x: x['bbox'][1])
            data[row['id']]['note_group'] = 'footnote:' + seed['id']
            data[row['id']]['note_marker'] = data[seed['id']]['marker']
            data[row['id']]['note_distance'] = (row['bbox'][1] - seed['bbox'][1]) / size
    # Anchor each numbered equation in its source column. Expand through a
    # bounded math region until actual prose, another equation or column edge.
    # This accommodates multi-line displays and below-display equation numbers.
    anchors=[]
    def mathematical(row):
        text=row['text'].strip();info=data[row['id']]
        if BAD.search(text):return False
        if info['code_group'] or info['note_group'] or len(text)>180:return False
        if re.match(r'^(?:and|the|this|where|for|with|so|if|at|in|particular|hence|now|since|thus|consider|it|we|let|from|here|each)\b',text,re.I):return False
        if (row['bbox'][1]<height*.09 or row['bbox'][3]>height*.91) and re.fullmatch(r'\d{1,4}',text):return False
        previous=[x for x in rows if x['native_block']==row['native_block'] and
                  0<baseline(row)-baseline(x)<size*1.65 and len(x['text'])>45 and
                  len(re.findall(r'[A-Za-z]{3,}',x['text']))>=5 and
                  abs(x['bbox'][0]-row['bbox'][0])<size*1.5]
        if previous and len(re.findall(r'[A-Za-z]{3,}',text))>=3:return False
        words=re.findall(r'[A-Za-z]{3,}',text)
        # Damaged text mappings are not mathematical evidence. Treating control
        # glyphs as an equation cue turns entire broken-font paragraphs into
        # formula regions; preserve them for review instead.
        math_evidence=info['mathfont']>.2 or any(c in MATH for c in text)
        # Mathematical displays may contain descriptive words (e.g. "pure
        # imaginary quantity"). Ordinary prose with occasional math is a barrier.
        if len(words)>=4 and len(' '.join(words))>len(text)*.35:return False
        if math_evidence:return True
        return bool(re.fullmatch(r'[\d\s.,+−–*/()\[\]{}|\u23a1-\u23b0]+',text) or (not words and re.search(r'\d',text) and len(text)<18) or re.fullmatch(r'[a-zA-Z]{1,2}[.,]?',text))
    equation_numbers=[row for row in rows if EQUATION_NUMBER.fullmatch(row['text'].strip())]
    embedded_numbers=[row for row in rows if not EQUATION_NUMBER.fullmatch(row['text'].strip()) and re.search(r'\(\s*\d+(?:[.\-]\d+)+[a-z]?\s*\)\s*$',row['text'].strip()) and mathematical(row)]
    for anchor in equation_numbers:
        right=anchor['bbox'][2]+size
        narrative=[row for row in rows if len(row['text'])>55 and len(re.findall(r'[A-Za-z]{3,}',row['text']))>=7 and
                   abs(row['bbox'][2]-anchor['bbox'][2])<width*.15 and
                   not data[row['id']]['note_group'] and not data[row['id']]['code_group'] and
                   not mathematical(row)]
        local=sorted(narrative,key=lambda row:abs(baseline(row)-baseline(anchor)))[:6]
        left=min((row['bbox'][0] for row in local),default=0)-size
        above=[row for row in narrative if baseline(row)<baseline(anchor)-size*.4]
        below=[row for row in narrative if baseline(row)>baseline(anchor)+size*.4]
        top=max((row['bbox'][3] for row in above),default=anchor['bbox'][1]-size*8)-size*.15
        bottom=min((row['bbox'][1] for row in below),default=anchor['bbox'][3]+size*8)+size*.15
        other_numbers=[x for x in equation_numbers+embedded_numbers if x['id']!=anchor['id'] and
                       left<=x['bbox'][0] and abs(x['bbox'][2]-anchor['bbox'][2])<width*.25]
        prior=[x for x in other_numbers if baseline(x)<baseline(anchor)]
        later=[x for x in other_numbers if baseline(x)>baseline(anchor)]
        if prior:top=max(top,max(x['bbox'][3] for x in prior)+size*.1)
        if later:bottom=min(bottom,min(x['bbox'][1] for x in later)-size*.1)
        # A short source prose fragment is a boundary too, even when it does not
        # meet the long narrative threshold (e.g. "This leaves the equation").
        barriers=[x for x in rows if not mathematical(x) and not BAD.search(x['text']) and not data[x['id']]['code_group'] and
                  not data[x['id']]['note_group'] and left<=x['bbox'][0] and
                  x['bbox'][2]<=right and len(re.findall(r'[A-Za-z]{3,}',x['text']))>=3]
        upper=[x for x in barriers if baseline(x)<baseline(anchor)]
        lower=[x for x in barriers if baseline(x)>baseline(anchor)]
        if upper:top=max(top,max(x['bbox'][3] for x in upper)-size*.15)
        if lower:bottom=min(bottom,min(x['bbox'][1] for x in lower)+size*.15)
        top=max(top,anchor['bbox'][1]-size*8);bottom=min(bottom,anchor['bbox'][3]+size*8)
        members=[row for row in rows if row['id']!=anchor['id'] and row not in equation_numbers and
                 left<=row['bbox'][0] and row['bbox'][2]<=right and
                 top<=baseline(row)<=bottom and
                 (mathematical(row) or BAD.search(row['text']))]
        if any(data[row['id']]['mathfont']>.2 or any(c in MATH for c in row['text']) for row in members):
            anchors.append((anchor,members))
    for row in rows:
        choices=[(abs(baseline(row)-baseline(anchor)),anchor) for anchor,members in anchors
                 if row in members or row['id']==anchor['id']]
        if choices:
            anchor=min(choices,key=lambda x:x[0])[1]
            data[row['id']]['math_group']='equation:'+anchor['id']
    # Unnumbered display equations still need a source-spatial region. Restrict
    # seeds to compact mathematical rows, then connect nearby fragments in 2D;
    # short inline prose such as "at q = 0" is explicitly excluded.
    unnumbered=[]
    for row in rows:
        info=data[row['id']];text=row['text'].strip()
        if BAD.search(text):
            if info['mathfont']>=.3:unnumbered.append(row)
            continue
        prior=[x for x in rows if x['id']!=row['id'] and x['native_block']==row['native_block'] and
               x['bbox'][1]<row['bbox'][1]-.5 and abs(x['bbox'][0]-row['bbox'][0])<row['size']*.6 and
               0<baseline(row)-baseline(x)<row['size']*1.6]
        previous=max(prior,key=lambda x:x['bbox'][1]) if prior else None
        prose_tail=bool(previous and len(previous['text'].split())>=6 and len(previous['text'].strip())>=40 and
                        not re.search(r'[.!?:]\s*$',previous['text']) and len(text.split())>=2)
        if info['math_group'] or info['code_group'] or info['note_group'] or prose_tail:
            continue
        words=re.findall(r'[A-Za-z]{3,}',text)
        operator_fraction=sum(c in MATH for c in text)/max(1,len(text))
        if len(text)>180 or len(words)>7 or (len(words)>=4 and len(' '.join(words))>len(text)*.5):
            continue
        if info['mathfont']>=.3 or operator_fraction>=.08:
            unnumbered.append(row)
    seeds=list(unnumbered)
    for row in rows:
        if not BAD.search(row['text']) or row in unnumbered:continue
        for seed in seeds:
            if row['native_block']!=seed['native_block']:continue
            gap_y=max(0,row['bbox'][1]-seed['bbox'][3],seed['bbox'][1]-row['bbox'][3])
            gap_x=max(0,row['bbox'][0]-seed['bbox'][2],seed['bbox'][0]-row['bbox'][2])
            if gap_y<=max(row['size'],seed['size'])*1.9 and gap_x<=max(profile['body_size']*5,width*.055):
                unnumbered.append(row);break
    components=[];unseen={row['id'] for row in unnumbered};lookup={row['id']:row for row in unnumbered}
    for row in unnumbered:
        if row['id'] not in unseen:continue
        unseen.remove(row['id']);stack=[row['id']];component=[]
        while stack:
            current=lookup[stack.pop()];component.append(current);a=current['bbox'];
            neighbors=[]
            for lid in unseen:
                other=lookup[lid];b=other['bbox'];gap_y=max(0,b[1]-a[3],a[1]-b[3])
                gap_x=max(0,b[0]-a[2],a[0]-b[2])
                aligned=gap_x<=max(profile['body_size']*5,width*.055)
                nearby=gap_y<=max(current['size'],other['size'])*1.9
                if aligned and nearby:
                    neighbors.append(lid)
            for lid in neighbors:unseen.remove(lid);stack.append(lid)
        has_math=any(data[x['id']]['mathfont']>=.3 or any(c in MATH for c in x['text']) for x in component)
        if has_math:components.append(component)
    for component in components:
        if not any(data[row['id']]['math_group'] for row in component):
            gid='equation-region:'+min(row['id'] for row in component)
            for row in component:data[row['id']]['math_group']=gid
    page_index = any(re.fullmatch(r'(?:subject |author )?index', r['text'].strip(), re.I) for r in rows[:12])
    page_contents = any(re.fullmatch(r'(?:table of )?contents', r['text'].strip(), re.I) for r in rows[:12])
    import source_structure as base_structure
    caption_seeds=[x for x in rows if base_structure.caption_anchor(x,page) and not re.match(r'^\s*table\b',x['text'],re.I)]
    for row in rows:
        info = data[row['id']]; box = row['bbox']; rs = max(1, row['size'])
        col = [x for x in rows if x['id'] != row['id'] and abs(x['bbox'][0] - box[0]) <= rs * 2.8 and
               abs(math.log(max(.1, x['size']) / rs)) < .22]
        above = [x for x in col if x['bbox'][1] < box[1] - rs * .3 and -rs < box[1] - x['bbox'][3] < rs * 2.5]
        below = [x for x in col if x['bbox'][1] > box[1] + rs * .3 and -rs < x['bbox'][1] - box[3] < rs * 2.5]
        previous = max(above, key=lambda r: r['bbox'][1]) if above else None
        following = min(below, key=lambda r: r['bbox'][1]) if below else None
        peers = [x for x in rows if x['native_block'] == row['native_block']]
        long_peers = [x for x in peers if len(x['text'].strip()) >= 45 and len(x['text'].split()) >= 6]
        tail = bool(previous and previous['native_block'] == row['native_block'] and
                    len(previous['text'].split()) >= 6 and len(previous['text'].strip()) >= 40 and
                    abs(previous['bbox'][0] - box[0]) < rs * .6 and
                    0 < baseline(row) - baseline(previous) < rs * 1.6 and
                    not re.search(r'[.!?:]\s*$', previous['text']) and
                    len(row['text'].split()) >= 2 and not info['math_group'] and not info['code_group'])
        explicit_lists=[x for x in peers if base_structure.list_marker(x,page) and
                        abs(x['size']-row['size']) < size*.12 and x['bbox'][1]<=box[1]+.5]
        list_chain=bool(explicit_lists and any(0<=box[0]-x['bbox'][0]<size*4 for x in explicit_lists))
        figure_band=False;figure_group=None
        for cap in caption_seeds:
            if not (box[3]<=cap['bbox'][1]+1 and cap['bbox'][0]-size*1.5<=(box[0]+box[2])/2<=cap['bbox'][2]+size*1.5):continue
            previous_caps=[c for c in caption_seeds if c['bbox'][1]<cap['bbox'][1] and
                           cap['bbox'][0]-size<=(c['bbox'][0]+c['bbox'][2])/2<=cap['bbox'][2]+size]
            floor=max((c['bbox'][3] for c in previous_caps),default=page['height']*.09)
            graphics=[g for g in page.get('graphic_regions',[]) if floor<=g[1]<cap['bbox'][1] and
                      cap['bbox'][0]-size<=(g[0]+g[2])/2<=cap['bbox'][2]+size]
            if graphics and box[1]>=max(floor,min(g[1] for g in graphics)-size*3) and cap['bbox'][1]-box[3]<height*.35:
                figure_band=not long_peers and len(row['text'])<60 and not info['note_group'] and not info['code_group']
                if figure_band:figure_group='figure:'+cap['id']
        following_blocks=[x for x in rows if x['native_block']!=row['native_block'] and
                          box[3]-.5<=x['bbox'][1]<box[3]+size*3 and
                          box[0]-size*2.5<=x['bbox'][0]<=box[0]+size*4]
        next_block=min(following_blocks,key=lambda x:x['bbox'][1]) if following_blocks else None
        info.update(figure_group=figure_group,list_chain=list_chain,figure_band=figure_band,next_block=next_block,
                    repeated_margin=bool((box[1]<height*.09 or box[3]>height*.91) and not figure_band and base_structure.furniture_key(row,page) in profile.get('repeated_furniture',[])),
                    previous=previous, following=following, peers=peers, prose_tail=tail,
                    native_long_prose=len(long_peers), page_index=page_index, page_contents=page_contents)
    return data

def features(row, page, profile, contexts):
    info = contexts[row['id']]; text = row['text'].strip(); box = row['bbox']; n = max(1, len(text))
    size = max(1, row['size']); base = max(1, profile['body_size']); width = page['width']; height = page['height']
    prev = info['previous']; nxt = info['following']; peers = info['peers']
    origins = [s.get('origin', [0, 0])[1] for s in row.get('spans', []) if s.get('text', '').strip()]
    def long(r): return bool(r and len(r['text'].strip()) >= 45 and len(r['text'].split()) >= 6)
    trailing = bool(re.search(r'(?:\s|\.\.)\s*(?:\d+(?:[–,-]\d+)*|[ivxlcdm]+)\s*$', text, re.I))
    math_overlap = sum(x['id'] != row['id'] and contexts[x['id']]['mathfont'] > .2 and
                       min(x['bbox'][2], box[2]) > max(x['bbox'][0], box[0]) and
                       max(0, x['bbox'][1]-box[3], box[1]-x['bbox'][3]) < size for x in page['lines'] if x['id'] in contexts)
    block_box = box_union([r['bbox'] for r in peers])
    return [math.log(size/base), (box[2]-box[0])/width, box[1]/height, box[0]/width, math.log1p(n)/6,
            sum(c.isalpha() for c in text)/n, sum(c.isdigit() for c in text)/n, text.count(' ')/n,
            info['mono'], float(bool(row['flags'] & 16) or bool(re.search(r'bold|cmbx', row['font'], re.I))),
            float(bool(row['flags'] & 2)), info['mathfont'], sum(c in MATH for c in text)/n,
            len(BAD.findall(text))/n, float(bool(CODE.search(text))), float(bool(info['code_group'])),
            float(bool(info['marker'])), float(bool(info['note_group'])), min(1, info.get('note_distance', 0)/20),
            float(bool(info['math_group'])), float(bool(EQUATION_NUMBER.fullmatch(text))), min(1, math_overlap/3),
            float(info['prose_tail']), float(long(row)), float(long(prev)), float(long(nxt)),
            float(bool(prev and prev['font'] == row['font'])), float(bool(nxt and nxt['font'] == row['font'])),
            max(-2, min(5, (box[1]-prev['bbox'][3])/size if prev else 5)),
            max(-2, min(5, (nxt['bbox'][1]-box[3])/size if nxt else 5)),
            min(5, abs(box[0]-prev['bbox'][0])/size) if prev else 5,
            min(5, abs(box[0]-nxt['bbox'][0])/size) if nxt else 5,
            min(1, info['native_long_prose']/5), float(info['page_index']), float(info['page_contents']),
            float(trailing), float(bool(re.match(r'^\d+(?:\.\d+)+\s+\w', text))),
            float(bool(nxt and nxt['font'] != row['font'] and long(nxt))),
            float(box[1] < height*.09 or box[3] > height*.91),
            float(any(b[0] <= (box[0]+box[2])/2 <= b[2] and b[1] <= (box[1]+box[3])/2 <= b[3] for b in page.get('graphic_regions', []))),
            float(bool(re.match(r'^(?:Fig(?:ure)?\.?|Table)\s*\d', text))),
            float(bool(re.match(r'^\[\d+\]', text))), float(bool(re.match(r'^(?:[•●▪]|\(\d+\)|\d+[.)])\s', text))),
            float(bool((box[1] < height*.09 or box[3] > height*.91) and any(re.sub(r'\d+', '#', text.casefold()) in str(k).casefold() for k in profile.get('repeated_furniture', [])))),
            float(row['font'].casefold() in profile.get('body_fonts', [])),
            sum(len(s.get('text', '')) for s in row.get('spans', []) if s.get('size', size) < size*.92)/n,
            min(3, (max(origins)-min(origins))/size) if origins else 0,
            (block_box[2]-block_box[0])/width, math.log1p(sum(len(x['text']) for x in peers)/len(peers))/6,
            (box[0]-block_box[0])/size, float(bool(re.search(r'[.!?:]\s*$', text))),
            sum(c in '{}[];_@|&~' for c in text)/n,float(info['list_chain']),float(info['figure_band']),
            float(bool(info['next_block'])),float(info['repeated_margin'])]

def refine(rows, page, profile, decisions, head, predictor):
    """Use a learned head with source-evidence gates; retain out-of-domain proposals."""
    contexts = context(page, profile)
    eligible = [r for r in rows if r['id'] in contexts]
    probabilities = predictor(head['network'], [features(r, page, profile, contexts) for r in eligible])
    proposals = {}
    for row, probs in zip(eligible, probabilities):
        rank = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)
        kind = CLASSES[rank[0]]; score = probs[rank[0]]; margin = score-probs[rank[1]]
        info = contexts[row['id']]; base = decisions[row['id']]
        source_text_damaged=bool(BAD.search(row['text']))
        accepted = score >= head.get('threshold', .9) and margin >= .4
        gates = {'retain': True, 'code': bool(info['code_group']), 'footnote': bool(info['note_group']),
                 'math': bool(info['math_group']),
                 'prose': bool(info['prose_tail'] or len(row['text'].split()) >= 6) and not info['code_group'] and not info['note_group'] and not info['math_group'] and not info['list_chain'] and not info['figure_band'],
                 'heading': bool(not info['page_index'] and not info['page_contents'] and info['next_block'] and not info['figure_band'] and not info['repeated_margin'] and
                                 len(row['text'].strip()) < 150 and
                                 (row['flags'] & 16 or re.search(r'bold|cmbx', row['font'], re.I)) and
                                 len(info['next_block']['text'].split()) >= 2),
                 'index': info['page_index'] and .09 < row['bbox'][1]/page['height'] < .95,
                 'contents': info['page_contents'] and .09 < row['bbox'][1]/page['height'] < .95,
                 'label': bool(base['assigned_role'] in {'label','body','heading'} and not info['native_long_prose'] and not info['note_group'] and len(row['text']) < 35)}
        accepted = accepted and bool(gates.get(kind)) and not source_text_damaged
        semantic = None
        if accepted and kind != 'retain':
            role = {'code':'body','footnote':'metadata','math':'equation','prose':'body',
                    'heading':'heading','index':'body','contents':'body','label':'label'}[kind]
            if kind == 'prose' and base['assigned_role'] not in {'body','equation','list'}:
                accepted = False
            else:
                base.update(assigned_role=role, review_required=False, rule='learned-region-'+kind)
                semantic = {'code':'code','footnote':'footnote','math':'equation','prose':'body',
                            'heading':'heading','index':'index','contents':'contents','label':'label'}[kind]
                base['semantic_role'] = semantic
        proposals[row['id']] = {'class': kind, 'score': round(score, 6), 'margin': round(margin, 6),
                                 'applied': bool(accepted and kind != 'retain'), 'semantic_role': semantic,
                                 **({'blocked_by':'unresolved-native-glyph'} if source_text_damaged else {})}
        base['region_prediction'] = proposals[row['id']]
        if info['list_chain'] and not info['note_group'] and not info['code_group']:
            base.update(assigned_role='list',semantic_role='list',rule='source-explicit-list-chain',review_required=False)
        if info['repeated_margin']:
            base.update(assigned_role='metadata',semantic_role='metadata',rule='source-repeated-margin',review_required=False)
    # Constrained graph decoding: a confidently learned region seed propagates
    # through a measured marker/font/alignment chain, not across a native block.
    for group_key,kind,role in [('note_group','footnote','metadata'),('code_group','code','body'),('math_group','math','equation'),('figure_group','label','label')]:
        grouped={}
        for row in eligible:
            gid=contexts[row['id']].get(group_key)
            if gid:grouped.setdefault(gid,[]).append(row)
        for gid,members in grouped.items():
            seeds=[row for row in members if not BAD.search(row['text']) and proposals[row['id']]['applied'] and proposals[row['id']]['class']==kind]
            fallback=not seeds and kind=='math' and any(decisions[row['id']]['assigned_role']=='equation' for row in members)
            if not seeds and not fallback:continue
            for row in members:
                dec=decisions[row['id']]
                if BAD.search(row['text']):
                    dec.update(assigned_role=role,semantic_role='equation',review_required=True,
                               rule='source-spatial-equation-region-unresolved-glyph')
                    dec['region_evidence']={'group':gid,'seed_line_ids':[x['id'] for x in seeds],
                                            'decoding':'spatial membership retained; native glyph mapping unresolved'}
                    continue
                dec.update(assigned_role=role,semantic_role='equation' if kind=='math' else kind,
                           review_required=fallback,rule='source-math-region-pending-review' if fallback else 'learned-seed-with-source-region-chain')
                dec['region_evidence']={'group':gid,'seed_line_ids':[x['id'] for x in seeds],
                                        'decoding':'source-constrained graph; not independent per-row confidence'}
    return contexts, proposals

def structured_groups(rows, decisions, contexts):
    """Expose spatial/line structures without inventing formula trees or cell truth."""
    groups = {}
    for row in rows:
        dec = decisions[row['id']]; info = contexts.get(row['id'], {})
        kind = dec.get('semantic_role')
        gid = info.get({'code':'code_group','footnote':'note_group','equation':'math_group'}.get(kind, ''))
        if kind in {'index','contents'}:gid=kind+':'+row['id']
        if not gid:
            continue
        groups.setdefault((kind, gid), []).append(row)
    result = []
    for (kind, gid), members in groups.items():
        members.sort(key=lambda r: (r['bbox'][1], r['bbox'][0]))
        result.append({'id': gid, 'kind': kind, 'members': members,
                       'bbox': box_union([r['bbox'] for r in members]),
                       'representation': 'source-spatial-region' if kind == 'equation' else 'source-line-block'})
    return result

def note_anchors(groups, rows):
    """Match actual raised source markers; never infer an absent reference."""
    notes = []
    for group in groups:
        if group['kind'] != 'footnote':
            continue
        members = group['members']; marker = leading_marker(members[0])
        if BAD.search(members[0]['text']):
            notes.append({'type':'footnote-reference','region_id':group['id'],'marker':marker,
                          'anchors':[],'status':'unresolved-damaged-source-glyph'})
            continue
        candidates = []
        for row in rows:
            if row in members or BAD.search(row['text']):
                continue
            spans=[sp for sp in row.get('spans',[]) if sp.get('text','').strip()]
            for si,span in enumerate(spans):
                if (span.get('text', '').strip() == marker and span.get('size', row['size']) < row['size']*.94 and
                        baseline(row)-span.get('origin', [0, 0])[1] > row['size']*.15):
                    before=spans[si-1] if si else None
                    after=spans[si+1] if si+1<len(spans) else None
                    # Adjacent mathematical glyphs or a same-rise fraction are
                    # exponent evidence, not footnote references.
                    if before and MATHFONT.search(before.get('font','')):continue
                    if after:
                        after_text=after.get('text','').strip()
                        same_rise=abs(after.get('origin',[0,0])[1]-span.get('origin',[0,0])[1])<row['size']*.12
                        # A marker before a mathematical variable (for example
                        # "finds^8 J = ...") can still be a footnote. Reject
                        # mathematical continuations only when the raised span
                        # itself continues as digits/fraction syntax.
                        if (MATHFONT.search(after.get('font','')) and re.match(r'^[0-9/+−-]',after_text)) or (same_rise and re.match(r'^[0-9/+−-]',after_text)):
                            continue
                    candidates.append({'line_id': row['id'], 'bbox': span['bbox'], 'marker': marker})
        notes.append({'type':'footnote-reference', 'region_id':group['id'], 'marker':marker,
                      'anchors':candidates, 'status':'source-marker-matched' if len(candidates)==1 else 'ambiguous-multiple-source-markers' if candidates else 'unresolved-no-source-marker'})
    return notes


def overlapping_layers(rows):
    """Detect competing damaged/clean text mappings without deleting either.

    Geometry alone cannot verify OCR. The proposal is a review relation, never
    permission to silently prefer a plausible-looking transcription.
    """
    problematic=[row for row in rows if BAD.search(row['text'])]
    candidates=[row for row in rows if row['text'].strip() and sum(c.isalpha() for c in row['text'])>=4]
    relations=[];seen=set()
    for row in problematic:
        a=row['bbox'];matches=[]
        for peer in candidates:
            if peer['id']==row['id']:
                continue
            b=peer['bbox'];intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
            denominator=max(1,min((a[2]-a[0])*(a[3]-a[1]),(b[2]-b[0])*(b[3]-b[1])))
            pair=tuple(sorted((row['id'],peer['id'])))
            if (intersection/denominator>=.65 and
                    abs(baseline(row)-baseline(peer))<max(row['size'],peer['size']) and pair not in seen):
                matches.append(peer['id']);seen.add(pair)
        if matches:
            relations.append({'type':'competing-overlapping-text-layer','native_line_id':row['id'],
                              'alternative_line_ids':matches,'status':'unresolved-source-transcription-review',
                              'both_layers_may_be_damaged':any(BAD.search(next(x['text'] for x in rows if x['id']==lid)) for lid in matches)})
    return relations
