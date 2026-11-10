"""Source-bound formula isolation; never invent symbols or claim LaTeX recovery.

Character geometry corroborates lexical math. Uncertain native mappings remain
evidence. The publisher restores original artwork at immutable formula anchors.
Copyright 2026 Yufeng Zhan. MIT.
"""
from __future__ import annotations
import base64
import hashlib
import html
import re
from pathlib import Path

REVISION = '1.0.3-math-isolation-16-bounded-source-runs'
TOKEN = re.compile(r'⟦MATH:[a-f0-9]{16}⟧')
MATHFONT = re.compile(r'math|symbol|cmsy|cmex|cmmi|mtex|mtsy|mtmi|msam|msbm|eurm|rsfs|m\d-n\d|R\d-tii', re.I)
SYMBOL = re.compile(r'[=±∑∫√∞∂∇≈≠≤≥<>×÷∈∉∝∼∏∧∨⊂⊆⊗ℏ≡⟨⟩α-ωΑ-Ω]')
ATOM = re.compile(r'[ \t\r\n\u00a0]+|\d+(?:\.\d+)?|[A-Za-zα-ωΑ-Ω\u0300-\u036f\u20d0-\u20ff]+|[\s\S]', re.UNICODE)
BAD = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffd]')
FUNCTIONS = {'sin','cos','tan','cot','sinh','cosh','tanh','log','ln','exp','lim','max','min','det','Tr','Re','Im','arg','mod'}
OPERATORS = set('=+−-*/^_±∑∫√∞∂∇≈≠≤≥<>×÷∈∉∝∼∏∧∨⊂⊆⊗ℏ≡|→↔←!·∗')
SCRIPTS = set('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎')


def _space(value):
    # Some PDFs map real glyphs to U+001C..U+001F, which Python calls
    # whitespace. They have visible source geometry and must not be trimmed.
    return bool(value) and value.isspace() and not BAD.search(value)


def _union(boxes):
    return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]


def _skip(text):
    if __package__:
        from .structure_regions import SHELL_PROMPT
    else:
        from structure_regions import SHELL_PROMPT
    return bool(re.match(r'^\s*(?:https?://|www\.|[\w.+-]+@)',text) or
                re.match(r'^\s*' + SHELL_PROMPT,text) or
                re.match(r'^\s*(?:def |class |import |#include|const |let |var |function |return |set )',text))


def ranges(text, attributes=None):
    """Conservative typography/lexical detection, with exact character offsets.

    Raised source markers are retained as markers, separately from formula
    accuracy. Ordinary italic prose, headings, email and ordinal suffixes are
    not mathematical evidence. No guessed Unicode or generated LaTeX is used.
    """
    if not text or _skip(text):return []
    attributes=attributes or [{} for _ in text]
    explicit=[]
    patterns=[r'\$\$[^$]+\$\$',r'(?<![\\\d])\$(?!\s|\d+(?:[.,]\d+)?(?:\s|$))[^$\n]+?\$',r'\\\([\s\S]+?\\\)',r'\\\[[\s\S]+?\\\]']
    # Corrupt font encodings can contain dollar signs that are not delimiters.
    if not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]',text):
        for pattern in patterns:
            for m in re.finditer(pattern,text):explicit.append({'start':m.start(),'end':m.end(),'evidence':['explicit-math-delimiter'],'kind':'formula'})
    # Compact chemistry has measured numeric subscripts but ordinary roman
    # element letters. Protect the complete compound, not isolated subscripts.
    # Require at least two element symbols and an explicit numeric subscript.
    for match in re.finditer(r'(?<![A-Za-z])(?:[A-Z][a-z]?[₀-₉0-9]*){2,}(?![A-Za-z])',text):
        value=match.group();elements=re.findall(r'[A-Z][a-z]?',value)
        periodic={'H','He','Li','Be','B','C','N','O','F','Ne','Na','Mg','Al','Si','P','S','Cl','Ar','K','Ca','Sc','Ti','V','Cr','Mn','Fe','Co','Ni','Cu','Zn','Ga','Ge','As','Se','Br','Kr','Rb','Sr','Y','Zr','Nb','Mo','Tc','Ru','Rh','Pd','Ag','Cd','In','Sn','Sb','Te','I','Xe','Cs','Ba','La','Ce','Pr','Nd','Pm','Sm','Eu','Gd','Tb','Dy','Ho','Er','Tm','Yb','Lu','Hf','Ta','W','Re','Os','Ir','Pt','Au','Hg','Tl','Pb','Bi','Po','At','Rn','Fr','Ra','Ac','Th','Pa','U','Np','Pu','Am','Cm','Bk','Cf','Es','Fm','Md','No','Lr','Rf','Db','Sg','Bh','Hs','Mt','Ds','Rg','Cn','Nh','Fl','Mc','Lv','Ts','Og'}
        measured=any(a.get('subscript') for a in attributes[match.start():match.end()])
        if all(e in periodic for e in elements) and (re.search(r'[₀-₉]',value) or measured):
            explicit.append({'start':match.start(),'end':match.end(),'evidence':['complete-chemical-compound-with-numeric-subscript'],'kind':'formula'})
    atoms=list(ATOM.finditer(text));groups=[];marker_offsets=set()
    # Raised note references are separate anchors. Never expand a leading
    # marker through whitespace into the article 'A' of a footnote.
    for match in re.finditer(r'[⁰¹²³⁴⁵⁶⁷⁸⁹]+|[0-9]+',text):
        attrs=attributes[match.start():match.end()]
        raised=any(a.get('script') for a in attrs) or any(c in SCRIPTS for c in match.group())
        previous=re.search(r'([A-Za-z]+)[.!?,;:]?$',text[:match.start()])
        leading=not text[:match.start()].strip() and match.end()<len(text) and (text[match.end()].isspace() or text[match.end()].isalpha())
        reference=previous and len(previous.group(1))>2 and not any(MATHFONT.search(a.get('font','')) or a.get('subscript') for a in attrs)
        if raised and (leading or reference):
            groups.append({'start':match.start(),'end':match.end(),'kind':'marker','evidence':['raised-note-marker-boundary']})
            marker_offsets.update(range(match.start(),match.end()))
    def quality(m):
        t=m.group();attrs=attributes[m.start():m.end()]
        if any(i in marker_offsets for i in range(m.start(),m.end())):return False,False
        font=any(MATHFONT.search(a.get('font','')) for a in attrs)
        italic=bool(attrs) and all(a.get('math_italic',a.get('italic')) or a.get('script') for a in attrs)
        script=any(a.get('script') for a in attrs)
        greek=bool(re.search(r'[α-ωΑ-Ω\u20d0-\u20ff]',t))
        latin=bool(re.fullmatch(r'[A-Za-z]+',t))
        # Plain-font engineering identifiers are mathematical when immediately
        # attached to a relation or bounded absolute-value expression.
        compact_identifier=latin and bool(re.fullmatch(r'[A-Z][A-Za-z]{1,15}',t)) and bool(
            re.match(r'\s*(?:[=≤≥<>≈≠]|\|\s*[=≤≥<>≈≠])',text[m.end():]) or
            m.start()>0 and text[m.start()-1]=='|' and m.end()<len(text) and text[m.end()]=='|')
        unit_suffix=latin and len(t)<=3 and m.start()>0 and text[m.start()-1].isdigit()
        attached_subscript=latin and len(t)<=8 and bool(attrs) and all(a.get('subscript') for a in attrs)
        # Protect a measured symbol, not the first character of a prose word.
        short_variable=latin and len(t)<=2 and italic and t not in {'a','an','as','at','by','in','is','it','of','on','or','to','we','be','do','no','so','if','et','al','eg','Co','De','I','A'}
        heading=bool(m.start()==len(text)-len(text.lstrip()) and re.match(r'^[A-Z]\.(?:\s|$)',text[m.start():]))
        seed=bool(not heading and (SYMBOL.search(t) or font and not _space(t) or short_variable or script and not _space(t) or any(c in SCRIPTS for c in t)))
        allowed=(_space(t) or bool(re.fullmatch(r'\d+(?:\.\d+)?',t)) or
                 len(t)==1 and (t.isalpha() or t in OPERATORS or t in '()[]{}' or t in SCRIPTS or greek) or
                 t in FUNCTIONS or compact_identifier or unit_suffix or attached_subscript or bool((font or script or greek or short_variable) and len(t)<=20) or
                 t in ',:' and m.start()>0 and m.end()<len(text) and not text[m.start()-1].isspace() and not text[m.end()].isspace())
        if re.fullmatch(r'\d+(st|nd|rd|th)',text[max(0,m.start()-3):m.end()]) or (t in {'st','nd','rd','th'} and m.start()>0 and text[m.start()-1].isdigit()):
            return False,False
        # Generic italicised acronyms such as 3D/N3XT are not short variables.
        if latin and ((m.start()>0 and text[m.start()-1].isdigit()) or (m.end()<len(text) and text[m.end()].isdigit())) and not font and not script and not short_variable and not unit_suffix:return False,False
        if latin and m.end()<len(text) and text[m.end()].isdigit() and t.isupper() and not font and not script:return False,False
        return seed,allowed
    qualities=[quality(a) for a in atoms]
    for i,(seed,allowed) in enumerate(qualities):
        if not seed or not allowed or _space(atoms[i].group()):continue
        left=right=i
        while left>0 and qualities[left-1][1]:left-=1
        while right+1<len(atoms) and qualities[right+1][1]:right+=1
        start,end=atoms[left].start(),atoms[right].end()
        while start<end and _space(text[start]):start+=1
        while end>start and _space(text[end-1]):end-=1
        # Remove any unmatched boundary bracket (including an opening bracket
        # at the right edge) rather than stealing the next prose parenthesis.
        changed=True
        while changed and start<end:
            changed=False
            for opening,closing in {'(':')','[':']','{':'}'}.items():
                value=text[start:end]
                if value.count(opening)>value.count(closing):
                    if value.startswith(opening):start+=1;changed=True
                    elif value.endswith(opening):end-=1;changed=True
                value=text[start:end]
                if value.count(closing)>value.count(opening):
                    if value.endswith(closing):end-=1;changed=True
                    elif value.startswith(closing):start+=1;changed=True
            while start<end and _space(text[start]):start+=1;changed=True
            while end>start and _space(text[end-1]):end-=1;changed=True
        value=text[start:end]
        if not value or not (any(c.isalnum() or c in '∑∫√∞ℏ' for c in value) or
                            any(MATHFONT.search(a.get('font','')) or a.get('unicode_unresolved') for a in attributes[start:end])):continue
        if value in {'I','A','a'} and not any(MATHFONT.search(a.get('font','')) for a in attributes[start:end]):continue
        while value.endswith(('-', '/', '·', ',')) and len(value)>1 and not re.search(r'[=+−≈<>≤≥]',value[:-1]):
            end-=1;value=text[start:end]
        if start and text[start-1] in '@:' and not SYMBOL.search(value):continue
        kind='marker' if all(c.isdigit() or c in SCRIPTS or c.isspace() or c in ',*†‡' for c in value) and not any(MATHFONT.search(a.get('font','')) or a.get('subscript') for a in attributes[start:end]) and not re.search(r'[₀-₉]',value) else 'formula'
        groups.append({'start':start,'end':end,'evidence':['math-font-or-symbol-or-measured-script'],'kind':kind})
    merged=[]
    for candidate in sorted(explicit+groups,key=lambda r:(r['start'],-r['end'])):
        if merged and candidate['start']<merged[-1]['end']:
            merged[-1]['end']=max(merged[-1]['end'],candidate['end'])
            merged[-1]['evidence']=sorted(set(merged[-1]['evidence']+candidate['evidence']))
            if candidate['kind']=='formula':merged[-1]['kind']='formula'
        else:merged.append(candidate.copy())
    return merged


def line_candidates(line):
    """Detect on measured typography; retain each source character's bounds."""
    if __package__:
        from .source_structure import typography_text,LIGATURES,suspect_native_encoding
    else:
        from source_structure import typography_text,LIGATURES,suspect_native_encoding
    text,_=typography_text(line)
    spans=line.get('spans',[]);attrs=[]
    if spans and all(re.search(r'courier|mono|consolas|menlo',s.get('font',''),re.I) for s in spans if s.get('text','').strip()):return text,[]
    if spans:
        if __package__:
            from .source_structure import text_baseline
        else:
            from source_structure import text_baseline
        base=text_baseline(line);size=max(.1,line.get('size',10))
        # A PDF span may begin with a space left at a preceding subscript's
        # baseline. Use the visible character origins, not that first space.
        baselines=[char['origin'][1] for span in spans
            if span.get('size',size)>=size*.88 for char in span.get('chars',[])
            if char.get('c','').strip() and len(char.get('origin',[]))==2]
        if baselines:base=sorted(baselines)[len(baselines)//2]
        for span in spans:
            chars=span.get('chars',[]);raw=span.get('text','')
            for i,c in enumerate(raw):
                origin=chars[i].get('origin',span.get('origin',[0,base])) if len(chars)==len(raw) else span.get('origin',[0,base])
                shift=origin[1]-base
                attrs.append({'font':span.get('font',''),'italic':bool(span.get('flags',0)&2),
                    'size_ratio':span.get('size',size)/size,'baseline_shift_em':shift/size,
                    'math_italic':bool(span.get('flags',0)&2) and (len(raw.strip())<=2 or bool(SYMBOL.search(raw))),
                    'unicode_unresolved':bool(chars[i].get('unicode_unresolved')) if len(chars)==len(raw) else False,
                    'native_glyph':chars[i].get('native_glyph') if len(chars)==len(raw) else None,
                    'source_size_pt':size,'source_origin':list(origin),
                    'source_synthetic':bool(chars[i].get('synthetic')) if len(chars)==len(raw) else True,
                    'script':span.get('size',size)<size*.9 and abs(shift)>size*.18,
                    'subscript':span.get('size',size)<size*.9 and shift>size*.12,
                    'bbox':chars[i]['bbox'] if len(chars)==len(raw) else span.get('bbox') if len(raw)==1 else None})
    native=''.join(s.get('text','') for s in spans)
    # Numeric script serialization is one character to one character. Match
    # the serialized source, rather than losing the attributes of 2 -> ².
    if not line.get('inline_spatial_groups') and len(native)==len(text):native=text
    if len(attrs)!=len(text) or line.get('inline_spatial_groups'):
        # Match unchanged source runs after physical-row whitespace insertion.
        from difflib import SequenceMatcher
        mapped=[{} for _ in text]
        for match in SequenceMatcher(None,native,text,autojunk=False).get_matching_blocks():
            for i in range(match.size):
                if match.a+i<len(attrs):mapped[match.b+i]=attrs[match.a+i]
        attrs=mapped
    # Explicit source-spatial groups retain their own full geometry. They must
    # not inherit an approximate character match for a reordered numerator.
    spatial=[]
    for group in line.get('inline_spatial_groups',[]):
        start=group['source_start'];value=group['text'];end=start+len(value)
        if line['text'][start:end]!=value:
            raise ValueError('Spatial formula/source transcript mismatch: '+line['id'])
        spatial.append({**group,'start':start,'end':end,'kind':'formula'})
    if not suspect_native_encoding(text):
        before=text
        expanded=[];out=[]
        for char,attr in zip(text,attrs):
            replacement=char.translate(LIGATURES);out.append(replacement);expanded.extend([attr]*len(replacement))
        text=''.join(out);attrs=expanded
        for rec in spatial:
            start,end=rec['start'],rec['end']
            rec['start']=len(before[:start].translate(LIGATURES))
            rec['end']=len(before[:end].translate(LIGATURES))
    found=[]
    candidates=ranges(text,attrs)
    # An evidenced stacked fraction takes priority over overlapping lexical
    # guesses, including guesses extending into following ordinary prose.
    candidates=[c for c in candidates if not any(c['start']<g['end'] and g['start']<c['end'] for g in spatial)]+spatial
    for i,attr in enumerate(attrs):
        if attr.get('unicode_unresolved') and not any(c['start']<=i<c['end'] for c in candidates):
            candidates.append({'start':i,'end':i+1,'kind':'source-glyph','evidence':['unresolved-native-font-mapping']})
    for rec in sorted(candidates,key=lambda c:c['start']):
        visible=[a for ch,a in zip(text[rec['start']:rec['end']],attrs[rec['start']:rec['end']]) if not _space(ch)]
        if not rec.get('bbox') and visible and all(a.get('bbox') for a in visible):rec['bbox']=_union([a['bbox'] for a in visible])
        rec.update(text=text[rec['start']:rec['end']],line_id=line['id'],
                   character_styles=attrs[rec['start']:rec['end']])
        if rec.get('serialization')=='spatial-glyph-transcript' and rec.get('bbox'):
            # Keep the exact extracted characters as text at measured positions.
            # This is inline composition, not image cropping or inferred LaTeX.
            box=rec['bbox'];runs=[]
            for span in spans:
                bb=span.get('bbox');value=span.get('text','')
                if not bb or not value.strip():continue
                if not (box[0]-.5<=bb[0] and bb[2]<=box[2]+.5 and box[1]-.5<=bb[1] and bb[3]<=box[3]+.5):continue
                runs.append({'text':value,'bbox':bb,'origin':span.get('origin',[bb[0],bb[3]]),
                             'size_pt':span.get('size',size),'italic':bool(span.get('flags',0)&2),
                             'font':span.get('font','')})
            rec['text_runs']=runs
            rec['fraction_rule']=[box[0],next((g['fraction_rule'][1] for g in line.get('inline_spatial_groups',[]) if g.get('text')==rec['text'] and g.get('fraction_rule')), (box[1]+box[3])/2),box[2]]
        found.append(rec)
    # A missing Unicode map can affect an entire printed line. Preserve its
    # adjacent source outlines as one measured run rather than thousands of
    # one-character PDF placements. Never cross readable text, a geometric
    # discontinuity, a formula/marker boundary or an absent outline.
    runs=[]
    for rec in found:
        prior=runs[-1] if runs else None
        if (prior and prior['kind']==rec['kind']=='source-glyph' and
            prior.get('bbox') and rec.get('bbox') and
            all(_space(c) for c in text[prior['end']:rec['start']]) and
            all(_space(ch) or style.get('native_glyph') for ch,style in
                zip(text[prior['start']:rec['end']],attrs[prior['start']:rec['end']]))):
            a,b=prior['bbox'],rec['bbox']
            same_line=abs((a[1]+a[3]-b[1]-b[3])/2)<=size*.35
            if same_line and -.5<=b[0]-a[2]<=size*.8:
                prior.update(end=rec['end'],text=text[prior['start']:rec['end']],
                    bbox=_union([a,b]),character_styles=attrs[prior['start']:rec['end']],
                    evidence=sorted(set(prior.get('evidence',[])+rec.get('evidence',[])+['contiguous-source-outline-run'])))
                continue
        runs.append(rec)
    return text,runs


def region_candidates(region,page):
    lines={x['id']:x for x in page['lines']};result=[];cursor=0
    for lid in region['line_ids']:
        line=lines[lid];text,found=line_candidates(line);trimmed=text.strip()
        at=region['text'].find(trimmed,cursor) if trimmed else -1
        # compose() may remove an evidenced line-end hyphen. Only its unchanged
        # prefix may lend geometry; do not approximate changed formula offsets.
        if at<0 and trimmed.endswith(('\u00ad','-','‐')):
            trimmed=trimmed[:-1];at=region['text'].find(trimmed,cursor) if trimmed else -1
        if at<0:continue
        leading=len(text)-len(text.lstrip())
        for rec in found:
            start=at+rec['start']-leading;end=at+rec['end']-leading
            if start>=at and end<=at+len(trimmed) and region['text'][start:end]==rec['text']:
                result.append({**rec,'start':start,'end':end})
        cursor=at+len(trimmed)
    return result


def attach(unit,candidates=None):
    """Keep literal source and an independently reversible formula template."""
    source=unit['source'];candidates=ranges(source) if candidates is None else candidates
    records=[];pieces=[];cursor=0
    for rec in sorted(candidates,key=lambda x:x['start']):
        start,end=rec['start'],rec['end']
        if not 0<=cursor<=start<end<=len(source):raise ValueError('Invalid overlapping math source range')
        token='⟦MATH:'+hashlib.sha256((unit['id']+'|'+str(start)+'|'+source[start:end]).encode()).hexdigest()[:16]+'⟧'
        records.append({**rec,'token':token,'source':source[start:end],'source_sha256':hashlib.sha256(source[start:end].encode()).hexdigest(),
            'representation':'source-literal','semantic_transcription':False})
        pieces.extend([source[cursor:start],token]);cursor=end
    if records:
        pieces.append(source[cursor:]);unit['protected_math']=records;unit['source_template']=''.join(pieces);unit['math_revision']=REVISION
    return unit


def attach_block(block,region,page,root,source_file):
    """Compose inline formulas from native text; only displays use source crops."""
    candidates=region_candidates(region,page);cursor=0
    for unit in block.get('units',[]):
        start=region['text'].find(unit['source'],cursor)
        if start<0:raise ValueError('Formula/source unit mapping is ambiguous')
        end=start+len(unit['source']);local=[{**c,'start':c['start']-start,'end':c['end']-start} for c in candidates if start<=c['start'] and c['end']<=end]
        for rec in ranges(unit['source']):
            if not any(rec['start']<c['end'] and c['start']<rec['end'] for c in local):local.append(rec)
        attach(unit,local);cursor=end
        for rec in unit.get('protected_math',[]):
            rec.update(page=page['page'],representation='native-inline-text',
                       body_size_pt=max(1,block.get('typography',{}).get('dominant_size_pt',10)))


    # Exact source artwork resolves appearance, not Unicode. Enrich only
    # damaged inline records, so ordinary prose does not acquire huge outlines.
    damaged=[];links=[]
    for unit in block.get('units',[]):
        for rec in unit.get('protected_math',[]):
            styles=rec.get('character_styles',[])
            if len(styles)!=len(rec['source']) or rec.get('text_runs'):continue
            if not any(style.get('native_glyph') or style.get('unicode_unresolved') or BAD.search(char)
                       for char,style in zip(rec['source'],styles)):continue
            spans=[]
            for char,style in zip(rec['source'],styles):
                if not style.get('bbox') or not style.get('source_origin'):continue
                native={'c':char,'bbox':style['bbox'],'origin':style['source_origin'],
                        'synthetic':style.get('source_synthetic',False),
                        'unicode_unresolved':style.get('unicode_unresolved',False)}
                spans.append({'font':style.get('font',''),'chars':[native],'text':char})
                links.append((style,native))
            if spans:damaged.append({'spans':spans,'direction':[1,0]})
    if damaged:
        import fitz
        if __package__:
            from .pdf_text_recovery import source_glyph_outlines
        else:
            from pdf_text_recovery import source_glyph_outlines
        with fitz.open(source_file) as original:
            source_glyph_outlines(original[page['page']-1],damaged,preserve_all=True)
        for style,native in links:
            if native.get('native_glyph'):style['native_glyph']=native['native_glyph']


def source_composition_html(record):
    """Compose verified source outlines at their native relative positions."""
    import xml.etree.ElementTree as ET
    if __package__:
        from .vector_assets import validate_svg
    else:
        from vector_assets import validate_svg
    styles=record.get('character_styles',[]);source=record['source']
    if len(styles)!=len(source) or record.get('text_runs'):return None
    if not any(s.get('native_glyph') for s in styles):return None
    if any(not char.isspace() and not style.get('native_glyph')
           for char,style in zip(source,styles)):return None
    glyphs=[(i,s,s['native_glyph']) for i,s in enumerate(styles) if s.get('native_glyph')]
    box=_union([g['bbox'] for _,_,g in glyphs]);size=record.get('body_size_pt',10)
    bases=[g['origin'][1]-s.get('baseline_shift_em',0)*s.get('source_size_pt',size) for _,s,g in glyphs]
    baseline=sorted(bases)[len(bases)//2]
    # A retained source row can be wider than a translated column. Bound the
    # replaced SVG itself, preserving its intrinsic aspect ratio and glyph
    # positions; clipping its parent would silently lose the final characters.
    css='display:inline-block;overflow:visible;width:'+str(round((box[2]-box[0])/size,6))+'em;max-width:100%;height:auto;vertical-align:'+str(round((baseline-box[3])/size,6))+'em;'
    outer=ET.Element('svg',{'xmlns':'http://www.w3.org/2000/svg',
        'width':str(box[2]-box[0]),'height':str(box[3]-box[1]),
        'viewBox':' '.join(str(v) for v in [box[0],box[1],box[2]-box[0],box[3]-box[1]]),
        'class':'inline-math-source-composed','style':css,'aria-label':'Original source notation'})
    for index,style,glyph in glyphs:
        if hashlib.sha256(glyph['svg'].encode()).hexdigest()!=glyph['sha256']:
            raise ValueError('Native source glyph outline changed')
        validate_svg(glyph['svg']);child=ET.fromstring(glyph['svg']);bb=glyph['bbox']
        # Flatten artwork into the common source coordinate system. Nested
        # SVG viewport handling differs across browser and PDF renderers.
        group=ET.SubElement(outer,'g')
        for element in child:group.append(element)
        # Measure the native character rectangle independently of ink bounds;
        # a combining mark can overlap its preceding glyph at the same origin.
        ET.SubElement(group,'rect',{'x':str(bb[0]),'y':str(bb[1]),
            'width':str(bb[2]-bb[0]),'height':str(bb[3]-bb[1]),'fill':'none','stroke':'none',
            'data-source-glyph-index':str(index),'data-source-glyph-sha256':glyph['sha256']})
    markup=ET.tostring(outer,encoding='unicode').replace('ns0:','').replace(':ns0','')
    # ElementTree can repeat xmlns on the outer node when nesting SVG nodes.
    markup=markup.replace('xmlns="http://www.w3.org/2000/svg" xmlns="http://www.w3.org/2000/svg"','xmlns="http://www.w3.org/2000/svg"')
    validate_svg(markup)
    return markup


def inline_text_html(record):
    """Compose native text; unresolved glyphs retain their source outlines."""
    composed=source_composition_html(record)
    if composed is not None:return composed
    source=record['source'];styles=record.get('character_styles',[])
    runs=record.get('text_runs',[]);box=record.get('bbox')
    if runs and box and record.get('fraction_rule'):
        size=record.get('body_size_pt',10);width=(box[2]-box[0])/size;height=(box[3]-box[1])/size
        parts=[]
        for run in runs:
            x=(run['origin'][0]-box[0])/size;y=(run['origin'][1]-box[1])/size
            parts.append('<span style="position:absolute;left:'+str(round(x,5))+'em;top:'+str(round(y,5))+'em;font-size:'+str(round(run['size_pt']/size,5))+'em;line-height:1;transform:translateY(-.8em);font-style:'+('italic' if run.get('italic') else 'normal')+'">'+html.escape(run['text'])+'</span>')
        y=(record['fraction_rule'][1]-box[1])/size
        parts.append('<span aria-hidden="true" style="position:absolute;left:0;right:0;top:'+str(round(y,5))+'em;border-top:.05em solid currentColor"></span>')
        return '<span class="inline-math-composed" style="display:inline-block;position:relative;width:'+str(round(width,5))+'em;height:'+str(round(height,5))+'em;vertical-align:-.45em;white-space:nowrap;font-family:serif">'+''.join(parts)+'</span>'
    if len(styles)!=len(source):return html.escape(source)
    groups=[]
    for offset,(char,style) in enumerate(zip(source,styles)):
        if style.get('native_glyph'):
            glyph=style['native_glyph'];svg=glyph['svg']
            if hashlib.sha256(svg.encode('utf-8')).hexdigest()!=glyph['sha256']:
                raise ValueError('Native source glyph outline changed')
            if __package__:
                from .vector_assets import validate_svg
            else:
                from vector_assets import validate_svg
            validate_svg(svg)
            box=glyph['bbox'];size=record.get('body_size_pt',style.get('source_size_pt',10))
            baseline=glyph['origin'][1]-style.get('baseline_shift_em',0)*style.get('source_size_pt',size)
            css='display:inline-block;overflow:visible;width:'+str(round((box[2]-box[0])/size,6))+'em;height:'+str(round((box[3]-box[1])/size,6))+'em;vertical-align:'+str(round((baseline-box[3])/size,6))+'em;'
            svg=svg.replace('<svg ','<svg data-source-glyph-index="'+str(offset)+'" data-source-glyph-sha256="'+glyph['sha256']+'" aria-label="Original source glyph" style="'+css+'" ',1)
            groups.append([('native-glyph',False,1),svg])
            continue
        shift=style.get('baseline_shift_em',0);ratio=style.get('size_ratio',1)
        tag='sup' if shift<-.18 and ratio<.9 else 'sub' if shift>.12 and ratio<.9 else 'span'
        # Unicode numeric scripts already carry their vertical form.
        if char in SCRIPTS:tag='span'
        key=(tag,bool(style.get('italic')),round(ratio,3) if tag!='span' else 1)
        if groups and groups[-1][0]==key:groups[-1][1]+=char
        else:groups.append([key,char])
    parts=[]
    for (tag,italic,ratio),value in groups:
        if tag=='native-glyph':parts.append(value);continue
        css='font-style:'+('italic' if italic else 'normal')+';'
        if tag!='span':css+='font-size:'+str(max(.4,min(.9,ratio)))+'em;line-height:0;'
        parts.append('<'+tag+' style="'+css+'">'+html.escape(value)+'</'+tag+'>')
    return ''.join(parts)


def validate(unit,target):
    expected=[r['token'] for r in unit.get('protected_math',[])]
    if not expected:return
    if TOKEN.findall(target)!=expected:raise ValueError('Formula tokens missing, duplicated, reordered or changed: '+unit['id'])
    if '⟦MATH:' in TOKEN.sub('',target):raise ValueError('Malformed formula token: '+unit['id'])


def literal(text,records):
    for rec in records:text=text.replace(rec['token'],rec['source'])
    return text


def unresolved_glyphs(unit):
    """Return unknown glyphs that lack verified source appearance evidence.

    Fencing a character alone is not a repair. Keep its source finding and
    block generation when the original appearance cannot be safely retained.
    """
    missing=[]
    for record in unit.get('protected_math',[]):
        styles=record.get('character_styles',[])
        for i,char in enumerate(record['source']):
            style=styles[i] if i<len(styles) else {}
            if not (BAD.search(char) or style.get('unicode_unresolved')):continue
            glyph=style.get('native_glyph')
            if (not glyph or record.get('text_runs') or
                    hashlib.sha256(glyph.get('svg','').encode('utf-8')).hexdigest()!=glyph.get('sha256')):
                missing.append({'token':record['token'],'offset':i,'source':char})
    return missing


def render(text,records,root=None):
    lookup={r['token']:r for r in records};parts=[];cursor=0
    for match in TOKEN.finditer(text):
        parts.append(html.escape(text[cursor:match.start()],quote=True));rec=lookup.get(match.group())
        if rec is None:raise ValueError('Unknown formula token in publication')
        if rec.get('asset') and root is not None:
            if __package__:
                from .translate import safe,sha
            else:
                from translate import safe,sha
            asset=safe(Path(root),rec['asset'])
            if sha(asset)!=rec['asset_sha256']:raise ValueError('Formula artwork changed')
            mime='image/svg+xml' if asset.suffix.lower()=='.svg' else 'image/png'
            if asset.suffix.lower()=='.svg':
                if __package__:
                    from .vector_assets import validate_svg
                else:
                    from vector_assets import validate_svg
                validate_svg(asset.read_bytes())
            # The CSS box is the declared artwork destination. SVG's default
            # xMidYMid meet adds unmeasured letterboxing after pixel alignment.
            # Change only viewport fitting; paths and source assets stay immutable.
            data=asset.read_bytes()
            if mime=='image/svg+xml':
                svg=data.decode('utf-8')
                svg=re.sub(r'(<svg\b[^>]*?)\s+preserveAspectRatio=[\"\'][^\"\']*[\"\']',r'\1',svg,count=1)
                data=svg.replace('<svg ','<svg preserveAspectRatio="none" ',1).encode('utf-8')
            src='data:'+mime+';base64,'+base64.b64encode(data).decode()
            fallback=''
            if rec.get('asset_fallback'):
                fp=safe(Path(root),rec['asset_fallback'])
                if sha(fp)!=rec['asset_fallback_sha256']:raise ValueError('Formula fallback changed')
                fallback=' data-raster-fallback="data:image/png;base64,'+base64.b64encode(fp.read_bytes()).decode()+'"'
            width=max(.25,rec.get('em_width',1));height=max(.5,rec.get('em_height',1))
            parts.append('<img class="inline-math" data-math-token="'+html.escape(rec['token'])+'" data-math-sha256="'+rec['asset_sha256']+'" src="'+src+'" alt="'+html.escape(rec['source'],quote=True)+'"'+fallback+' contenteditable="false" style="display:inline-block;width:'+str(round(width,5))+'em;height:auto;aspect-ratio:'+str(round(width/height,8))+';max-width:100%;object-fit:contain;vertical-align:-.22em;margin-inline:.08em">')
        else:parts.append('<span class="inline-math-literal" data-math-token="'+html.escape(rec['token'])+'" data-math-sha256="'+rec['source_sha256']+'" dir="ltr" contenteditable="false" style="white-space:nowrap">'+inline_text_html(rec)+'</span>')
        cursor=match.end()
    parts.append(html.escape(text[cursor:],quote=True));return ''.join(parts)


def source_render(unit,root=None):
    return render(unit.get('source_template',unit['source']),unit.get('protected_math',[]),root)



def prepare_native_pdf(browser_page,page_selector='#edPages>.ed-page'):
    """Reserve measured notation boxes for original PDF operator placement."""
    geometry=browser_page.evaluate('''selector=>[...document.querySelectorAll(selector)].flatMap((p,index)=>{
      const pb=p.getBoundingClientRect();const glyphs=[...p.querySelectorAll('svg.inline-math-source-composed')].map(g=>{
        const r=g.getBoundingClientRect(),m=g.closest('[data-math-token]'),vb=g.viewBox.baseVal;
        return {page:index+1,token:m?.dataset.mathToken,source_sha256:m?.dataset.mathSha256,
          source_bbox:[vb.x,vb.y,vb.x+vb.width,vb.y+vb.height],
          pdf_bbox:[(r.left-pb.left)*.75,(r.top-pb.top)*.75,(r.right-pb.left)*.75,(r.bottom-pb.top)*.75]};});
      const artwork=[...p.querySelectorAll('img.inline-math[data-math-token]')].map(im=>{
        const r=im.getBoundingClientRect(),s=getComputedStyle(im);let x=r.x-pb.x,y=r.y-pb.y,w=r.width,h=r.height,nw=im.naturalWidth,nh=im.naturalHeight;
        if(im.src.startsWith('data:image/svg+xml')){const comma=im.src.indexOf(','),head=im.src.slice(0,comma),raw=im.src.slice(comma+1),svg=new DOMParser().parseFromString(head.includes(';base64')?atob(raw):decodeURIComponent(raw),'image/svg+xml').documentElement,vb=svg.getAttribute('viewBox')?.split(/[ ,]+/).map(Number);if(vb?.length===4){nw=vb[2];nh=vb[3];}}
        if(Math.min(w,h,nw,nh)<=0)throw Error('Empty native formula artwork geometry');
        if(s.objectFit==='contain'){const scale=Math.min(w/nw,h/nh),vw=nw*scale,vh=nh*scale;x+=(w-vw)/2;y+=(h-vh)/2;w=vw;h=vh;}
        else if(s.objectFit!=='fill')throw Error('Unsupported native formula artwork fit');
        return {kind:'source-asset',page:index+1,token:im.dataset.mathToken,asset_sha256:im.dataset.mathSha256,
          pdf_bbox:[x*.75,y*.75,(x+w)*.75,(y+h)*.75]};});return [...glyphs,...artwork];})''',page_selector)
    if geometry:
        browser_page.add_style_tag(content='@media print {svg.inline-math-source-composed,img.inline-math[data-math-token] {visibility:hidden !important}}')
    return geometry


def overlay_native_pdf(project_path,pdf_path,geometry,edition):
    """Reuse original PDF text/drawing operators in measured inline boxes.

    Source font operators avoid font-hinting differences introduced by outlined
    HTML vectors. No formula is transcribed, inferred, rasterized or translated.
    """
    import fitz
    from contextlib import ExitStack
    if __package__:
        from .translate import project,safe,sha,write
    else:
        from translate import project,safe,sha,write
    if __package__:
        from .vector_assets import source_crop_page
    else:
        from vector_assets import source_crop_page
    root,manifest,content=project(project_path)
    lookup={r['token']:(b,u,r) for b in content['blocks'] for u in b.get('units',[])
            for r in u.get('protected_math',[])}
    sources={s['id']:s for s in content['sources']}
    placements=[];before=sha(pdf_path)
    if geometry:
        with fitz.open(pdf_path) as output, ExitStack() as source_stack:
            originals={};raw_pages={};source_hashes={}
            for item in geometry:
                if item['token'] not in lookup:raise ValueError('Unknown native math PDF placement')
                block,unit,record=lookup[item['token']]
                if not isinstance(item.get('page'),int) or not 1<=item['page']<=len(output):
                    raise ValueError('Native math output page is invalid')
                artwork=item.get('kind')=='source-asset'
                if hashlib.sha256(record['source'].encode('utf-8')).hexdigest()!=record['source_sha256']:
                    raise ValueError('Native math source transcript changed')
                if artwork:
                    if not record.get('asset') or item.get('asset_sha256')!=record['asset_sha256'] or sha(safe(root,record['asset']))!=record['asset_sha256']:
                        raise ValueError('Native formula artwork identity changed')
                    source_box=record['bbox'];glyphs=[]
                else:
                    if item.get('kind') not in (None,'source-glyph-composition'):raise ValueError('Unknown native math placement kind')
                    if item['source_sha256']!=record['source_sha256']:raise ValueError('Native math source transcript changed')
                    if source_composition_html(record) is None:raise ValueError('Native math appearance evidence incomplete')
                    glyphs=[style['native_glyph'] for style in record['character_styles'] if style.get('native_glyph')]
                    source_box=_union([g['bbox'] for g in glyphs])
                    if len(item['source_bbox'])!=4 or any(abs(a-b)>1e-4 for a,b in zip(source_box,item['source_bbox'])):
                        raise ValueError('Native math source viewport changed')
                source=sources[block['source']['document_id']];file=safe(root,source['file'])
                if file not in originals:
                    source_hashes[file]=sha(file)
                    originals[file]=source_stack.enter_context(fitz.open(file))
                if source_hashes[file]!=source['sha256']:raise ValueError('Native math original PDF changed')
                target=output[item['page']-1];destination=fitz.Rect(item['pdf_bbox']);clip=fitz.Rect(source_box)
                if destination.is_empty or not target.rect.contains(destination):raise ValueError('Native math placement is outside its PDF page')
                if clip.is_empty or abs((destination.width/destination.height)/(clip.width/clip.height)-1)>.02:
                    raise ValueError('Native formula artwork aspect ratio changed')
                original=originals[file]
                if not isinstance(record['page'],int) or not 1<=record['page']<=len(original):
                    raise ValueError('Native math source page is invalid')
                page=original[record['page']-1]
                if not page.rect.contains(clip):raise ValueError('Native math source bounds exceed its original page')
                # Text-only evidence is measured once per source page. Reusing
                # the document also lets MuPDF share its fonts/images instead
                # of embedding the entire page again for each inline glyph.
                key=(file,record['page'])
                if not artwork and key not in raw_pages:
                    raw_pages[key]=page.get_text('rawdict',flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES)['blocks']
                owned=[fitz.Rect(g['bbox']) for g in glyphs];exclusions=list(record.get('native_text_exclusions',[])) if artwork else []
                for native_block in ([] if artwork else raw_pages[key]):
                    if native_block['type']!=0:continue
                    for line in native_block['lines']:
                        for span in line['spans']:
                            for char in span['chars']:
                                bb=fitz.Rect(char['bbox'])
                                if not bb.intersects(clip) or any(bb.intersects(keep) for keep in owned):continue
                                exclusions.append({'bbox':list(bb),
                                    'reason':'Measured native character lies outside every owned glyph rectangle.',
                                    'evidence':'unit='+unit['id']+'; source_sha256='+source['sha256']+'; native_bbox='+str(list(bb))})
                with source_crop_page(page,exclusions) as isolated:
                    target.show_pdf_page(destination,isolated.parent,isolated.number,
                        clip=clip,keep_proportion=False,overlay=True)
                placements.append({'token':item['token'],'unit_id':unit['id'],'output_page':item['page'],
                    'source_page':record['page'],'source_sha256':source['sha256'],
                    'source_bbox':source_box,'pdf_bbox':list(destination),'native_text_exclusions':len(exclusions),
                    'native_text_exclusion_evidence':exclusions,
                    'kind':'source-asset' if artwork else 'source-glyph-composition',
                    'method':'original-pdf-operators-at-measured-inline-geometry'})
            for file in originals:
                if sha(file)!=source_hashes[file]:
                    raise ValueError('Native math original PDF changed during placement')
            temp=Path(pdf_path).with_suffix('.native-inline.pdf')
            output.save(temp,garbage=4,deflate=True)
        temp.replace(pdf_path)
    report={'revision':REVISION,'edition':edition,'placements':placements,'pass':True,
            'before_pdf_sha256':before,'pdf_sha256':sha(pdf_path),'unicode_inferred':False,
            'translation_model_calls':0,'semantic_certification':False}
    write(root/'reports'/('native-inline-pdf-'+edition+'.json'),report)
    return report


def verify_pdf(project_path,browser_page,pdf_path,edition,page_selector='#edPages>.ed-page'):
    """Compare every inline source artwork occurrence with actual PDF pixels."""
    import fitz
    from contextlib import ExitStack
    if __package__:
        from .translate import project,safe,sha,write
    else:
        from translate import project,safe,sha,write
    from asset_fidelity import compare_pdf_region,close_render_cache
    root,manifest,content=project(project_path)
    records={r['token']:(b,u,r) for b in content['blocks'] for u in b.get('units',[]) for r in u.get('protected_math',[]) if r.get('asset')}
    glyph_records={r['token']+':'+str(i):(b,u,r,style['native_glyph'])
        for b in content['blocks'] for u in b.get('units',[]) for r in u.get('protected_math',[])
        for i,style in enumerate(r.get('character_styles',[])) if style.get('native_glyph')}
    browser_page.emulate_media(media='print')
    geometry=browser_page.evaluate('''selector=>[...document.querySelectorAll(selector)].map((p,index)=>{
      const page=p.getBoundingClientRect();return {page:index+1,images:[...p.querySelectorAll('img[data-math-token]')].map(im=>{
        const r=im.getBoundingClientRect(),s=getComputedStyle(im);let nw=im.naturalWidth,nh=im.naturalHeight;
        if(im.src.startsWith('data:image/svg+xml')){const comma=im.src.indexOf(','),head=im.src.slice(0,comma),raw=im.src.slice(comma+1),svg=new DOMParser().parseFromString(head.includes(';base64')?atob(raw):decodeURIComponent(raw),'image/svg+xml').documentElement,vb=svg.getAttribute('viewBox')?.split(/[ ,]+/).map(Number);if(vb?.length===4){nw=vb[2];nh=vb[3];}}
        return {token:im.dataset.mathToken,asset:im.dataset.mathSha256,x:r.x-page.x,y:r.y-page.y,w:r.width,h:r.height,nw,nh,fit:s.objectFit};}),
        glyphs:[...p.querySelectorAll('[data-source-glyph-sha256]')].map(g=>{const r=g.getBoundingClientRect();
        return {key:g.closest('[data-math-token]')?.dataset.mathToken+':'+g.dataset.sourceGlyphIndex,sha256:g.dataset.sourceGlyphSha256,
          x:r.x-page.x,y:r.y-page.y,w:r.width,h:r.height};})};})''',page_selector)
    folder=root/'reports/formula-fidelity'/edition;folder.mkdir(parents=True,exist_ok=True)
    sources={s['id']:s for s in content['sources']};checks=[];seen=[];glyph_seen=[];glyph_checks=[]
    native_frames=[];frame_report=root/'reports'/('native-inline-pdf-'+edition+'.json')
    if frame_report.is_file():
        import json
        evidence=json.loads(frame_report.read_text(encoding='utf-8'))
        if evidence.get('pdf_sha256')!=sha(pdf_path):raise ValueError('Native inline PDF placement evidence is stale')
        native_frames=evidence.get('placements',[])
    with fitz.open(pdf_path) as output, ExitStack() as source_stack:
        originals={};source_hashes={};comparison_cache={}
        source_stack.callback(close_render_cache,comparison_cache)
        def original(file,source):
            if file not in originals:
                source_hashes[file]=sha(file)
                originals[file]=source_stack.enter_context(fitz.open(file))
            if source_hashes[file]!=source['sha256']:raise ValueError('Formula source file changed')
            return originals[file]
        for page_record in geometry:
            page=output[page_record['page']-1]
            for index,image in enumerate(page_record['images']):
                token=image['token'];seen.append(token);check={'token':token,'output_page':page_record['page']}
                if token not in records:checks.append({**check,'pass':False,'error':'Unknown formula asset'});continue
                block,unit,record=records[token];check['unit_id']=unit['id']
                if image['asset']!=record['asset_sha256']:checks.append({**check,'pass':False,'error':'Changed formula artwork'});continue
                x,y,w,h=[image[k] for k in ['x','y','w','h']]
                if min(w,h,image['nw'],image['nh'])<=0:checks.append({**check,'pass':False,'error':'Empty formula geometry'});continue
                source_width=record['bbox'][2]-record['bbox'][0];source_height=record['bbox'][3]-record['bbox'][1]
                if min(source_width,source_height)<=0 or abs((w/h)/(source_width/source_height)-1)>.02:
                    checks.append({**check,'pass':False,'error':'Formula artwork aspect ratio changed',
                        'source_aspect_ratio':source_width/source_height,'output_aspect_ratio':w/h});continue
                if image['fit']=='contain':
                    scale=min(w/image['nw'],h/image['nh']);vw,vh=image['nw']*scale,image['nh']*scale
                    x+=(w-vw)/2;y+=(h-vh)/2;w,h=vw,vh
                elif image['fit']!='fill':checks.append({**check,'pass':False,'error':'Unsupported formula image fit'});continue
                box=fitz.Rect(x*.75,y*.75,(x+w)*.75,(y+h)*.75)
                source=sources[block['source']['document_id']];source_file=safe(root,source['file'])
                stem=folder/f"{unit['id']}-p{page_record['page']:04d}-{index:03d}"
                expected=stem.with_name(stem.name+'-expected.png');actual=stem.with_name(stem.name+'-actual.png')
                metrics=compare_pdf_region(original(source_file,source)[record['page']-1],record['bbox'],page,box,expected,actual,
                    native_text_exclusions=record.get('native_text_exclusions',[]),render_cache=comparison_cache)
                checks.append({**check,**metrics,'pdf_bbox':list(box),'source_bbox':record['bbox'],
                    'expected_crop':expected.relative_to(root).as_posix(),'expected_sha256':sha(expected),
                    'rendered_crop':actual.relative_to(root).as_posix(),'rendered_sha256':sha(actual)})
            for index,item in enumerate(page_record.get('glyphs',[])):
                key=item['key'];glyph_seen.append(key);check={'key':key,'output_page':page_record['page']}
                if key not in glyph_records:
                    glyph_checks.append({**check,'pass':False,'error':'Unknown native glyph'});continue
                block,unit,record,glyph=glyph_records[key]
                if item['sha256']!=glyph['sha256']:
                    glyph_checks.append({**check,'pass':False,'error':'Native glyph identity changed'});continue
                x,y,w,h=[item[k] for k in ['x','y','w','h']]
                if min(w,h)<=0:
                    glyph_checks.append({**check,'pass':False,'error':'Empty native glyph geometry'});continue
                box=fitz.Rect(x*.75,y*.75,(x+w)*.75,(y+h)*.75)
                source=sources[block['source']['document_id']];source_file=safe(root,source['file'])
                stem=folder/f"{unit['id']}-glyph-p{page_record['page']:04d}-{index:03d}"
                expected=stem.with_name(stem.name+'-expected.png');actual=stem.with_name(stem.name+'-actual.png')
                frames=[f for f in native_frames if f['token']==record['token'] and
                        f['output_page']==page_record['page'] and
                        (fitz.Rect(f['pdf_bbox'])+(-.001,-.001,.001,.001)).contains(box)]
                if len(frames)>1:raise ValueError('Ambiguous native inline PDF placement evidence')
                frame=frames[0] if frames else None
                if frame and frame['source_sha256']!=source['sha256']:raise ValueError('Native inline PDF source identity changed')
                metrics=compare_pdf_region(original(source_file,source)[record['page']-1],glyph['bbox'],page,box,expected,actual,
                    render_cache=comparison_cache,
                    **({'source_frame':frame['source_bbox'],'output_frame':frame['pdf_bbox'],
                        'native_text_exclusions':frame.get('native_text_exclusion_evidence',[])} if frame else {}))
                glyph_checks.append({**check,**metrics,'unit_id':unit['id'],'sha256':glyph['sha256'],
                    'source_bbox':glyph['bbox'],'pdf_bbox':list(box),
                    'expected_crop':expected.relative_to(root).as_posix(),'expected_sha256':sha(expected),
                    'rendered_crop':actual.relative_to(root).as_posix(),'rendered_sha256':sha(actual)})
        for file in originals:
            if sha(file)!=source_hashes[file]:raise ValueError('Formula source changed during pixel verification')
    expected_count=len(manifest['editions'])+1 if edition.split('-adjust-')[0].endswith('-alignment') else 1
    missing=[token for token in records if seen.count(token)!=expected_count]
    glyph_missing=[key for key in glyph_records if glyph_seen.count(key)!=expected_count]
    result={'revision':REVISION,'edition':edition,'pdf_sha256':sha(pdf_path),'checks':checks,
        'missing_or_duplicated':missing,'expected_occurrences_per_asset':expected_count,
        'native_glyph_checks':glyph_checks,'native_glyph_missing_or_duplicated':glyph_missing,
        'pass':not missing and not glyph_missing and all(c.get('pass') for c in checks+glyph_checks),'semantic_transcription':False}
    write(root/'reports'/('formula-pdf-'+edition+'.json'),result);return result


def release_errors(root,manifest,content):
    if __package__:
        from .translate import read,sha
    else:
        from translate import read,sha
    if not any(r.get('asset') or any(s.get('native_glyph') for s in r.get('character_styles',[]))
               for b in content['blocks'] for u in b.get('units',[]) for r in u.get('protected_math',[])):return []
    errors=[]
    for language in manifest['target_languages']:
        for edition in manifest['editions']+['alignment']:
            name=language+'-'+edition;p=root/'reports'/('formula-pdf-'+name+'.json');pdf=root/'outputs'/(name+'.pdf')
            if not p.is_file() or not pdf.is_file():errors.append({'code':'formula-pdf-report-missing','edition':name});continue
            report=read(p)
            if not report.get('pass') or report.get('revision')!=REVISION or report.get('pdf_sha256')!=sha(pdf):errors.append({'code':'formula-pdf-report-failed-or-stale','edition':name})
    return errors


def audit(root,content):
    if __package__:
        from .translate import safe,sha
    else:
        from translate import safe,sha
    errors=[]
    for block in content['blocks']:
        for unit in block.get('units',[]):
            records=unit.get('protected_math',[])
            if not records:continue
            if literal(unit.get('source_template',''),records)!=unit['source']:errors.append({'code':'formula-source-roundtrip','id':unit['id']})
            for rec in records:
                if hashlib.sha256(rec['source'].encode()).hexdigest()!=rec['source_sha256']:errors.append({'code':'formula-source-hash','id':unit['id']})
                for style in rec.get('character_styles',[]):
                    glyph=style.get('native_glyph')
                    if glyph and hashlib.sha256(glyph.get('svg','').encode('utf-8')).hexdigest()!=glyph.get('sha256'):
                        errors.append({'code':'native-glyph-outline-hash','id':unit['id']})
                for field in ['asset','asset_fallback']:
                    if not rec.get(field):continue
                    try:
                        p=safe(root,rec[field])
                        if not p.is_file() or sha(p)!=rec[field+'_sha256']:errors.append({'code':'formula-asset-hash','id':unit['id']})
                    except (KeyError,ValueError):errors.append({'code':'formula-asset-path','id':unit['id']})
            for language,editions in unit.get('translations',{}).items():
                for edition,target in editions.items():
                    try:validate(unit,target)
                    except ValueError:errors.append({'code':'formula-integrity','id':unit['id'],'language':language,'edition':edition})
    return errors
