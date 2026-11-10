"""Learned contextual refinements and source-preserving region relationships.

Copyright 2026 Yufeng Zhan. MIT. No generated text, OCR or formula transcription.
The specialist is optional; existing role/link checkpoints retain their contract.
"""
from __future__ import annotations
import math
import re
import statistics

REVISION = '1.0.1-region-context-2'
DECODER_REVISION = '1.0.3-region-decoder-21-native-prose-boundaries'
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
SHELL_PROMPT = r'(?:[A-Za-z_][\w.@-]*:[^\s<>|]*|\[[^\]\n]+\]|[\w.@/~-]+)?[>#%$]\s+\S+'
CODE = re.compile(r'^\s*(?:' + SHELL_PROMPT + r'|module\b|endmodule\b|always\s*@|begin\s*:|end\s*;?$|(?:input|output|reg|wire)\s+\[|'
                  r'(?:def|class|import|from|return|for|while|if|else|elif|try|except)\b|#include\b|'
                  r'(?:set|read_hdl|read_verilog|create_clock|report_timing)\s+|'
                  r'(?:const|let|var|function)\s+\w|\w+\s*\([^)]*\)\s*\{|'
                  r'[A-Za-z_]\w*\s*=\s*(?:true|false|null|None)\s*$)')
EQUATION_NUMBER = re.compile(r'^\(\s*\d+(?:[.\-]\d+)*[a-z]?\s*\)$')
MATHFONT = re.compile(r'math|symbol|cmsy|cmex|cmmi|mtex|mtsy|mtmi|m\d-n\d|R\d-tii', re.I)
MONO = re.compile(r'courier|mono|consolas|menlo|inconsolata|liberationmono', re.I)
MATH = set('=±∑∫√∞∂∇≈≠≤≥×÷∈∝∼∏∧∨⊂⊆⊗ΣΠψΨφΦαβγδεθλμρσΩℏ≡⟨⟩')
# Decoder-only source cues. Keep the trained feature vocabulary unchanged.
SOURCE_MATH = MATH | set('+−πτνξζηωϕϑ⋅·∕')
BAD = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffd]')

def box_union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]

def baseline(row):
    if '_math_axis_baseline' in row:return row['_math_axis_baseline']
    spans = [s for s in row.get('spans', []) if s.get('text', '').strip()]
    return statistics.median(s.get('origin', [0, row['bbox'][3]])[1] for s in spans) if spans else row['bbox'][3]

def fraction(row, pattern):
    spans = row.get('spans', [])
    def ink(span):
        if __package__:
            from .source_structure import visible_math_controls
        else:
            from source_structure import visible_math_controls
        return max(len(span.get('text','').strip()),int(visible_math_controls({'spans':[span]})))
    return sum(ink(s) for s in spans if pattern.search(s.get('font', ''))) / max(1,sum(ink(s) for s in spans))

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

def equation_number_anchor(row):
    """Measure the printed number, excluding padded spaces and the expression.

    A visible source layer and an invisible OCR layer can have different line
    bounds for the same printed number. Character geometry is authoritative;
    the original row and all its characters remain untouched.
    """
    match = re.search(r'\(\s*\d+(?:[.\-]\d+)*[a-z]?\s*\)\s*$', row['text'])
    if not match:
        return None
    label = re.sub(r'\s+', '', match.group())
    chars = [char for span in row.get('spans', []) for char in span.get('chars', [])]
    text = ''.join(char.get('c', '') for char in chars)
    native_match = re.search(r'\(\s*\d+(?:[.\-]\d+)*[a-z]?\s*\)\s*$', text)
    if (native_match and re.sub(r'\s+', '', native_match.group()) == label and
            all(len(char.get('c', '')) == 1 for char in chars)):
        selected = [char for char in chars[native_match.start():native_match.end()]
                    if not char['c'].isspace()]
        if selected and all(len(char.get('bbox', [])) == 4 for char in selected):
            origins = [char['origin'][1] for char in selected if len(char.get('origin', [])) == 2]
            return {**row, 'bbox': box_union([char['bbox'] for char in selected]),
                    '_math_axis_baseline': statistics.median(origins) if origins else baseline(row),
                    '_equation_label': label}
    return {**row, '_equation_label': label}


def equation_anchor_groups(numbers, size):
    """Unify coincident labels; repeated numbers elsewhere stay independent."""
    groups = []
    def coincident(a, b):
        x, y = a['bbox'], b['bbox']
        overlap = max(0, min(x[2], y[2])-max(x[0], y[0]))
        return (a['_equation_label'] == b['_equation_label'] and
                abs(x[2]-y[2]) <= size*.4 and
                overlap >= .75*max(.1, min(x[2]-x[0], y[2]-y[0])) and
                abs(baseline(a)-baseline(b)) <= size*.3 and
                abs((x[1]+x[3]-y[1]-y[3])/2) <= size*.4)
    for row in numbers:
        anchor = equation_number_anchor(row)
        candidates = [g for g in groups if all(coincident(anchor, a) for a, _ in g)]
        if len(candidates) == 1:
            candidates[0].append((anchor, row))
        else:
            groups.append([(anchor, row)])
    result = []
    for group in groups:
        # Prefer a standalone number for a stable region name. Retain the full
        # embedded expression in the members, rather than replacing its box.
        anchor, _ = min(group, key=lambda pair: (
            not bool(EQUATION_NUMBER.fullmatch(pair[1]['text'].strip())), pair[1]['id']))
        result.append((anchor, [row for _, row in group]))
    return result

def context(page, profile):
    """Measure relations once per page, without annotations or learned predictions."""
    if __package__:
        from .source_structure import source_text_present,visible_math_controls
    else:
        from source_structure import source_text_present,visible_math_controls
    if __package__:
        from .pdf_text_recovery import math_ink_geometry
    else:
        from pdf_text_recovery import math_ink_geometry
    geometry={r['id']:math_ink_geometry(r) for r in page['lines']}
    rows = [{**r,'bbox':geometry[r['id']]['bbox'],
             '_math_axis_baseline':geometry[r['id']]['axis_baseline_estimate']}
            if geometry[r['id']] else r for r in page['lines'] if source_text_present(r)]
    size = max(1, profile['body_size']); width = page['width']; height = page['height']
    by_id = {r['id']: r for r in rows}
    data = {r['id']: {'mono': fraction(r, MONO), 'mathfont': fraction(r, MATHFONT),
                     'marker': leading_marker(r), 'code_group': None, 'note_group': None,
                     'math_group': None,'math_ink_geometry':geometry[r['id']]} for r in rows}
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
        # A clean raised-marker seed can establish note ownership even when
        # an aligned continuation contains an unresolved inline symbol.
        # The glyph still needs review; it must not become body prose.
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
    # Drawn/native table geometry and graph interiors are not display equations.
    # These source constraints are applied before and after learned refinement.
    table_boxes=[t['bbox'] for t in page.get('table_regions',[])]+list(page.get('structure_regions',[]))
    graphic_boxes=page.get('graphic_regions',[])
    def within(row,boxes):
        b=row['bbox'];cx=(b[0]+b[2])/2;cy=(b[1]+b[3])/2
        return any(g[0]-.5<=cx<=g[2]+.5 and g[1]-.5<=cy<=g[3]+.5 for g in boxes)
    for row in rows:
        info=data[row['id']]
        info['table_interior']=within(row,table_boxes)
        near_graphic=any(g[0]-size*3<=(row['bbox'][0]+row['bbox'][2])/2<=g[2]+size*3 and
            g[1]-size*1.5<=(row['bbox'][1]+row['bbox'][3])/2<=g[3]+size*1.5 and
            g[2]-g[0]>size*5 and g[3]-g[1]>size*4 for g in graphic_boxes)
        info['graphic_interior']=(within(row,graphic_boxes) or near_graphic) and len(row['text'])<80
        containing=[g for g in graphic_boxes if within(row,[g])]
        info['compact_graphic_only']=bool(containing) and not near_graphic and all(
            g[2]-g[0]<=size*3 and g[3]-g[1]<=size*3 for g in containing)
        # Reading-layer consolidation must not erase a native paragraph's
        # preceding-row evidence. A remaining hidden prose tail may still have
        # its original preceding row archived under the visible primary.
        # Use the immutable source ledger for this local boundary cue; never
        # reinsert that archived text into reading units or model prompts.
        peers=[x for x in page.get('native_lines', rows)
               if x['native_block']==row['native_block'] and x['bbox'][1]<row['bbox'][1]-.5]
        previous=max(peers,key=lambda x:x['bbox'][1]) if peers else None
        info['short_prose_tail']=bool(previous and len(previous['text'])>40 and
            len(re.findall(r'[A-Za-z]{3,}',previous['text']))>=4 and
            abs(previous['bbox'][0]-row['bbox'][0])<size*.8 and
            0<baseline(row)-baseline(previous)<size*1.8 and
            not re.search(r'[.!?:]\s*$',previous['text']))
    # PDF writers may split one prose baseline across unrelated native blocks,
    # even in the middle of a word. Measure adjacent same-font fragments as a
    # source constraint only; never rewrite, complete or duplicate their text.
    prose_rows=[r for r in rows if not data[r['id']]['code_group'] and
                not data[r['id']]['note_group'] and data[r['id']]['mathfont']<.2 and
                not EQUATION_NUMBER.fullmatch(r['text'].strip()) and
                abs(r.get('direction',[1,0])[1])<.05]
    unseen={r['id'] for r in prose_rows};prose_baselines=[]
    for row in prose_rows:
        if row['id'] not in unseen:continue
        unseen.remove(row['id']);stack=[row];members=[]
        while stack:
            current=stack.pop();members.append(current)
            for other in prose_rows:
                if other['id'] not in unseen:continue
                gap=max(current['bbox'][0],other['bbox'][0])-min(current['bbox'][2],other['bbox'][2])
                if (current['font']==other['font'] and
                    abs(math.log(max(.1,current['size'])/max(.1,other['size'])))<.12 and
                    abs(baseline(current)-baseline(other))<size*.22 and
                    -size*.8<=gap<=size*.6):
                    unseen.remove(other['id']);stack.append(other)
        text=' '.join(x['text'].strip() for x in sorted(members,key=lambda x:x['bbox'][0]))
        words=re.findall(r'[A-Za-z]{3,}',text)
        if len(text)>=40 and len(words)>=5:
            prose_baselines.append({'text':text,'bbox':box_union([x['bbox'] for x in members]),
                                    'baseline':statistics.median(baseline(x) for x in members)})
            if len(members)>1:
                for member in members:data[member['id']]['same_baseline_prose']=True
    # Anchor each numbered equation in its source column. Expand through a
    # bounded math region until actual prose, another equation or column edge.
    # This accommodates multi-line displays and below-display equation numbers.
    anchors=[]
    def source_typography(row):
        spans=[s for s in row.get('spans',[]) if s.get('text','').strip()]
        maximum=max((s.get('size',row['size']) for s in spans),default=row['size'])
        scripts=any(s.get('size',maximum)<maximum*.83 for s in spans)
        alternate_glyphs=sum(sum(ord(c)>127 or bool(BAD.fullmatch(c)) for c in s.get('text',''))
                             for s in spans)
        varied=len({s.get('font','') for s in spans})>=2
        return spans,scripts,bool(varied and alternate_glyphs and
                                 (alternate_glyphs>=2 or scripts or len(row['text'])<45))
    def mathematical(row, numbered=False):
        text=row['text'].strip();info=data[row['id']]
        spans,scripts,encoded_typography=source_typography(row)
        words=re.findall(r'[A-Za-z]{3,}',text)
        # A bounded numbered region can retain artwork with a broken font map,
        # but damaged text alone is never an unnumbered mathematical seed.
        if BAD.search(text) and (len(words)>=4 or
                info['mathfont']<.2 and not (numbered and encoded_typography and len(text)<90)):return False
        fraction_glyph=bool(numbered and info.get('compact_graphic_only') and len(text)<=8 and
            any(sp.get('flags',0)&2 or MATHFONT.search(sp.get('font','')) for sp in spans) and
            any(left-.6<=row['bbox'][0] and row['bbox'][2]<=right+.6 and
                abs(baseline(row)-y)<=size*1.5 and right-left<=size*4
                for left,y,right in page.get('fraction_rules',[])))
        if (abs(row.get('direction',[1,0])[1])>.05 or info['code_group'] or info['note_group'] or
            info['table_interior'] or info['graphic_interior'] and not fraction_glyph or
            info['short_prose_tail'] or info.get('same_baseline_prose') or len(text)>180):return False
        if not text and visible_math_controls(row):return True
        if text.casefold()=='or':
            nearby=[x for x in rows if x['id']!=row['id'] and abs(baseline(x)-baseline(row))<size*1.7 and data[x['id']]['mathfont']>.2]
            return len(nearby)>=2
        if text.casefold() in {'is','and','the','where','thus','hence','therefore'}:return False
        if re.match(r'^(?:and|the|this|where|for|with|so|if|at|in|particular|hence|now|since|thus|consider|it|we|let|from|here|each)\b',text,re.I):return False
        if (row['bbox'][1]<height*.09 or row['bbox'][3]>height*.91) and re.fullmatch(r'\d{1,4}',text):return False
        previous=[x for x in rows if x['native_block']==row['native_block'] and
                  0<baseline(row)-baseline(x)<size*1.65 and len(x['text'])>45 and
                  len(re.findall(r'[A-Za-z]{3,}',x['text']))>=5 and
                  abs(x['bbox'][0]-row['bbox'][0])<size*1.5]
        if previous and len(re.findall(r'[A-Za-z]{3,}',text))>=3:return False
        # Damaged text mappings are not mathematical evidence. Treating control
        # glyphs as an equation cue turns entire broken-font paragraphs into
        # formula regions; preserve them for review instead.
        math_evidence=info['mathfont']>.2 or any(c in SOURCE_MATH for c in text)
        # Mathematical displays may contain descriptive words (e.g. "pure
        # imaginary quantity"). Ordinary prose with occasional math is a barrier.
        # Several descriptive subscripts can look like prose after flattening.
        # Inspect the actual main-size spans: a compact relation with measured
        # scripts and only variables/functions at the main baseline is spatial
        # mathematics. An ordinary clause with an inline variable is not.
        maximum=max((s.get('size',row['size']) for s in spans),default=row['size'])
        main_words=[word for span in spans if span.get('size',maximum)>=maximum*.83
                    for word in re.findall(r'[A-Za-z]+',span.get('text',''))]
        scripted_relation=bool(numbered and scripts and len(text)<120 and
            re.search(r'[=≈≠≤≥]',text) and main_words and
            all(len(word)<=2 or word in {'exp','log','ln','sin','cos','tan','max','min','lim','det'} for word in main_words))
        # A fraction product can have full-word variable names and descriptive
        # subscripts. Require native italic/math lettering and measured scripts,
        # not a plausible formula inferred from the words.
        scripted_product=bool(numbered and scripts and len(text)<120 and
            re.search(r'[×⋅÷]',text) and spans and
            all(not re.search(r'[A-Za-z]',sp.get('text','')) or
                sp.get('flags',0)&2 or MATHFONT.search(sp.get('font','')) for sp in spans))
        if len(words)>=4 and not (info['mathfont']>=.75 and scripts or scripted_relation or scripted_product):return False
        if math_evidence:return True
        # A parenthesized raised index does not require a font called "Math".
        # Keep the measured italic variable with its scripts inside an already
        # numbered display; ordinary words cannot seed this ownership rule.
        if (numbered and scripts and re.fullmatch(r'[A-Za-z]{1,2}\s*\([A-Za-z0-9]{1,3}\)',text)
                and any(sp.get('flags',0)&2 for sp in spans)):
            return True
        # A compact roman denominator can contain a differential/function name.
        # Require a real horizontal fraction rule above it and measured scripts,
        # rather than classifying parentheses or a word as mathematics alone.
        if (numbered and scripts and re.fullmatch(r'[A-Za-z0-9_()+−*/.,]{1,32}',text)
                and any(left-.6<=row['bbox'][0] and row['bbox'][2]<=right+.6 and
                        0<baseline(row)-y<size*1.7 and
                        row['bbox'][1]>=y-size*.3 and right-left<size*8
                        for left,y,right in page.get('fraction_rules',[]))):
            return True
        # Upright identifiers may be separate native objects on the left of a
        # relation or above/below a fraction rule. Require either measured
        # scripts or a local same-baseline operator; the word itself never
        # seeds an unnumbered display. Source column and graphic gates above
        # still apply.
        if numbered and len(text)<=20 and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?: or [A-Za-z][A-Za-z0-9_]*)?',text):
            if scripts:return True
            for peer in rows:
                if peer['id']==row['id'] or not re.search(r'[=≈≠≤≥]',peer['text']):continue
                if len(peer['text'])>45 or len(re.findall(r'[A-Za-z]{3,}',peer['text']))>=3:continue
                a,b=row['bbox'],peer['bbox']
                if (abs(baseline(row)-baseline(peer))<=size*.25 and
                    max(0,a[0]-b[2],b[0]-a[2])<=size*3):return True
        if numbered and encoded_typography and len(words)<=3 and len(text)<90:return True
        # A roman function name belongs to its adjacent measured mathematical
        # expression, including cases split into separate native PDF objects.
        # It is not an independent display merely because the model likes it.
        if text in {'exp','log','ln','sin','cos','tan','max','min','lim','det'}:
            return any(x['id']!=row['id'] and data[x['id']]['mathfont']>.2 and
                max(0,x['bbox'][0]-row['bbox'][2],row['bbox'][0]-x['bbox'][2])<size*3 and
                max(0,x['bbox'][1]-row['bbox'][3],row['bbox'][1]-x['bbox'][3])<size*1.5
                for x in rows)
        if (spans and all(s.get('flags',0)&2 or MATHFONT.search(s.get('font','')) for s in spans)
                and len(text)<32 and len(words)<=2 and
                (scripts or not re.search(r'\s',text) or numbered and (row['size']<size*.85 or
                    len(text)<12 and all(len(w)<=3 for w in text.split()))) and
                (not re.search(r'[.!?:]\s*$',text) or numbered and scripts and len(words)<=1)):
            return True
        # Roman words under a source integral/sum are limits, not freestanding
        # prose. Require a measured small script adjacent to the actual operator
        # in a numbered search; the word alone cannot seed a new display.
        if numbered and row['size']<size*.85 and len(text)<18 and len(words)<=1 and re.fullmatch(r'[A-Za-z0-9,._]+',text):
            for peer in rows:
                if peer['id']==row['id']:continue
                operator=visible_math_controls(peer) or any(c in '∫∑∏⋃⋂' for c in peer['text'])
                a,b=row['bbox'],peer['bbox']
                if (operator and max(0,a[0]-b[2],b[0]-a[2])<size*.8 and
                    max(0,a[1]-b[3],b[1]-a[3])<size*1.8):return True
        # Descriptive roman subscripts may be separate PDF text objects. A
        # small word is owned only beside a larger mathematical variable with
        # a measured script displacement; it never seeds an unnumbered region.
        if numbered and row['size']<size*.85 and re.fullmatch(r'[A-Za-z]{3,12}',text):
            for peer in rows:
                if peer['id']==row['id'] or not re.fullmatch(r'[A-Za-z]{1,2}',peer['text'].strip()):continue
                if peer['size']<row['size']*1.25:continue
                if (-.5<=row['bbox'][0]-peer['bbox'][2]<=size*.7 and
                    0<=baseline(row)-baseline(peer)<=size*.7 and
                    row['bbox'][1]<peer['bbox'][3]):return True
        if numbered and re.fullmatch(r'[A-Za-z]{1,2}(?:[,._][A-Za-z0-9]{1,3})+',text):return True
        return bool(re.fullmatch(r'[\d\s.,+−–*/()\[\]{}|\u23a1-\u23b0]+',text) or (not words and re.search(r'\d',text) and len(text)<18) or re.fullmatch(r'[a-zA-Z]{1,2}[.,]?',text))
    equation_numbers=[row for row in rows if EQUATION_NUMBER.fullmatch(row['text'].strip())]
    embedded_numbers=[row for row in rows if not EQUATION_NUMBER.fullmatch(row['text'].strip()) and
                      re.search(r'\(\s*\d+(?:[.\-]\d+)*[a-z]?\s*\)\s*$',row['text'].strip()) and
                      mathematical(row,numbered=True) and
                      (data[row['id']]['mathfont']>.2 or any(c in SOURCE_MATH for c in row['text']))]
    number_groups=equation_anchor_groups(equation_numbers+embedded_numbers,size)
    for anchor,number_rows in number_groups:
        right=anchor['bbox'][2]+size
        narrative=[row for row in rows if abs(row.get('direction',[1,0])[1])<.05 and
                   len(row['text'])>55 and len(re.findall(r'[A-Za-z]{3,}',row['text']))>=7 and
                   abs(row['bbox'][2]-anchor['bbox'][2])<width*.15 and
                   not data[row['id']]['note_group'] and not data[row['id']]['code_group'] and
                   not mathematical(row,numbered=True)]
        measured=narrative+[line for line in prose_baselines if len(line['text'])>55 and
                           len(re.findall(r'[A-Za-z]{3,}',line['text']))>=7 and
                           abs(line['bbox'][2]-anchor['bbox'][2])<width*.15]
        local=sorted(measured,key=lambda row:abs(row.get('baseline',baseline(row))-baseline(anchor)))[:6]
        # A full-width footer aligned to a column's right edge must not make
        # the column search span unrelated prose in the other column. Compare
        # widths of the nearest native narrative rows before measuring its left.
        if len(local)>=3:
            typical=statistics.median(x['bbox'][2]-x['bbox'][0] for x in local)
            local=[x for x in local if x['bbox'][2]-x['bbox'][0]<=typical*1.6]
        left=min((row['bbox'][0] for row in local),default=0)-size
        above=[row for row in narrative if baseline(row)<baseline(anchor)-size*.4]
        below=[row for row in narrative if baseline(row)>baseline(anchor)+size*.4]
        top=max((row['bbox'][3] for row in above),default=anchor['bbox'][1]-size*8)-size*.15
        bottom=min((row['bbox'][1] for row in below),default=anchor['bbox'][3]+size*8)+size*.15
        other_numbers=[x for x,_ in number_groups if x['id']!=anchor['id'] and
                       left<=x['bbox'][0] and abs(x['bbox'][2]-anchor['bbox'][2])<width*.25]
        prior=[x for x in other_numbers if baseline(x)<baseline(anchor)]
        later=[x for x in other_numbers if baseline(x)>baseline(anchor)]
        if prior:top=max(top,max(x['bbox'][3] for x in prior)+size*.1)
        if later:bottom=min(bottom,min(x['bbox'][1] for x in later)-size*.1)
        # A short source prose fragment is a boundary too, even when it does not
        # meet the long narrative threshold (e.g. "This leaves the equation").
        barriers=[x for x in rows if abs(x.get('direction',[1,0])[1])<.05 and
                  not mathematical(x,numbered=True) and not data[x['id']]['code_group'] and
                  not data[x['id']]['note_group'] and left<=x['bbox'][0] and
                  x['bbox'][2]<=right and (len(re.findall(r'[A-Za-z]{3,}',x['text']))>=3 or re.match(r'^(?:since|and|where|thus|is)\b',x['text'],re.I))]
        upper=[x for x in barriers if baseline(x)<baseline(anchor)]
        lower=[x for x in barriers if baseline(x)>baseline(anchor)]
        if upper:top=max(top,max(x['bbox'][3] for x in upper)-size*.15)
        if lower:bottom=min(bottom,min(x['bbox'][1] for x in lower)+size*.15)
        top=max(top,anchor['bbox'][1]-size*8);bottom=min(bottom,anchor['bbox'][3]+size*8)
        members=[row for row in rows if row['id']!=anchor['id'] and row not in equation_numbers and
                 left<=row['bbox'][0] and row['bbox'][2]<=right and
                 top<=baseline(row)<=bottom and
                 mathematical(row,numbered=True)]
        # An equation number bounds a search, not every math-looking label
        # underneath it. Start in its baseline band and grow only through
        # local ink; a later circuit's supply labels are separate components.
        near=[row for row in members if abs(baseline(row)-baseline(anchor))<=size*1.25]
        if not near and members:
            nearest=min(members,key=lambda row:abs(baseline(row)-baseline(anchor)))
            if abs(baseline(nearest)-baseline(anchor))<=size*3:
                near=[nearest]
        connected={row['id'] for row in near}
        frontier=list(near)
        while frontier:
            seed=frontier.pop()
            for row in members:
                if row['id'] in connected:continue
                a,b=seed['bbox'],row['bbox']
                gap_x=max(0,a[0]-b[2],b[0]-a[2])
                gap_y=max(0,a[1]-b[3],b[1]-a[3])
                same_baseline=abs(baseline(seed)-baseline(row))<=size*.25
                if ((gap_x<=size*1.5 and gap_y<=size*.95) or
                    same_baseline and gap_x<=size*3):
                    connected.add(row['id']);frontier.append(row)
        members=[row for row in members if row['id'] in connected]
        # A final cases row can consist of an upright value and descriptive
        # words ("0, Otherwise") with no mathematical font. Retain that source
        # row only beside an actual connected brace, inside its vertical band,
        # and aligned with another branch from the same native PDF object.
        # Its words alone never seed a display or extend into following prose.
        braces=[row for row in members if re.fullmatch(r'[\s{⎧⎨⎩⎪]+',row['text'])]
        if braces:
            brace=box_union([row['bbox'] for row in braces])
            branches=[row for row in members if row['bbox'][0]>=brace[2]-.5 and
                      re.match(r'^(?:[+−-]?\d+(?:\.\d+)?|[A-Za-z]{1,2})\s*[,;]',row['text'].strip())]
            for row in rows:
                info=data[row['id']];text=row['text'].strip();box=row['bbox']
                if (row in members or info['code_group'] or info['note_group'] or
                    info['table_interior'] or info['graphic_interior'] or
                    abs(row.get('direction',[1,0])[1])>.05 or len(text)>64 or
                    not re.match(r'^(?:[+−-]?\d+(?:\.\d+)?|[A-Za-z]{1,2})\s*[,;]\s*\S',text)):
                    continue
                if (left<=box[0] and box[2]<=right and top<=baseline(row)<=bottom and
                    -.5<=box[0]-brace[2]<=size*2.5 and
                    brace[1]-size*.3<=box[1] and box[3]<=brace[3]+size and
                    any(peer['native_block']==row['native_block'] and
                        abs(peer['bbox'][0]-box[0])<=size*.5 and
                        0<baseline(row)-baseline(peer)<=size*2 for peer in branches)):
                    members.append(row)
                    info['piecewise_branch_evidence']='connected-source-brace-and-aligned-native-branch'
        if (any(row in embedded_numbers for row in number_rows) or
            any(data[row['id']]['mathfont']>.2 or any(c in SOURCE_MATH for c in row['text']) or
                source_typography(row)[2] for row in members)):
            members += [row for row in number_rows if row not in members]
            anchors.append((anchor,members))
    for row in rows:
        choices=[(abs(baseline(row)-baseline(anchor)),anchor) for anchor,members in anchors
                 if row in members or row['id']==anchor['id']]
        if choices:
            # A small stacked glyph between successive numbers belongs to
            # its nearby expression, not necessarily the closest number's
            # baseline. Use the actual larger ink in each candidate component.
            if len(choices)>1 and row['size']<size*.85:
                # A centred limit can be nearer the next fraction's font box
                # than its own large operator. Require a compact, horizontally
                # overlapping parent before using general nearest-ink distance.
                # Shared candidate fragments cannot establish that parent: the
                # parent itself must be nearer this equation's number band.
                supported=[]
                for distance,candidate in choices:
                    peers=[x for a,ms in anchors if a['id']==candidate['id'] for x in ms
                           if x['id']!=row['id'] and x['size']>row['size']*1.25]
                    for peer in peers:
                        a,b=row['bbox'],peer['bbox']
                        overlap=max(0,min(a[2],b[2])-max(a[0],b[0]))
                        gap_y=max(0,a[1]-b[3],b[1]-a[3])
                        nearest=min(choices,key=lambda choice:abs(baseline(peer)-baseline(choice[1])))[1]
                        if (nearest['id']==candidate['id'] and b[2]-b[0]<=size*2 and
                            overlap>=.6*max(.1,a[2]-a[0]) and gap_y<=size*.75):
                            supported.append((distance,candidate));break
                if len(supported)==1:choices=supported
                ink_choices=[]
                for distance,candidate in choices:
                    peers=[x for a,ms in anchors if a['id']==candidate['id'] for x in ms
                           if x['id']!=row['id'] and x['size']>row['size']*1.25 and
                           x['bbox'][2]-x['bbox'][0]<=size*2.5 and
                           min(choices,key=lambda choice:abs(baseline(x)-baseline(choice[1])))[1]['id']==candidate['id']]
                    if peers:
                        gap=min(math.hypot(max(0,row['bbox'][0]-x['bbox'][2],x['bbox'][0]-row['bbox'][2]),
                                           max(0,row['bbox'][1]-x['bbox'][3],x['bbox'][1]-row['bbox'][3])) for x in peers)
                        # A distant expression in the next equation is not a
                        # script parent merely because its font box is closer.
                        if gap<=size*.85:ink_choices.append((gap,distance,candidate))
                if ink_choices:choices=[(distance,candidate) for gap,distance,candidate in ink_choices
                                        if gap<=min(x[0] for x in ink_choices)+.1]
            anchor=min(choices,key=lambda x:x[0])[1]
            data[row['id']]['math_group']='equation:'+anchor['id']
    # Unnumbered display equations still need a source-spatial region. Restrict
    # seeds to compact mathematical rows, then connect nearby fragments in 2D;
    # short inline prose such as "at q = 0" is explicitly excluded.
    unnumbered=[]
    for row in rows:
        info=data[row['id']];text=row['text'].strip()
        if not mathematical(row):continue
        if BAD.search(text):
            if info['mathfont']>=.3 and len(re.findall(r'[A-Za-z]{3,}',text))<4 and not info['math_group']:unnumbered.append(row)
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
    # Complete measured denominators, matrix entries and stacked scripts near
    # a display seed. Long prose and existing numbered regions are barriers.
    seeds=list(unnumbered)
    for _ in range(3):
        added=[]
        for row in rows:
            if row in unnumbered or data[row['id']]['math_group'] or data[row['id']]['note_group'] or data[row['id']]['code_group']:continue
            if not mathematical(row):continue
            for seed in seeds:
                gap_y=max(0,row['bbox'][1]-seed['bbox'][3],seed['bbox'][1]-row['bbox'][3])
                gap_x=max(0,row['bbox'][0]-seed['bbox'][2],seed['bbox'][0]-row['bbox'][2])
                if gap_y>max(row['size'],seed['size'])*1.9 or gap_x>max(size*5,width*.055):continue
                top,bottom=sorted([baseline(row),baseline(seed)])
                if any(top+size*.2<baseline(x)<bottom-size*.2 and (len(re.findall(r'[A-Za-z]{3,}',x['text']))>=2 or re.match(r'^(?:since|and|where|thus|is)\b',x['text'],re.I)) and
                       not mathematical(x) and min(row['bbox'][2],seed['bbox'][2],x['bbox'][2])>max(min(row['bbox'][0],seed['bbox'][0]),x['bbox'][0]) for x in rows):continue
                added.append(row);break
        if not added:break
        unnumbered.extend(added);seeds=added
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
                    top,bottom=sorted([baseline(current),baseline(other)])
                    blocked=any(top+size*.2<baseline(x)<bottom-size*.2 and
                        not mathematical(x) and not data[x['id']]['code_group'] and
                        (len(re.findall(r'[A-Za-z]{3,}',x['text']))>=2 or re.match(r'^(?:since|and|where|thus|is)\b',x['text'],re.I)) and
                        min(a[2],b[2],x['bbox'][2])>max(min(a[0],b[0]),x['bbox'][0]) for x in rows)
                    if not blocked:neighbors.append(lid)
            for lid in neighbors:unseen.remove(lid);stack.append(lid)
        has_math=any(data[x['id']]['mathfont']>=.3 or any(c in MATH for c in x['text']) for x in component)
        if has_math:components.append(component)
    for component in components:
        if not any(data[row['id']]['math_group'] for row in component):
            gid='equation-region:'+min(row['id'] for row in component)
            for row in component:data[row['id']]['math_group']=gid
    # Short piecewise conditions can have ordinary roman "for" in a separate
    # native object. Keep their text in the existing mathematical envelope,
    # rather than also publishing it as a stray body paragraph. This never
    # expands an envelope through adjacent prose or invents a missing clause.
    envelopes={}
    for row in rows:
        gid=data[row['id']]['math_group']
        if gid:envelopes.setdefault(gid,[]).append(row['bbox'])
    envelopes={gid:box_union(boxes) for gid,boxes in envelopes.items()}
    for row in rows:
        info=data[row['id']];text=row['text'].strip();b=row['bbox']
        if (info['math_group'] or info['code_group'] or info['note_group'] or
            info['table_interior'] or info['graphic_interior'] or info['short_prose_tail']):continue
        if not (re.match(r'^(?:for|if|when)\b',text,re.I) and len(text)<65 and
                len(re.findall(r'[A-Za-z]{3,}',text))<=1 and
                re.search(r'[=<>≤≥≠]',text) and info['mathfont']>.2):continue
        cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2
        owners=[gid for gid,box in envelopes.items()
                if box[0]-.5<=cx<=box[2]+.5 and box[1]-.5<=cy<=box[3]+.5]
        if len(owners)==1:info['math_group']=owners[0]
    page_index = any(re.fullmatch(r'(?:subject |author )?index', r['text'].strip(), re.I) for r in rows[:12])
    page_contents = any(re.fullmatch(r'(?:table of )?contents', r['text'].strip(), re.I) for r in rows[:12])
    if __package__:
        from . import source_structure as base_structure
    else:
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
        if info['table_interior'] and not info['note_group'] and not info['code_group']:
            base.update(assigned_role='table',semantic_role='table',rule='source-table-interior',review_required=True)
        elif info['graphic_interior'] and base.get('assigned_role')=='equation':
            base.update(assigned_role='label',semantic_role='label',rule='source-graphic-label-not-display',review_required=True)
        elif base.get('assigned_role')=='equation' and not info['math_group']:
            # The broad role head can promote a prose tail, command output or
            # corrupt caption from a mathematical peer in the same PDF object.
            # Only a spatially supported region can become a display equation.
            # Keep the learned proposal for audit; retain source text for review.
            base.update(assigned_role='body',semantic_role='body',
                        rule='display-proposal-without-source-spatial-support',review_required=True)
        if info['repeated_margin']:
            base.update(assigned_role='metadata',semantic_role='metadata',rule='source-repeated-margin',review_required=False)
        # Retain a strongly typed, explicitly numbered display as a provisional
        # learned proposal when it falls below the normal acceptance threshold.
        # This does not lower that threshold or claim an accepted neural seed.
        # In particular, small subscript fonts at a page top are not sufficient
        # evidence to discard a whole formula as running furniture.
        if (not accepted and not source_text_damaged and kind=='math' and
            score>=.8 and margin>=.4 and info['mathfont']>=.75 and
            str(info['math_group']).startswith('equation:') and
            re.search(r'\(\s*\d+(?:[.\-]\d+)*[a-z]?\s*\)\s*$',row['text'].strip()) and
            any(c in SOURCE_MATH for c in row['text']) and
            not info['repeated_margin'] and not info['table_interior'] and
            not info['graphic_interior']):
            base.update(assigned_role='equation',semantic_role='equation',review_required=True,
                        rule='source-math-region-pending-review')
            base['provisional_region_prediction']={'class':'math','score':round(score,6),
                'line_id':row['id'],'accepted':False,'reason':'numbered-source-artwork-retained-for-review'}
        # Keep compact numbered artwork even when damaged native mappings
        # prevent neural acceptance. Preserve the raw proposal and review flag;
        # this is a source-preservation fallback, not an accepted ML seed.
        if (source_text_damaged and str(info['math_group']).startswith('equation:') and
            re.search(r'\(\s*\d+(?:[.\-]\d+)*[a-z]?\s*\)\s*$',row['text'].strip()) and
            len(re.findall(r'[A-Za-z]{3,}',row['text']))<4 and
            any(any(c in SOURCE_MATH for c in member['text']) for member in eligible
                if contexts[member['id']]['math_group']==info['math_group']) and info['mathfont']>0 and
            not info['repeated_margin'] and not info['table_interior'] and not info['graphic_interior']):
            base.update(assigned_role='equation',semantic_role='equation',review_required=True,
                        rule='source-math-region-pending-review')
            base['provisional_region_prediction']={'class':kind,'score':round(score,6),
                'line_id':row['id'],'accepted':False,'suggested_region':'math',
                'reason':'numbered-damaged-source-artwork-retained-for-review'}
    # Constrained graph decoding: a confidently learned region seed propagates
    # through a measured marker/font/alignment chain, not across a native block.
    for group_key,kind,role in [('note_group','footnote','metadata'),('code_group','code','body'),('math_group','math','equation'),('figure_group','label','label')]:
        grouped={}
        for row in eligible:
            gid=contexts[row['id']].get(group_key)
            # A caption band's generous graphic padding must not steal a
            # member of a source-bounded display after its math seed ran.
            if gid and not (kind=='label' and
                           str(contexts[row['id']].get('math_group')).startswith('equation:')):
                grouped.setdefault(gid,[]).append(row)
        for gid,members in grouped.items():
            seeds=[row for row in members if not BAD.search(row['text']) and proposals[row['id']]['applied'] and proposals[row['id']]['class']==kind]
            fallback=not seeds and kind=='math' and any(decisions[row['id']]['assigned_role']=='equation' for row in members)
            if not seeds and not fallback:continue
            for row in members:
                dec=decisions[row['id']]
                if BAD.search(row['text']):
                    dec.update(assigned_role=role,semantic_role='equation' if kind=='math' else kind,review_required=True,
                               rule='source-spatial-equation-region-unresolved-glyph' if kind=='math' else 'source-'+kind+'-chain-unresolved-glyph')
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
        geometry=info.get('math_ink_geometry') if kind=='equation' else None
        member={**row,'bbox':geometry['bbox'],'native_declared_bbox':row['bbox'],
                'source_ink_geometry':geometry} if geometry else row
        groups.setdefault((kind, gid), []).append(member)
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
