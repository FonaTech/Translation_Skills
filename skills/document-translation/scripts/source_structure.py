"""Offline, source-preserving PDF structure reconstruction.

The learned role and join heads propose structure, never source words or review.
Every native physical line is retained exactly once with immutable span evidence.
Copyright 2026 Yufeng Zhan. MIT.
"""
from __future__ import annotations
from collections import Counter
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import math
import re
import statistics
import unicodedata

MODEL_PATH = Path(__file__).resolve().parent.parent / 'assets/models/source-structure.json'
EXTRACTION_REVISION = '1.0.2-native-rows-21-caption-grid-boundaries'
FEATURE_REVISION = '1.0.1-structure-features-28'
ROLES = ['body', 'title', 'heading', 'metadata', 'caption', 'reference', 'equation', 'label', 'table', 'list']
ROLE_FEATURES = ['size_ratio','width','height','left','top','right','bottom','log_length','digit_fraction','uppercase_fraction','letter_fraction','bold','italic','monospace','symbol_font','small_span_fraction','log_spans','line_height_ratio','caption_start','reference_start','metadata_cue','name_initials','list_start','math_fraction','heading_cue','terminal','first_page','font_body_overlap','size_to_max','bad_char','native_caption_context','native_reference_context','preceding_gap','following_gap','short_label','direction_x','direction_y','native_line_position','native_block_log_lines','native_block_mean_length','native_block_height','native_block_width','explicit_caption_label','repeated_furniture','native_block_first_size_ratio','block_heading_cue','block_metadata_cue','table_region','font_doc_fraction','primary_body_font','sans_family','block_contact_context','same_baseline_peers','body_font_size_distance','title_band','numbered_heading','different_block_font','block_max_size_ratio','block_reference_density','block_reference_starts','bare_web_address','after_title_band','before_title_band','reference_section_context','section_heading_context','front_matter_metadata_context','running_header_context','explicit_metadata_label','author_line_context','affiliation_block_context','list_continuation_context','display_equation_context','explicit_heading_label','graphic_context']
JOIN_FEATURES = ['vertical_gap','baseline_step','left_delta','right_delta','horizontal_overlap','size_log_ratio','same_font','same_native_block','terminal','hyphen','next_lower','next_upper','previous_width','next_width','log_previous_length','log_next_length','same_role','role_body','role_title','role_heading','role_metadata','role_caption','role_reference','role_equation','role_label','role_table','role_list','next_caption_start','next_reference_start','next_list_start','same_direction','previous_indent','next_indent','native_adjacent','column_transition']
JOIN_FEATURES += ['previous_block_position','next_block_position','next_block_inset','previous_block_fill','next_numbered_item','terminal_indent_boundary']
JOIN_FEATURES += ['transition_previous_bottom','transition_next_top']
JOIN_FEATURES += ['next_heading_start']
JOIN_FEATURES += ['next_affiliation_boundary']
JOIN_FEATURES += ['bracket_continuation']
ROLE_FEATURES += ['page_number_context','footnote_context','math_neighbor_context','local_font_heading','sidebar_metadata_context']
ROLE_FEATURES += ['source_figure_band']
ROLE_FEATURES += ['inline_prose_math_context']
ROLE_FEATURES += ['captioned_table_context','subfigure_caption_context']
ROLE_FEATURES += ['filled_heading_context']
CAPTION = re.compile(r'^\s*(?:(?i:table)\s*(?:[A-Z]?\d+(?:\.\d+)*[a-z]?|[IVX]+)\s*(?:[.:：｜](?!\d)|$)|(?i:fig(?:ure)?s?\.?|图|表|図|圖|abb\.|abbildung|tabelle)\s*(?:[A-Z]?\d+(?:\.\d+)*[a-z]?|[IVX]+)\s*[.:：｜](?!\d)|\d+\.\s+.{8,}\(\d{1,4}\s*(?:KB|MB)\)\s*$|(?i:flowchart)\s+(?:showing|to implement)\b)')
REFERENCE = re.compile(r'^\s*(?:\[\d{1,4}\]|\d{1,4}\.|\[[A-Z][A-Za-zÀ-ž’\-]+(?:\s+[A-Za-zÀ-ž’\-]+){0,3}\s+(?:\d{2,4}[a-z]?|[IVX]{2,4})\])\s+(?:[A-Z][A-Za-zÀ-ž’\-]*(?:\s+[A-Z][A-Za-zÀ-ž’\-]*\.?){0,5}(?:,|\s+[“"])|[A-Z]\.\s)')
REFERENCES_HEADING = re.compile(r'^\s*(?:(?:\d+(?:\.\d+)*|[IVX]+)\.?\s+)?(?:references?|bibliography|works cited|literature cited|参考文献|引用文献)\s*[:：]?\s*$',re.I)
SECTION_HEADING = re.compile(r'^\s*(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+[A-Z][A-Z0-9 &,/().:-]{5,90}\s*$')
ABSTRACT_START = re.compile(r'^\s*(?:abstract|summary|摘要|概要)\b',re.I)
METADATA = re.compile(r'(?:\b(?:doi|issn|isbn|received|accepted|published|copyright|correspondence|university|institute|department|laboratory|all rights reserved|keywords?|key\s+words|arxiv)\b|palabras\s+clave|mots-cl[eé]s|schl[uü]sselw[oö]rter|https?://|@|©|收稿|发表|关键词|關鍵詞|作者|大学|研究所)', re.I)
EXPLICIT_METADATA = re.compile(r'^\s*(?:(?:doi|issn|isbn|received|accepted|revised|published|available\s+online|correspondence|keywords?|key\s+words|index\s+terms|arxiv(?:\s+preprint)?|preprint|copyright|all\s+rights\s+reserved|e-?mail|email|authorized\s+licensed\s+use\s+limited\s+to)\s*[:：—–-]?|(?:palabras\s+clave|mots-cl[eé]s|schl[uü]sselw[oö]rter|关键词|關鍵詞|收稿|发表|作者)\s*[:：]|(?:https?://|www\.)\S+|©|\(c\))|^\s*(?:full\s+paper|research\s+article|review\s+article|open\s+access|short\s+communication|impact\s+article)\s*$', re.I)
EXPLICIT_METADATA_EXTRA = re.compile(r'^\s*(?:corresponding\s+author|see\s+https?://\S+(?:\s+for\s+more\s+information)?)|^\s*communication\s*$',re.I)
EXPLICIT_HEADING = re.compile(r'^\s*(?:(?:\d+(?:\.\d+)*|[IVX]+|[A-Z])\.\s*)?(?:abstract|introduction|background|related\s+work|methods?|materials\s+and\s+methods|results?|discussion|conclusions?|acknowledg\w*|appendix|contents|summary|normal\s+operation|seu\s+tolerance|impact\s+statement|摘要|引言|结论|参考文献|方法|目录|附录)\s*$',re.I)
LIST_START = re.compile(r'^\s*(?:[•●▪■–-]|››|\d+[.)]|\((?:[a-z]|[0-9]{1,2})\))\s+',re.I)
MATH_FONT = re.compile(r'(?:symbol|math|cmsy|cmex|cmmi|mtex|mtsy|rmtmi)',re.I)
AFFILIATION_WORD = re.compile(r'\b(?:department|faculty|school|university|institute|institution|college|academy|laboratory|centre|center|research\s+centre)\b',re.I)
COPYRIGHT_NOTICE = re.compile(r'(?:©|copyright|all rights reserved|personal use is permitted|authorized licensed use limited)',re.I)
PUNCTUATION_FREE_CAPTION = re.compile(r'^\s*(?:FIGURES?\s+[A-Z]?\d+(?:\.\d+)*[a-z]?\s+(?=[A-Z(])|(?:Fig\.|Table)\s*[A-Z]?\d+(?:\.\d+)*[a-z]?\s+(?!Shows?\b|Is\b|Was\b|Presents?\b)(?=[A-Z(])|(?i:fig(?:ure)?s?\.?|图|表|図|圖)\s*[A-Z]?\d+(?:\.\d+)*[a-z]?\s+\([a-z]\))')
FOOTNOTE_START = re.compile(r'(?:contribut(?:ed|ion)\s+equally|(?:this\s+(?:work|research|material)|the\s+authors?).{0,65}(?:supported|funded)|funding\s+(?:from|by))',re.I)
BAD_NATIVE_GLYPH = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]')
HEADING = re.compile(r'^(?:\d+(?:\.\d+)*[.\s]+|[IVX]+\.\s+)?(?:abstract|introduction|results?|discussion|conclusions?|methods?|references|acknowledg\w*|appendix|contents|summary|摘要|引言|结论|参考文献|方法|目录|附录)\b', re.I)
LIGATURES = str.maketrans({'ﬀ':'ff','ﬁ':'fi','ﬂ':'fl','ﬃ':'ffi','ﬄ':'ffl','ﬅ':'st','ﬆ':'st'})


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()).hexdigest()


def native_text_damaged(text):
    """Flag control/replacement glyphs; do not guess their intended characters."""
    return bool(BAD_NATIVE_GLYPH.search(text))


def median(values, default=10):
    return statistics.median(values) if values else default


def union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def font_key(name):
    return re.sub(r'^[A-Z]{6}\+', '', name).casefold()


def caption_start(text):
    return bool(CAPTION.search(text) or PUNCTUATION_FREE_CAPTION.search(text) or
                re.match(r'^\s*(?:Fig(?:ure)?s?\.?|Table)\s*[A-Z]?\d+(?:\.\d+)*[a-z]?\s*\|',text,re.I) or
                re.match(r'^\s*(?:Fig(?:ure)?s?\.?|Table)\s+[A-Z]?\d+(?:\.\d+)*\s*\((?i:colou?r\s+online|online\s+colou?r)\)\s+\S',text) or
                re.match(r'^\s*(?:Figure|Table)\s*\d+(?:\.\d+)*\s+(?=[A-Z(])',text))


def caption_anchor(line, page):
    """Disambiguate a caption prefix from a wrapped in-sentence reference."""
    if not caption_start(line['text']):
        return False
    if re.match(r'^\s*(?:fig(?:ure)?s?\.?)\s*[A-Z]?\d+(?:\.\d+)*[a-z]?\s*(?:\([a-z]\)\s*)?'
                r'(?:illustrates?|shows?|demonstrates?|depicts?|presents?|is|was|are|were)\b',line['text'],re.I):
        return False
    previous=[x for x in page['lines'] if x['native_block']==line['native_block'] and
              x['id']!=line['id'] and x['text'].strip() and
              x['bbox'][1]<line['bbox'][1]-.5 and
              abs(x['bbox'][0]-line['bbox'][0])<line['size']*3]
    if previous:
        prior=max(previous,key=lambda x:x['bbox'][1])
        # An unfinished prose line can wrap immediately before "Fig. 2. (a)".
        # A standalone caption at a font/paragraph boundary remains eligible.
        if (len(prior['text'].strip())>25 and not terminal_sentence(prior['text']) and
                line['bbox'][1]-prior['bbox'][3]<line['size']*.7 and
                abs(math.log(max(.1,prior['size'])/max(.1,line['size'])))<.12):
            return False
    return True


def terminal_sentence(text):
    # A citation after a period is still an end of sentence. PDF text often
    # inserts spaces inside superscript citation brackets.
    text=re.sub(r'(?:\s*\[\s*\d[\d\s,;–—-]*\])+$','',text.strip())
    return bool(re.search(r'[.!?。！？:]\s*$',text))


def numbered_typographic_heading(line,page):
    """A numbered section followed locally by a different prose font.

    Unknown embedded font names still distinguish typefaces. Require an actual
    typographic transition; numbering alone cannot distinguish a list item.
    """
    text=line['text'].strip();box=line['bbox'];size=max(1,line['size'])
    if not re.match(r'^\d+(?:\.\d+)*\.\s+[A-Z]',text) or len(text)>=100 or terminal_sentence(text):return False
    return any(x['bbox'][1]>box[1]+.5 and 0<=x['bbox'][1]-box[3]<size*1.8 and
               abs(x['bbox'][0]-box[0])<size*3 and
               font_key(x['font'])!=font_key(line['font']) and
               len(x['text'].strip())>50 for x in page.get('lines',[]))


def list_marker(line,page):
    text=line['text'].strip()
    if not LIST_START.match(text) or REFERENCE.match(text) or caption_start(text) or EXPLICIT_HEADING.fullmatch(text) or SECTION_HEADING.match(text) or numbered_typographic_heading(line,page):return False
    previous=[x for x in page.get('lines',[]) if x['native_block']==line['native_block'] and x['text'].strip() and
              x['bbox'][1]<line['bbox'][1]-.5 and abs(x['bbox'][0]-line['bbox'][0])<line['size']*3]
    if previous:
        prior=max(previous,key=lambda x:x['bbox'][1])
        if re.search(r'\b(?:fig(?:ure)?s?|tables?|eq(?:uation)?s?|no)\.?\s*$',prior['text'],re.I):return False
        # A numeric token can close a parenthetical phrase split at a physical
        # line boundary, e.g. "(delay" / "2)". The measured adjacent same-block
        # continuation is distinct from an independently numbered list item.
        if (re.match(r'^\d+\)\s',text) and prior['text'].count('(')>prior['text'].count(')') and
                line['bbox'][1]-prior['bbox'][3]<line['size']*.8 and
                abs(line['bbox'][0]-prior['bbox'][0])<line['size']*.5):return False
    return True


def text_baseline(line):
    spans=[s for s in line['spans'] if s.get('text','').strip()]
    if not spans:return line['bbox'][3]
    largest=max(s.get('size',line['size']) for s in spans)
    main=[s for s in spans if s.get('size',line['size'])>=largest*.88]
    weighted=sorted((s.get('origin',[0,line['bbox'][3]])[1],max(1,len(s['text'].strip()))) for s in main)
    half=sum(n for _,n in weighted)/2;total=0
    for baseline,n in weighted:
        total+=n
        if total>=half:return baseline
    return weighted[-1][0]


def suspect_native_encoding(text):
    """A repeated print ligature can encode a radical's drawn rule, not prose."""
    stripped=text.strip()
    return bool(len(stripped)>=3 and any(c in stripped for c in 'ﬀﬁﬂﬃﬄﬅﬆ') and
                max(Counter(stripped).values())/len(stripped)>.75)


def fragmented_prose_block(lines):
    """Conservative evidence for narrow justified prose split into words.

    Several regularly spaced baselines must fill a common paragraph edge.
    Small label grids without continuous sentence text remain separate. This
    only recovers whitespace and never supplies missing text or equation syntax.
    """
    if len(lines)<6:return False
    scale=median([x['size'] for x in lines]);box=union([x['bbox'] for x in lines])
    text=' '.join(x['text'].strip() for x in lines)
    if not (6*scale<box[2]-box[0]<32*scale and
            sum(c.isalpha() for c in text)>120 and
            sum(c in '.,;。；，' for c in text)>=2 and
            sum(c.isalpha() for c in text)/max(1,len(text))>.65):return False
    bands=[]
    for row in sorted(lines,key=text_baseline):
        if not bands or text_baseline(row)-text_baseline(bands[-1][0])>scale*.2:bands.append([row])
        else:bands[-1].append(row)
    if len(bands)<5 or not any(len(band)>1 for band in bands):return False
    steps=[text_baseline(b[0])-text_baseline(a[0]) for a,b in zip(bands,bands[1:])]
    if sum(.85*scale<step<1.9*scale for step in steps)<len(steps)*.8:return False
    edges=[union([x['bbox'] for x in band]) for band in bands]
    return (sum(abs(b[0]-box[0])<scale*.4 or abs(b[2]-box[2])<scale*.4 for b in edges)>=len(edges)*.85)


def subfigure_prefix(text):
    return bool(re.match(r'^\s*\([a-z]\)\s+\S.{4,}',text))


def physical_rows(native, table_regions=None, heading_regions=None):
    """Rejoin same-native-block PDF fragments on one printed text baseline.

    Mathematical and rotated fragments stay separate. Native line IDs remain
    immutable evidence; this is whitespace recovery, never word generation.
    """
    cells=[cell for table in (table_regions or []) for cell in table.get('cells',[]) if cell]
    def cell_for(line):
        x=(line['bbox'][0]+line['bbox'][2])/2;y=(line['bbox'][1]+line['bbox'][3])/2
        return next((i for i,c in enumerate(cells) if c[0]-.3<=x<=c[2]+.3 and c[1]-.3<=y<=c[3]+.3),None)
    def heading_region(line):
        x=(line['bbox'][0]+line['bbox'][2])/2;y=text_baseline(line)
        choices=[(i,r) for i,r in enumerate(heading_regions or []) if r[0]<=x<=r[2] and r[1]-1<=y<=r[3]+1]
        return min(choices,key=lambda item:(item[1][2]-item[1][0])*(item[1][3]-item[1][1]))[0] if choices else None
    blocks={}
    for line in native:blocks.setdefault(line['native_block'],[]).append(line)
    result=[]
    for lines in blocks.values():
        anchors=[r for r in lines if caption_start(r['text'])]
        def caption_panel(line):
            # Several numbered captions can share one native block. A shared
            # baseline does not permit joining their independent continuations.
            scale=max(1,line['size']);baseline=text_baseline(line)
            nearby=[r for r in anchors if -.3*scale<=baseline-text_baseline(r)<=scale*6]
            aligned=[r for r in nearby if any(abs(text_baseline(r)-text_baseline(other))<scale*.4 and
                     abs(r['bbox'][0]-other['bbox'][0])>scale*6 for other in nearby)]
            eligible=[r for r in aligned if r['bbox'][0]-scale*.5<=line['bbox'][0]]
            return max(eligible,key=lambda r:r['bbox'][0])['id'] if eligible else None
        panels={line['id']:caption_panel(line) for line in lines}
        header_panels={line['id']:heading_region(line) for line in lines}
        normal_size=median([x['size'] for x in lines])
        dropcaps={}
        for initial in lines:
            if len(initial['text'].strip())!=1 or not initial['text'].strip().isalpha() or initial['size']<normal_size*1.65:continue
            targets=[x for x in lines if x is not initial and len(x['text'])>12 and x['size']<initial['size']/1.65 and
                     abs(x['bbox'][1]-initial['bbox'][1])<x['size']*.7 and
                     -1<=x['bbox'][0]-initial['bbox'][2]<x['size']*2]
            if targets:dropcaps[initial['id']]=min(targets,key=lambda x:(x['bbox'][1],x['bbox'][0]))['id']
        text_block=' '.join(x['text'] for x in lines)
        author_rows=(len(re.findall(r'\b[A-Z][a-z]{2,}',text_block))>=5 and text_block.count(',')>=2 and
                     bool(re.search(r'(?<=[A-Za-z])\d[*∗†‡,\s]',text_block)))
        # Compact section numbers and their title share a printed baseline.
        # Other small native blocks may contain unrelated table/figure cells.
        section_number=(len(lines)==2 and bool(re.fullmatch(r'(?:\d+(?:\.\d+)*\.?|[IVXLC]+\.)',lines[0]['text'].strip())) and
                        abs(text_baseline(lines[0])-text_baseline(lines[1]))<.8 and
                        0<=lines[1]['bbox'][0]-lines[0]['bbox'][2]<lines[0]['size']*2 and
                        (lines[0]['flags']&16 or lines[0]['size']>11 or re.search(r'bold|medi',lines[0]['font'],re.I) or
                         EXPLICIT_HEADING.fullmatch(lines[1]['text'].strip()) or lines[1]['text'].strip().isupper()))
        subfigure_fragments=any(subfigure_prefix(x['text']) for x in lines)
        short_caption_fragments=bool(len(lines)==2 and caption_start(lines[0]['text']) and
            not caption_start(lines[1]['text']) and not subfigure_prefix(lines[1]['text']) and
            abs(text_baseline(lines[0])-text_baseline(lines[1]))<.8 and
            0<=lines[1]['bbox'][0]-lines[0]['bbox'][2]<lines[0]['size']*4)
        if max(len(x['text']) for x in lines)<35 and not section_number and not author_rows and not subfigure_fragments and not short_caption_fragments and not fragmented_prose_block(lines):
            result.extend({**x,'native_line_ids':[x['id']]} for x in lines);continue
        rows=[]
        for line in lines:
            if line['id'] in dropcaps:continue
            if abs(line['direction'][1])>.05 or suspect_native_encoding(line['text']):
                rows.append([line]);continue
            origin=text_baseline(line)
            match=None
            for row in reversed(rows):
                base=max(row,key=lambda x:len(x['text']));baseline=text_baseline(base)
                if any(suspect_native_encoding(x['text']) for x in row):continue
                if cell_for(base)!=cell_for(line):continue
                if header_panels[base['id']]!=header_panels[line['id']]:continue
                if panels[base['id']]!=panels[line['id']]:continue
                rowbox=union([x['bbox'] for x in row])
                gap=max(0,line['bbox'][0]-rowbox[2],rowbox[0]-line['bbox'][2])
                scale=max(line['size'],base['size'])
                if caption_start(line['text']) and any(caption_start(member['text']) for member in row):continue
                if subfigure_prefix(line['text']) and any(subfigure_prefix(member['text']) for member in row):continue
                if not author_rows and gap>scale*.6 and len(line['text'].strip())>=35 and len(base['text'].strip())>=35:continue
                overlaps=not (line['bbox'][0]>=rowbox[2]-scale*.5 or line['bbox'][2]<=rowbox[0]+scale*.5)
                # A serializer may emit a subscript before its containing text
                # run. Permit nested fragments only when actual nonspace glyph
                # boxes do not collide; never deduplicate overlapping text.
                collision=False
                if overlaps:
                    incoming=[c for span in line['spans'] for c in span.get('chars',[]) if c['c'].strip()]
                    present=[c for member in row for span in member['spans'] for c in span.get('chars',[]) if c['c'].strip()]
                    if not incoming or not present:collision=True
                    for a in incoming:
                        for b in present:
                            ax,by=a['bbox'],b['bbox']
                            area=max(0,min(ax[2],by[2])-max(ax[0],by[0]))*max(0,min(ax[3],by[3])-max(ax[1],by[1]))
                            if area>.3*min(max(.1,(ax[2]-ax[0])*(ax[3]-ax[1])),max(.1,(by[2]-by[0])*(by[3]-by[1]))):
                                collision=True;break
                        if collision:break
                if line['direction']==base['direction'] and abs(origin-baseline)<max(.8,scale*.16) and gap<scale*4 and not collision:
                    match=row;break
            if match is None:rows.append([line])
            else:match.append(line)
        for initial_id,target_id in dropcaps.items():
            initial=next(x for x in lines if x['id']==initial_id)
            for row in rows:
                if any(x['id']==target_id for x in row):row.append(initial);break
        for row in rows:
            row.sort(key=lambda x:x['bbox'][0]);parts=[];spans=[];right=None
            for line in row:
                previous_is_initial=bool(parts and any(x['id'] in dropcaps and x['text']==parts[-1] for x in row))
                if right is not None and line['bbox'][0]-right>.65 and parts and not previous_is_initial and not parts[-1].endswith(' ') and not line['text'].startswith(' '):parts.append(' ')
                parts.append(line['text']);right=line['bbox'][2];spans.extend(line['spans'])
            principal=max(row,key=lambda x:len(x['text']))
            nested=any(a['bbox'][0]<b['bbox'][0]<a['bbox'][2] and b['bbox'][2]<a['bbox'][2]+.5
                       for a in row for b in row if a is not b)
            glyph_runs=[]
            if nested and all(span.get('chars') for member in row for span in member['spans'] if span['text'].strip()):
                atoms=[{**c,'native_line_id':member['id'],'size':span.get('size',member['size']),
                        'font':span.get('font',member['font'])}
                       for member in row for span in member['spans'] for c in span.get('chars',[])]
                nonspace=[c for c in atoms if c['c'].strip()]
                def occupied_space(c):
                    return any(d['native_line_id']!=c['native_line_id'] and
                               min(c['bbox'][2],d['bbox'][2])-max(c['bbox'][0],d['bbox'][0])>
                               min(c['bbox'][2]-c['bbox'][0],d['bbox'][2]-d['bbox'][0])*.45
                               for d in nonspace)
                atoms=[c for c in atoms if c['c'].strip() or not occupied_space(c)]
                atoms.sort(key=lambda c:(c['bbox'][0],c['bbox'][1]))
                parts=[];prior=None
                for atom in atoms:
                    if (prior and prior['native_line_id']!=atom['native_line_id'] and
                            atom['bbox'][0]-prior['bbox'][2]>.65 and
                            not prior['c'].isspace() and not atom['c'].isspace()):parts.append(' ')
                    parts.append(atom['c']);prior=atom
                glyph_runs=atoms
            result.append({**principal,'id':row[0]['id'],'text':''.join(parts),'bbox':union([x['bbox'] for x in row]),'spans':spans,'native_line_ids':[x['id'] for x in row],
                           'row_fragments':[{'native_line_id':x['id'],'text':x['text'],'bbox':x['bbox']} for x in row],
                           'inline_glyph_runs':glyph_runs})
    # A hanging bibliography number may be serialized in a separate native
    # object. Rejoin only a short bracketed marker and its unique same-baseline
    # text neighbour. Preserve every native line and measured glyph run.
    for marker in list(result):
        if not re.fullmatch(r'\s*\[\d{1,4}\]\s*',marker['text']):continue
        peers=[row for row in result if row is not marker and len(row['text'].strip())>25 and
               abs(text_baseline(row)-text_baseline(marker))<marker['size']*.25 and
               0<=row['bbox'][0]-marker['bbox'][2]<marker['size']*2.5 and
               abs(math.log(max(.1,row['size'])/max(.1,marker['size'])))<.1]
        if len(peers)!=1:continue
        row=peers[0];row['text']=marker['text'].strip()+' '+row['text'].lstrip();row['bbox']=union([marker['bbox'],row['bbox']])
        row['native_line_ids']=marker.get('native_line_ids',[marker['id']])+row.get('native_line_ids',[row['id']])
        row['row_fragments']=marker.get('row_fragments',[])+row.get('row_fragments',[])
        row['spans']=marker['spans']+row['spans'];row['inline_glyph_runs']=[]
        result.remove(marker)
    return result


def raw_page(page, detect_tables=False):
    import fitz
    flags = fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES
    raw = page.get_text('rawdict', flags=flags, sort=False)
    lines = []
    for bi, block in enumerate(raw['blocks']):
        if block.get('type') != 0:
            continue
        for li, line in enumerate(block.get('lines', [])):
            spans = []
            for si, span in enumerate(line['spans']):
                chars = span.get('chars', [])
                text = ''.join(c['c'] for c in chars)
                spans.append({**{k:v for k,v in span.items() if k!='chars'}, 'text':text, 'chars':chars, 'index':si})
            text = ''.join(s['text'] for s in spans)
            if not text:
                continue
            weights = [(len(s['text'].strip()), s) for s in spans if s['text'].strip()]
            principal = max(weights, key=lambda x:x[0])[1] if weights else spans[0]
            lines.append({'id':f'p{page.number+1:04d}-b{bi:04d}-l{li:04d}', 'native_block':bi, 'native_line':li,
                          'text':text, 'bbox':list(line['bbox']), 'direction':list(line.get('dir',[1,0])),
                          'wmode':line.get('wmode',0), 'spans':spans, 'size':float(principal.get('size',10)),
                          'font':principal.get('font',''), 'flags':principal.get('flags',0)})
    tables=[];table_error=None
    if detect_tables:
        try:
            for table in page.find_tables().tables:
                if table.row_count>=2 and table.col_count>=2:tables.append({'bbox':list(table.bbox),'rows':table.row_count,'columns':table.col_count,'cells':[list(c) if c else None for c in table.cells]})
        except Exception as error:table_error=str(error)
    tables,rejected_tables=filter_table_regions(lines,tables,page.rect.width,page.rect.height)
    structure_regions=[];graphic_regions=[];heading_regions=[]
    try:
        horizontal=[];vertical=[]
        for drawing in page.get_drawings():
            rect=drawing.get('rect')
            if (rect and drawing.get('fill') is not None and rect.width>page.rect.width*.2 and
                    6<=rect.height<=40 and 0<=rect.x0<rect.x1<=page.rect.width and
                    0<=rect.y0<rect.y1<=page.rect.height):
                heading_regions.append(list(rect))
            if (rect and rect.width>=3 and rect.height>=3 and rect.width*rect.height>=36 and
                    0<=rect.x0<rect.x1<=page.rect.width and 0<=rect.y0<rect.y1<=page.rect.height and
                    rect.width*rect.height<=page.rect.width*page.rect.height*.05):
                graphic_regions.append([rect.x0,rect.y0,rect.x1,rect.y1])
            for item in drawing.get('items',[]):
                if item[0]=='re':
                    box=item[1]
                    if box.height<=2 and box.width>=8:horizontal.append((box.x0,(box.y0+box.y1)/2,box.x1))
                    elif box.width<=2 and box.height>=8:vertical.append(((box.x0+box.x1)/2,box.y0,box.y1))
                    continue
                if item[0]!='l':continue
                a,b=item[1],item[2]
                if abs(a.y-b.y)<=.6 and abs(a.x-b.x)>=8:
                    horizontal.append((min(a.x,b.x),a.y,max(a.x,b.x)))
                elif abs(a.x-b.x)<=.6 and abs(a.y-b.y)>=8:
                    vertical.append((a.x,min(a.y,b.y),max(a.y,b.y)))
        horizontal=coalesce_horizontal_rules(horizontal,page.rect.width)
        candidates=[]
        for index,(left,top,right) in enumerate(horizontal):
            for x0,bottom,x1 in horizontal[index+1:]:
                if bottom-top<35 or bottom-top>page.rect.height*.38:continue
                overlap=max(0,min(right,x1)-max(left,x0))/max(1,min(right-left,x1-x0))
                if overlap<.72:continue
                candidate=[max(0,min(left,x0)),min(top,bottom),min(page.rect.width,max(right,x1)),max(top,bottom)]
                nested=any(min(t['bbox'][2],candidate[2])-max(t['bbox'][0],candidate[0])>10 and
                           min(t['bbox'][3],candidate[3])-max(t['bbox'][1],candidate[1])>20 for t in tables)
                interior=sorted(x for x,y0,y1 in vertical if candidate[0]+5<x<candidate[2]-5 and
                                y0<=candidate[1]+3 and y1>=candidate[3]-3)
                figure_grid=any(r['bbox'][0]-.5<=candidate[0] and r['bbox'][1]-.5<=candidate[1] and
                                r['bbox'][2]+.5>=candidate[2] and r['bbox'][3]+.5>=candidate[3] for r in rejected_tables)
                if (nested or len(interior)>=2) and not figure_grid:candidates.append(candidate)
        for candidate in sorted(candidates,key=lambda r:(-(r[2]-r[0])*(r[3]-r[1]),r[1],r[0])):
            if not any(r[0]<=candidate[0]+1 and r[1]<=candidate[1]+1 and r[2]>=candidate[2]-1 and r[3]>=candidate[3]-1
                       for r in structure_regions):structure_regions.append(candidate)
        structure_regions.extend(horizontal_table_boxes(lines,horizontal,page.rect.width,page.rect.height))
        # A below-table caption can otherwise seed a false table extending into
        # the following figure plate. Keep local detector cells and reject only
        # broad inferred rectangles containing several distinct figure captions.
        structure_regions=[box for box in structure_regions if not {m.group(1) for row in lines
            if box[0]<=(row['bbox'][0]+row['bbox'][2])/2<=box[2] and box[1]<=row['bbox'][1]<=box[3]
            and (m:=re.match(r'^\s*(?:fig(?:ure)?s?\.?)\s*([A-Z]?\d+(?:\.\d+)*)[.:|\s]',row['text'],re.I))}]
        for image in page.get_images(full=True):
            for rect in page.get_image_rects(image[0]):
                if (rect.width>=3 and rect.height>=3 and rect.width*rect.height>=36 and
                        0<=rect.x0<rect.x1<=page.rect.width and 0<=rect.y0<rect.y1<=page.rect.height and
                        rect.width*rect.height<=page.rect.width*page.rect.height*.05):
                    graphic_regions.append([rect.x0,rect.y0,rect.x1,rect.y1])
    except Exception as error:
        table_error=table_error or str(error)
    return {'page':page.number+1,'width':page.rect.width,'height':page.rect.height,'rotation':page.rotation,
            'cropbox':list(page.cropbox),'lines':physical_rows(lines,tables,heading_regions),'native_lines':lines,'raw_sha256':digest(lines),
            'table_regions':tables,'rejected_table_regions':rejected_tables,'structure_regions':structure_regions,'graphic_regions':graphic_regions,
            'heading_regions':heading_regions,
            'table_detection_error':table_error,'extraction_revision':EXTRACTION_REVISION}


def coalesce_horizontal_rules(rules,width):
    """Join contiguous source rule segments, including thin filled rectangles.

    A rule is geometric evidence only. Caption and repeated cell bands must
    still corroborate a table; no line creates cell text or semantic truth.
    """
    bands=[]
    for left,y,right in sorted(rules,key=lambda r:(r[1],r[0])):
        band=next((b for b in reversed(bands) if abs(b[0][1]-y)<=.8),None)
        if band is None:bands.append([(left,y,right)])
        else:band.append((left,y,right))
    result=[]
    for band in bands:
        spans=[]
        for left,y,right in sorted(band):
            if spans and left<=spans[-1][2]+1.5:spans[-1]=(spans[-1][0],spans[-1][1],max(spans[-1][2],right))
            else:spans.append((left,y,right))
        result.extend(r for r in spans if r[2]-r[0]>=width*.15)
    return result


def horizontal_table_boxes(lines,horizontal,width,height):
    """Caption + aligned horizontal rules + repeated cell bands, without verticals.

    These rectangles are role proposals, never generated cell contents. End a
    proposal before later captions or larger-font narrative, and require actual
    separate text columns on at least two source baselines.
    """
    boxes=[];rules=sorted(set(horizontal),key=lambda r:r[1])
    for caption in lines:
        if not re.match(r'^\s*table\b',caption['text'],re.I) or not caption_start(caption['text']):continue
        size=max(1,caption['size']);cb=caption['bbox']
        starts=[r for r in rules if 0<=r[1]-cb[3]<size*4 and r[0]-size*5<=(cb[0]+cb[2])/2<=r[2]+size*5]
        if not starts:continue
        top=min(starts,key=lambda r:r[1]);left,y0,right=top
        stop=y0+height*.38
        for row in lines:
            box=row['bbox']
            if box[1]<=y0:continue
            if (caption_start(row['text']) or
                len(row['text'].strip())>65 and row['size']>=size*1.06) and min(right,box[2])-max(left,box[0])>size*3:
                stop=min(stop,box[1])
        aligned=[r for r in rules if y0+20<r[1]<stop and abs(r[0]-left)<width*.035 and abs(r[2]-right)<width*.035]
        if not aligned:continue
        bottom=max(r[1] for r in aligned)
        cells=[r for r in lines if y0<=r['bbox'][1] and r['bbox'][3]<=bottom+.8 and
               left-.5<=r['bbox'][0] and r['bbox'][2]<=right+.5]
        bands=[]
        for cell in sorted(cells,key=lambda r:(text_baseline(r),r['bbox'][0])):
            if not bands or abs(text_baseline(cell)-text_baseline(bands[-1][0]))>size*.6:bands.append([cell])
            else:bands[-1].append(cell)
        if sum(len(band)>=2 and max(r['bbox'][0] for r in band)-min(r['bbox'][0] for r in band)>size*4 for band in bands)>=2:
            boxes.append([left,y0,right,bottom])
    return boxes


def filter_table_regions(lines,tables,width,height):
    """Keep detector evidence but do not force multi-figure frames into cells.

    A grid is a geometric proposal, not proof of a semantic table. Multiple
    independently numbered figure captions inside one frame are contradictory
    evidence. A nested local grid needs its own caption or dense populated
    cells; the multi-figure outer frame alone is not a table veto.
    """
    captions=[r for r in lines if caption_start(r['text']) and not re.match(r'^\s*table\b',r['text'],re.I)]
    rejected=[];kept=[]
    for table in tables:
        box=table['bbox']
        anchors=[r for r in captions if box[0]<=(r['bbox'][0]+r['bbox'][2])/2<=box[2] and box[1]<=r['bbox'][1]<=box[3]]
        figures={m.group(1) for r in anchors if (m:=re.match(r'^\s*(?:fig(?:ure)?s?\.?)\s*([A-Z]?\d+(?:\.\d+)*)',r['text'],re.I))}
        if len(figures)>=2:
            rejected.append({**table,'reason':'multiple-numbered-figure-captions-inside-grid','figure_numbers':sorted(figures)})
        else:kept.append(table)
    remaining=[]
    for table in kept:
        box=table['bbox'];cx=(box[0]+box[2])/2
        parent=any(r['bbox'][0]-.5<=box[0] and r['bbox'][1]-.5<=box[1] and
                   r['bbox'][2]+.5>=box[2] and r['bbox'][3]+.5>=box[3] for r in rejected)
        below=[r for r in captions if 0<=r['bbox'][1]-box[3]<height*.25 and r['bbox'][0]-width*.025<=cx<=r['bbox'][2]+width*.025]
        table_label=any(re.match(r'^\s*table\b',r['text'],re.I) and
                        (0<=box[1]-r['bbox'][3]<height*.1 or 0<=r['bbox'][1]-box[3]<height*.04) and
                        box[0]-width*.05<=(r['bbox'][0]+r['bbox'][2])/2<=box[2]+width*.05 for r in lines)
        cells=[cell for cell in table.get('cells',[]) if cell]
        occupied=sum(any(r['text'].strip() and cell[0]<=(r['bbox'][0]+r['bbox'][2])/2<=cell[2] and
                         cell[1]<=(r['bbox'][1]+r['bbox'][3])/2<=cell[3] for r in lines) for cell in cells)
        dense_data=bool(len(cells)>=8 and table.get('rows',0)>=3 and table.get('columns',0)>=3 and occupied/len(cells)>=.7)
        local_data=table_label or dense_data
        if (parent and not local_data) or (below and not local_data):
            rejected.append({**table,'reason':'nested-in-figure-grid' if parent else 'small-grid-in-figure-caption-context'})
        else:remaining.append(table)
    return remaining,rejected


def furniture_key(line,page):
    bb=line['bbox']
    if not (bb[1]<page['height']*.09 or bb[3]>page['height']*.91 or abs(line['direction'][1])>.05):return None
    text=re.sub(r'\d+','#',line['text'].strip().casefold())
    return text if text else None


def raised_footnote_marker(line):
    """Read an actual smaller raised leading glyph; never infer missing marks."""
    spans=sorted([span for span in line.get('spans',[]) if span.get('text','').strip()],
                 key=lambda span:span['bbox'][0])
    if len(spans)<2:return False
    first=spans[0];others=spans[1:]
    return bool(re.fullmatch(r'\d{1,3}|[*†‡]',first['text'].strip()) and
                first.get('size',line['size'])<line['size']*.85 and
                text_baseline(line)-first.get('origin',[0,0])[1]>line['size']*.15 and
                any(len(span['text'].strip())>=3 for span in others))


def document_profile(pages):
    sizes = Counter(); fonts = Counter(); words = Counter(); max_size = 0; furniture=Counter()
    for page in pages:
        furniture.update({key for line in page['lines'] if (key:=furniture_key(line,page))})
        for line in page['lines']:
            text = line['text']; n = len(text.strip()); max_size = max(max_size,line['size'])
            if n>30:
                sizes[round(line['size']*4)/4] += n
                fonts[font_key(line['font'])] += n
            for word in re.findall(r'[^\W\d_]{4,}', text.translate(LIGATURES), re.UNICODE):
                words[word.casefold()] += 1
    size = sizes.most_common(1)[0][0] if sizes else 10
    title_bands=[]
    if pages:
        first=pages[0]
        titles=[x for x in first['lines'] if x['size']>=size*1.18 and len(x['text'].strip())>12 and
                x['bbox'][2]-x['bbox'][0]>first['width']*.3 and not METADATA.search(x['text']) and
                x['bbox'][1]<first['height']*.38 and abs(x['direction'][1])<.05]
        if titles:
            # A small magazine masthead can precede the actual large title.
            # Pick the dominant eligible type size, excluding single drop caps,
            # then retain same-block title lines beyond the initial top band.
            seed=max(titles,key=lambda x:(x['size'],-x['bbox'][1]));group=[seed]
            for candidate in sorted(first['lines'],key=lambda x:(x['bbox'][1],x['bbox'][0])):
                if candidate is seed or candidate['bbox'][1]<seed['bbox'][1]-.5:continue
                aligned_short=(candidate['bbox'][2]-candidate['bbox'][0]>first['width']*.15 and
                    abs((candidate['bbox'][0]+candidate['bbox'][2]-seed['bbox'][0]-seed['bbox'][2])/2)<seed['size']*2 and
                    font_key(candidate['font'])==font_key(seed['font']) and not METADATA.search(candidate['text']))
                if candidate['native_block']!=seed['native_block'] and candidate not in titles and not aligned_short:continue
                if abs(math.log(candidate['size']/seed['size']))>.1 or candidate['bbox'][1]-group[-1]['bbox'][3]>seed['size']*.9:break
                group.append(candidate)
            titles=group
            title_bands=[min(x['bbox'][1] for x in titles),max(x['bbox'][3] for x in titles)]
    front_matter_bottom=None
    if pages and title_bands:
        first=pages[0]
        cutoff=[x['bbox'][1] for x in first['lines'] if ABSTRACT_START.search(x['text'])]
        if not cutoff:
            blocks={}
            for line in first['lines']:blocks.setdefault(line['native_block'],[]).append(line)
            for block in blocks.values():
                text=' '.join(line['text'].strip() for line in block)
                if (len(block)>=4 and min(line['bbox'][1] for line in block)>title_bands[1] and
                        len(text)>180 and terminal_sentence(text) and len(AFFILIATION_WORD.findall(text))<2):
                    cutoff.append(min(line['bbox'][1] for line in block))
        if cutoff:front_matter_bottom=min(cutoff)
    return {'body_size':size,'body_fonts':[x for x,_ in fonts.most_common(3)],'max_size':max_size or size,
            'native_words':sorted(words),'repeated_furniture':[k for k,n in furniture.items() if n>=2],'font_histogram':dict(fonts),'size_histogram':dict(sizes),'title_band':title_bands,'front_matter_bottom':front_matter_bottom}


def captioned_table_boxes(page):
    """A table label corroborates detector/drawn-grid geometry, never cell truth."""
    captions=[r for r in page.get('lines',[]) if re.match(r'^\s*table\b',r['text'],re.I) and caption_anchor(r,page)]
    boxes=[list(t['bbox']) for t in page.get('table_regions',[])]+[list(r) for r in page.get('structure_regions',[])]
    # Repeated horizontal rules can yield overlapping partial grid rectangles.
    # Union them before checking distance to the single caption above the table.
    merged=[]
    for box in sorted(boxes,key=lambda b:(b[1],b[0])):
        for i,prior in enumerate(merged):
            overlap_x=max(0,min(box[2],prior[2])-max(box[0],prior[0]))
            overlap_y=max(0,min(box[3],prior[3])-max(box[1],prior[1]))
            if (overlap_x>.85*min(box[2]-box[0],prior[2]-prior[0]) and
                    overlap_y>.5*min(box[3]-box[1],prior[3]-prior[1])):
                merged[i]=union([prior,box]);break
        else:merged.append(box)
    boxes=merged
    return [box for box in boxes if any(
        (0<=box[1]-cap['bbox'][3]<max(1,cap['size'])*4 or
         0<=cap['bbox'][1]-box[3]<max(1,cap['size'])*2) and
        box[0]-cap['size']*5<=(cap['bbox'][0]+cap['bbox'][2])/2<=box[2]+cap['size']*5
        for cap in captions)]


def subfigure_caption_context(line,page):
    peers=[r for r in page['lines'] if r['native_block']==line['native_block'] and subfigure_prefix(r['text'])]
    for anchor in peers:
        size=max(1,anchor['size']);box=anchor['bbox']
        if abs(line['bbox'][1]-box[1])>size*1.3 or abs(line['size']-anchor['size'])>size*.15:continue
        below_graph=any(-size*.1<=box[1]-r[3]<size*3.4 and
                        min(box[2],r[2])-max(box[0],r[0])>min(box[2]-box[0],r[2]-r[0])*.5
                        for r in page.get('graphic_regions',[]))
        main_caption=any(caption_anchor(r,page) and not re.match(r'^\s*table\b',r['text'],re.I) and
                         box[3]<r['bbox'][1]<box[3]+page['height']*.6 for r in page['lines'])
        if below_graph and main_caption:return True
    return False


def role_features(line, page, profile):
    text=line['text'].strip(); bb=line['bbox']; w=page['width']; h=page['height']; size=max(.1,line['size']); n=max(1,len(text)); alpha=sum(c.isalpha() for c in text)
    peers=[x for x in page['lines'] if x['native_block']==line['native_block'] and x['text'].strip()] or [line]
    pos=next((i for i,x in enumerate(peers) if x['id']==line['id']),0)
    block_text=' '.join(x['text'] for x in peers)
    author_text=re.sub(r'(?<=[A-Za-zÀ-ÖØ-öø-ÿ])\d{1,2}(?=[*†‡∗,;]|\s|$)','',block_text)
    block_names=len(re.findall(r'\b[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ’\-]{1,}\b',author_text))
    block_initials=len(re.findall(r'\b[A-Z]\.\s*',block_text))
    author_markers=len(re.findall(r'(?<=[A-Za-zÀ-ÖØ-öø-ÿ])\d{1,2}(?=[*†‡∗,;]|\s|$)',block_text))
    author_line_context=bool(page['page']==1 and size<profile['body_size']*1.5 and bb[1]<h*.34 and len(block_text)<500 and block_text.count(',')>=1 and
                             ((block_initials>=2) or (block_names>=3 and (author_markers>=2 or re.search(r'[*†‡∗]',block_text)))))
    affiliation_terms=len(AFFILIATION_WORD.findall(block_text))
    affiliation_block_context=bool(page['page']==1 and not ABSTRACT_START.search(text) and not any(ABSTRACT_START.search(x['text']) for x in peers[:pos+1]) and affiliation_terms>=2 and len(block_text)<2500 and
                                   (('@' in block_text or re.search(r'\b\d{1,2}\s*(?:department|faculty|school|university|institute)',block_text,re.I)) or affiliation_terms>=4))
    def inside_table(candidate):
        box=candidate['bbox'];cx=(box[0]+box[2])/2;cy=(box[1]+box[3])/2
        return any(t['bbox'][0]-.5<=cx<=t['bbox'][2]+.5 and t['bbox'][1]-.5<=cy<=t['bbox'][3]+.5
                   for t in page.get('table_regions',[]))
    anchors=[x for x in peers[:pos+1] if caption_anchor(x,page)]
    caption_context=caption_anchor(line,page)
    if not caption_context and not inside_table(line):
        for anchor in reversed(anchors):
            chain=[x for x in peers if anchor['bbox'][1]-.5<=x['bbox'][1]<=bb[1]+.5]
            chain.sort(key=lambda x:(x['bbox'][1],x['bbox'][0]))
            if (all(not inside_table(x) and abs(math.log(max(.1,x['size'])/max(.1,anchor['size'])))<.15 for x in chain) and
                    all(b['bbox'][1]-a['bbox'][3]<size*1.1 for a,b in zip(chain,chain[1:]))):
                caption_context=True;break
    if not caption_context:
        current=line;visited=set()
        for _ in range(12):
            center=(current['bbox'][0]+current['bbox'][2])/2;current_size=max(1,current['size'])
            previous=[x for x in page['lines'] if x['id']!=current['id'] and x['id'] not in visited and
                      x['bbox'][3]<=current['bbox'][1]+current_size*.2 and
                      abs((x['bbox'][0]+x['bbox'][2])/2-center)<current_size*5 and
                      abs(x['size']-current_size)<current_size*.35]
            if not previous:break
            earlier=max(previous,key=lambda x:x['bbox'][3]);gap=current['bbox'][1]-earlier['bbox'][3]
            if gap>current_size*1.05:break
            if inside_table(current) or SECTION_HEADING.fullmatch(current['text'].strip()) or EXPLICIT_HEADING.fullmatch(current['text'].strip()):break
            if SECTION_HEADING.fullmatch(earlier['text'].strip()) or EXPLICIT_HEADING.fullmatch(earlier['text'].strip()):break
            if abs(math.log(max(.1,earlier['size'])/current_size))>.18 and not re.match(r'^\s*table\b',earlier['text'],re.I):break
            if caption_anchor(earlier,page):caption_context=True;break
            visited.add(earlier['id']);current=earlier
    line_center=(bb[0]+bb[2])/2
    block_center=(min(x['bbox'][0] for x in peers)+max(x['bbox'][2] for x in peers))/2
    reference_context=any(REFERENCES_HEADING.search(x['text'].strip()) and x['bbox'][1]<bb[1] and
                          abs((x['bbox'][0]+x['bbox'][2])/2-block_center)<max(w*.18,(x['bbox'][2]-x['bbox'][0])*1.5)
                          for x in page['lines'])
    nearby_refs=[x for x in page['lines'] if REFERENCE.match(x['text']) and
                 abs(x['bbox'][0]-bb[0])<profile['body_size']*4]
    column_refs=[x for x in nearby_refs if abs(math.log(max(.1,x['size'])/size))<.1]
    # Bibliography sections often end at an author biography printed in a
    # different size. A heading above cannot override that local boundary.
    preceding_refs=[x for x in nearby_refs if x['bbox'][1]<bb[1]]
    if preceding_refs and not column_refs:reference_context=False
    if len(column_refs)>=3 and (any(REFERENCES_HEADING.fullmatch(x['text'].strip()) for x in page['lines']) or len(column_refs)>=5):
        region_top=min(x['bbox'][1] for x in column_refs)
        region_bottom=max(x['bbox'][3] for x in column_refs)+size*10
        intervening_heading=any(region_top<x['bbox'][1]<bb[1] and abs(x['bbox'][0]-bb[0])<profile['body_size']*5 and
                               (EXPLICIT_HEADING.fullmatch(x['text'].strip()) or SECTION_HEADING.fullmatch(x['text'].strip())) and
                               not REFERENCES_HEADING.fullmatch(x['text'].strip()) for x in page['lines'])
        # A bibliography entry can continue at the next column's top before
        # its first numbered marker. Match its type size and hanging column.
        reference_context |= region_top-size*4<=bb[1]<=region_bottom and not intervening_heading
    dense_reference_context=bool(sum(bool(REFERENCE.match(x['text'])) for x in peers)>=3 and REFERENCE.match(peers[0]['text']))
    section_heading_context=bool(SECTION_HEADING.search(text))
    if not section_heading_context and text.isupper() and 4<=len(text.strip())<=40:
        for x in page['lines']:
            if x['id']==line['id'] or x['bbox'][3]>bb[1]:continue
            if bb[1]-x['bbox'][3]>size*2.2 or abs(x['size']-size)>size*.35:continue
            if abs((x['bbox'][0]+x['bbox'][2])/2-line_center)>size*5:continue
            if SECTION_HEADING.search(x['text']):section_heading_context=True;break
    front_matter_bottom=profile.get('front_matter_bottom')
    title_band=profile.get('title_band') or []
    front_matter_metadata_context=bool(page['page']==1 and len(title_band)==2 and front_matter_bottom and
                                       bb[1]>title_band[1]-size*.5 and bb[3]<front_matter_bottom and size<profile['max_size']*.9)
    running_header_context=bool((bb[1]<h*.09 or bb[3]>h*.97) and size<=profile['body_size']*1.35 and len(text)<180 and
                                (bb[3]>h*.97 or size<profile['body_size']*.9 or font_key(line['font']) not in profile['body_fonts'][:1] or furniture_key(line,page) in profile.get('repeated_furniture',[])))
    running_header_context |= bool(page['page']>1 and bb[1]<h*.16 and size<profile['body_size']*.92 and
        len(peers)<=6 and re.search(r'\bet\s+al\.|\b(?:vol(?:ume)?\.?\s+\d|(?:19|20)\d{2})\b',block_text,re.I))
    running_header_context |= bool(furniture_key(line,page) in profile.get('repeated_furniture',[]) and
                                   (bb[1]<h*.09 or bb[3]>h*.91))
    if reference_context and furniture_key(line,page) not in profile.get('repeated_furniture',[]):
        running_header_context=False
    def list_predecessor(current):
        visited=set();after_terminal=False;initial=current
        for _ in range(40):
            candidates=[x for x in page['lines'] if x['id']!=current['id'] and x['id'] not in visited and
                       x['bbox'][1]<current['bbox'][1]-size*.35 and
                       -size*.45<=current['bbox'][1]-x['bbox'][3]<=max(2.5*size,22) and
                       abs(x['bbox'][0]-current['bbox'][0])<=max(2.5*size,18)]
            if not candidates:return False
            previous=max(candidates,key=lambda x:x['bbox'][3]);visited.add(previous['id'])
            previous_text=previous['text'].strip()
            if (abs(math.log(max(.1,previous['size'])/max(.1,current['size'])))>.12 or
                    any(caption_anchor(x,page) for x in page['lines'] if x['native_block']==previous['native_block'])):return False
            if EXPLICIT_HEADING.fullmatch(previous_text) or SECTION_HEADING.match(previous_text) or numbered_typographic_heading(previous,page) or caption_start(previous_text):return False
            if list_marker(previous,page):
                hanging=initial['bbox'][0]-previous['bbox'][0]
                return not after_terminal or size*.35<=hanging<=size*2.5
            if re.search(r'[.!?。！？:]\s*$',previous_text):
                # A hanging item may contain several complete sentences. A new
                # indented paragraph still ends propagation at its own boundary.
                if abs(current['bbox'][0]-previous['bbox'][0])>size*.3:return False
                after_terminal=True
            current=previous
        return False
    list_continuation_context=bool(list_predecessor(line))
    flags=line['flags']; font=font_key(line['font']); context=' '.join(x['text'] for x in peers[:3])
    preceding=(bb[1]-peers[pos-1]['bbox'][3])/size if pos else 2
    following=(peers[pos+1]['bbox'][1]-bb[3])/size if pos+1<len(peers) else 2
    small=sum(len(s['text']) for s in line['spans'] if s.get('size',size)<size*.85)/n
    math_count=sum(c in '=±∑∫√∞∂∇≈≠≤≥×÷∈∝∼∏∧∨⊂⊆⊗' or unicodedata.category(c)=='Sm' for c in text)
    def formula_like(candidate):
        candidate_text=candidate['text'].strip()
        math_chars=sum(len(span.get('text','').strip()) for span in candidate.get('spans',[])
                       if MATH_FONT.search(font_key(span.get('font',''))))
        math_ratio=math_chars/max(1,len(candidate_text))
        narrow=candidate['bbox'][2]-candidate['bbox'][0]<w*.48
        return bool(len(candidate_text)<=45 and narrow and
                    (math_ratio>=.35 or
                     (MATH_FONT.search(font_key(candidate['font'])) and len(candidate_text)<=24) or
                     (re.search(r'[=∑∫√≤≥≈×÷]',candidate_text) and len(candidate_text)<=24)))
    display_equation_context=bool(formula_like(line) or
                                    ((len(text)<=24 and bb[2]-bb[0]<w*.48) and any(formula_like(x) for x in peers)))
    alpha_heading=bool(re.match(r'^[A-Z]\.\s+[A-Z]',text) and len(text)<105 and not terminal_sentence(text) and
                       not author_line_context and not front_matter_metadata_context and
                       (bool(flags&18) or 'bold' in font or 'italic' in font))
    split_section_number=bool(re.fullmatch(r'[IVX]+\.',text) and len(peers)<=3 and any(EXPLICIT_HEADING.fullmatch(x['text'].strip()) for x in peers if x['id']!=line['id']))
    centered_bold_heading=bool(3<=len(text)<=90 and (flags&16 or 'bold' in font) and not terminal_sentence(text) and
        not caption_context and not display_equation_context and not front_matter_metadata_context and
        not any(r['bbox'][0]<=line_center<=r['bbox'][2] and r['bbox'][1]<=bb[1]<=r['bbox'][3] for r in page.get('rejected_table_regions',[])) and
        size>=profile['body_size']*.95 and size<profile['body_size']*1.3 and
        any(len(x['text'].strip())>80 and abs(x['size']-size)<size*.1 and 0<=x['bbox'][1]-bb[3]<size*1.8 and
            abs((x['bbox'][0]+x['bbox'][2])/2-line_center)<size*4 for x in page['lines']))
    numbered_font_heading=numbered_typographic_heading(line,page)
    explicit_heading_label=bool(EXPLICIT_HEADING.fullmatch(unicodedata.normalize('NFKC',text)) or REFERENCES_HEADING.fullmatch(text) or alpha_heading or split_section_number or centered_bold_heading or numbered_font_heading)
    if explicit_heading_label and not caption_anchor(line,page):caption_context=False
    metadata_continuation=False
    previous_row=line
    for earlier in reversed(peers[:pos]):
        if (abs(math.log(size/max(.1,earlier['size'])))>=.2 or explicit_heading_label or
                EXPLICIT_HEADING.fullmatch(earlier['text'].strip()) or SECTION_HEADING.fullmatch(earlier['text'].strip()) or
                ABSTRACT_START.search(previous_row['text']) or REFERENCE.match(previous_row['text']) or previous_row['bbox'][1]-earlier['bbox'][3]>size*1.8):break
        if EXPLICIT_METADATA.search(earlier['text']) or EXPLICIT_METADATA_EXTRA.search(earlier['text']):
            # Metadata may start in the middle of a mixed native block. Do not
            # propagate across an intervening empty paragraph or font change.
            metadata_continuation=not any(not x['text'].strip() and earlier['native_line']<x['native_line']<line['native_line'] for x in page['lines'] if x['native_block']==line['native_block'])
            break
        previous_row=earlier
    explicit_metadata_label=bool(EXPLICIT_METADATA.search(text) or EXPLICIT_METADATA_EXTRA.search(text) or
                                 COPYRIGHT_NOTICE.search(text) or metadata_continuation or
                                 (page['page']==1 and bb[1]<h*.5 and text.startswith('Citation ') and
                                  re.search(r'\bdoi\b|doi\.org',block_text,re.I)))
    graphic_context=bool(len(text)<=40 and any(r[0]-.5<=(bb[0]+bb[2])/2<=r[2]+.5 and r[1]-.5<=(bb[1]+bb[3])/2<=r[3]+.5 for r in page.get('graphic_regions',[])))
    captioned_table_context=any(r[0]-.5<=(bb[0]+bb[2])/2<=r[2]+.5 and r[1]-.5<=(bb[1]+bb[3])/2<=r[3]+.5 for r in captioned_table_boxes(page))
    subcaption_context=subfigure_caption_context(line,page)
    page_number_context=bool((bb[1]>h*.88 or bb[3]<h*.06) and re.fullmatch(r'\(?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?\)?',text,re.I))
    # A mixed native block may contain acknowledgments followed by references.
    # Only the contiguous funding paragraph can supply footnote context.
    local_footnote=[line]
    for earlier in reversed(peers[:pos]):
        if (REFERENCES_HEADING.fullmatch(earlier['text'].strip()) or REFERENCE.match(earlier['text']) or
                abs(earlier['size']-size)>size*.15 or local_footnote[-1]['bbox'][1]-earlier['bbox'][3]>size*1.8):break
        local_footnote.append(earlier)
    footnote_context=bool(bb[1]>h*.78 and size<profile['body_size']*.92 and
                          (FOOTNOTE_START.search(' '.join(x['text'] for x in reversed(local_footnote))) or
                           any(raised_footnote_marker(x) for x in local_footnote)))
    math_scale=max(size,profile['body_size'])
    neighbors=[x for x in page['lines'] if x['text'].strip() and len(x['text'].strip())<=24 and x['bbox'][2]-x['bbox'][0]<w*.35 and
               max(0,x['bbox'][0]-bb[2],bb[0]-x['bbox'][2])<=math_scale*2.6 and max(0,x['bbox'][1]-bb[3],bb[1]-x['bbox'][3])<=math_scale*.65]
    math_neighbor_context=bool(len(text)<=24 and bb[2]-bb[0]<w*.35 and sum(formula_like(x) for x in neighbors)>=2)
    # Unknown embedded font names (e.g. CIDFont+F2) still carry useful contrast:
    # a short uniform block in a distinct font amid body prose can be a heading.
    local_font_heading=bool(len(block_text.strip())<150 and not any(terminal_sentence(x['text']) for x in peers) and
                            font not in profile['body_fonts'][:1] and size>=profile['body_size'] and size<profile['body_size']*1.3 and
                            not author_line_context and not affiliation_block_context and not caption_context)
    sidebar_rows=[x for x in page['lines'] if x['text'].strip() and abs(x['bbox'][0]-bb[0])<size*2.5 and
                  x['bbox'][2]-x['bbox'][0]<w*.32 and x['size']<profile['body_size']*.85]
    sidebar_metadata_context=bool(page['page']==1 and size<profile['body_size']*.85 and bb[2]-bb[0]<w*.32 and bb[1]>h*.4 and
                                  sum(bool(EXPLICIT_METADATA.search(x['text']) or COPYRIGHT_NOTICE.search(x['text'])) for x in sidebar_rows)>=3)
    # A caption bounds a graphic, not all preceding text in that column. Require
    # local graphic evidence or an isolated subfigure marker. In particular the
    # document's modal font size cannot decide whether a regular block is prose:
    # source pages and captions may use different body sizes.
    figure_captions=[x for x in page['lines'] if caption_anchor(x,page) and not re.match(r'^\s*table\b',x['text'],re.I) and
                     x['bbox'][1]>bb[3] and x['bbox'][0]-size*1.5<=(bb[0]+bb[2])/2<=x['bbox'][2]+size*1.5]
    source_figure_band=False
    # Control glyphs are excluded only from this cue test, never source text.
    cue_text=re.sub(r'[\x00-\x1f\ufffd]','',text).strip()
    subfigure_marker=bool(re.fullmatch(r'\([a-z]\)',cue_text))
    regular_prose_block=(sum(len(x['text'].strip())>35 for x in peers)>=3 and len(block_text)>180 and
                         sum(terminal_sentence(x['text']) for x in peers)>=1 and
                         not any(caption_anchor(x,page) for x in peers))
    sparse_label_block=(len(peers)>=5 and sum(len(x['text'].strip())<28 for x in peers)>=len(peers)*.8 and
                        not any(AFFILIATION_WORD.search(x['text']) or EXPLICIT_METADATA.search(x['text']) for x in peers))
    if figure_captions and (size<profile['body_size']*.96 or subfigure_marker) and len(text)<60 and not captioned_table_context and not caption_anchor(line,page) and not regular_prose_block and not front_matter_metadata_context:
        cap=min(figure_captions,key=lambda x:x['bbox'][1])
        narrative_between=any(len(x['text'].strip())>50 and x['size']>=size*.96 and
                              bb[3]<x['bbox'][1]<cap['bbox'][1] and x['bbox'][2]>bb[0] and x['bbox'][0]<bb[2] for x in page['lines'])
        graphics=page.get('graphic_regions',[])+[r['bbox'] for r in page.get('rejected_table_regions',[])]
        graphic_support=any(r[0]-size*2<=(bb[0]+bb[2])/2<=r[2]+size*2 and
                            r[1]-size*2<=(bb[1]+bb[3])/2<=min(r[3]+size*2,cap['bbox'][1])
                            for r in graphics)
        source_figure_band=(graphic_support or subfigure_marker or sparse_label_block) and not narrative_between and cap['bbox'][1]-bb[3]<h*(.85 if subfigure_marker else .6) and not (bb[1]<h*.09 and len(text)>15 and font in profile['body_fonts'][:1])
    filled_heading_context=bool((flags&16 or 'bold' in font) and size>=profile['body_size']*.95 and
        12<len(text)<150 and not terminal_sentence(text) and not METADATA.search(text) and not caption_anchor(line,page) and
        any(r[0]-.5<=bb[0] and bb[2]<=r[2]+.5 and r[1]-2<=bb[1] and bb[3]<=r[3]+2 and
            bb[2]-bb[0]>=(r[2]-r[0])*.35 for r in page.get('heading_regions',[])))
    inline_prose_math_context=bool(len(text)<=25 and any(
        x['id']!=line['id'] and len(x['text'].strip())>=17 and len(x['text'].split())>=3 and
        x['native_block']==line['native_block'] and x['size']>=profile['body_size']*.85 and
        abs(text_baseline(x)-text_baseline(line))<=profile['body_size']*.65 and
        max(0,x['bbox'][0]-bb[2],bb[0]-x['bbox'][2])<=profile['body_size']*2
        for x in peers) and max(len(x['text'].strip()) for x in peers)>=40)
    return [math.log(size/max(.1,profile['body_size'])),(bb[2]-bb[0])/w,(bb[3]-bb[1])/h,bb[0]/w,bb[1]/h,bb[2]/w,bb[3]/h,
            math.log1p(n)/6,sum(c.isdigit() for c in text)/n,sum(c.isupper() for c in text)/max(1,alpha),alpha/n,
            float(bool(flags&16) or 'bold' in font),float(bool(flags&2) or 'italic' in font),float(bool(flags&8) or 'cour' in font),
            float(bool(MATH_FONT.search(font))),min(1,small),min(1,math.log1p(len(line['spans']))/6),(bb[3]-bb[1])/size,
            float(caption_anchor(line,page)),float(bool(REFERENCE.search(text))),float(bool(METADATA.search(text))),
            min(1,len(re.findall(r'\b[A-Z]\.(?=\s|[A-Z.])',text))/3),float(list_marker(line,page)),
            min(1,math_count/n*5),float(bool(HEADING.search(text))),float(bool(re.search(r'[.!?。！？:]\s*$',text))),
            float(page['page']==1),float(font in profile['body_fonts']),size/max(.1,profile['max_size']),float('�' in text),
            float(caption_context),float(bool(REFERENCE.search(text)) or reference_context or dense_reference_context),max(-3,min(5,preceding)),max(-3,min(5,following)),
            float(n<12),line['direction'][0],line['direction'][1],pos/max(1,len(peers)-1),
            math.log1p(len(peers))/5,math.log1p(sum(len(x['text']) for x in peers)/max(1,len(peers)))/6,
            (union([x['bbox'] for x in peers])[3]-union([x['bbox'] for x in peers])[1])/h,
            (union([x['bbox'] for x in peers])[2]-union([x['bbox'] for x in peers])[0])/w,
            float(caption_context),
            float(furniture_key(line,page) in profile.get('repeated_furniture',[])),
            math.log(max(.1,peers[0]['size'])/max(.1,profile['body_size'])),
            float(bool(HEADING.search(peers[0]['text']))),
            float(bool(re.search(r'^(?:Received|Accepted|Published|DOI:|ISSN|ISBN|©|Copyright|Prof\.|Department|School|University)|https?://|www\.|@',peers[0]['text'],re.I))),
            float(any(t['bbox'][0]-.5<=(bb[0]+bb[2])/2<=t['bbox'][2]+.5 and t['bbox'][1]-.5<=(bb[1]+bb[3])/2<=t['bbox'][3]+.5 for t in page.get('table_regions',[])) or
                  any(r[0]-.5<=(bb[0]+bb[2])/2<=r[2]+.5 and r[1]-.5<=(bb[1]+bb[3])/2<=r[3]+.5 for r in page.get('structure_regions',[]))),
            profile.get('font_histogram',{}).get(font,0)/max(1,sum(profile.get('font_histogram',{}).values())),
            float(bool(profile['body_fonts']) and font==profile['body_fonts'][0]),
            float(any(k in font for k in ['sans','helvet','arial','proxima','gothic','calibri'])),
            float(any(re.search(r'@|\b(?:e-?mail|prof\.|department|school of|received:|accepted:)\b',x['text'],re.I) for x in peers)),
            min(1,sum(abs(text_baseline(x)-text_baseline(line))<size*.2 and x['id']!=line['id'] and x['native_block']!=line['native_block'] for x in page['lines'])/5),
            abs(math.log(size/max(.1,profile['body_size']))),
            float(page['page']==1 and bool(profile.get('title_band')) and profile['title_band'][0]-.5<=bb[1]<=profile['title_band'][1]+.5),
            float(bool(re.match(r'^(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+[A-Z]',text))),
            float(font_key(peers[0]['font'])!=font),
            math.log(max(x['size'] for x in peers)/max(.1,profile['body_size'])),
            sum(bool(REFERENCE.search(x['text'])) for x in peers)/max(1,len(peers)),
            min(1,sum(bool(REFERENCE.search(x['text'])) for x in peers)/5),
            float(bool(re.fullmatch(r'(?:https?://|www\.)\S+',text))),
            float(page['page']==1 and bool(profile.get('title_band')) and bb[1]>profile['title_band'][1] and bb[1]<profile['title_band'][1]+h*.18),
            float(page['page']==1 and bool(profile.get('title_band')) and bb[3]<profile['title_band'][0]),float(reference_context),float(section_heading_context),float(front_matter_metadata_context),float(running_header_context),float(explicit_metadata_label),
            float(author_line_context),float(affiliation_block_context),float(list_continuation_context),float(display_equation_context),float(explicit_heading_label),float(graphic_context),
            float(page_number_context),float(footnote_context),float(math_neighbor_context),float(local_font_heading),float(sidebar_metadata_context),float(source_figure_band),float(inline_prose_math_context),float(captioned_table_context),float(subcaption_context),float(filled_heading_context)]


def join_features(a,b,page,roles,column_transition=False):
    x=a['bbox']; y=b['bbox']; size=max(1,(a['size']+b['size'])/2); width=page['width']; ta=a['text'].strip();tb=b['text'].strip()
    overlap=max(0,min(x[2],y[2])-max(x[0],y[0]))/max(1,min(x[2]-x[0],y[2]-y[0]))
    ra,rb=roles
    ap=[line for line in page.get('lines',[a,b]) if line['native_block']==a['native_block'] and line['text'].strip()]
    bp=[line for line in page.get('lines',[a,b]) if line['native_block']==b['native_block'] and line['text'].strip()]
    apos=next((i for i,line in enumerate(ap) if line['id']==a['id']),0)/max(1,len(ap)-1)
    bpos=next((i for i,line in enumerate(bp) if line['id']==b['id']),0)/max(1,len(bp)-1)
    inset=(y[0]-min(line['bbox'][0] for line in bp))/size
    fill=(x[2]-x[0])/max(1,max(line['bbox'][2] for line in ap)-min(line['bbox'][0] for line in ap))
    # Across columns, raw negative page-height gaps and positive gutter deltas
    # are not physical line spacing. Canonicalize these local-spacing features;
    # keep the verified seam flag and separate page-position evidence below.
    gap,step,left,right=(y[1]-x[3])/size,(y[1]-x[1])/size,(y[0]-x[0])/size,(y[2]-x[2])/size
    if column_transition:gap,step,left,right,overlap=.2,1.2,0.,((y[2]-y[0])-(x[2]-x[0]))/size,1.
    return [gap,step,left,right,overlap,
            math.log(max(.1,b['size'])/max(.1,a['size'])),float(font_key(a['font'])==font_key(b['font'])),float(a['native_block']==b['native_block']),
            float(terminal_sentence(ta)),float(ta.endswith(('-','‐','\u00ad'))),float(tb[:1].islower()),float(tb[:1].isupper()),
            (x[2]-x[0])/width,(y[2]-y[0])/width,math.log1p(len(ta))/6,math.log1p(len(tb))/6,float(ra==rb),
            *[float(ra==r) for r in ROLES],float(rb=='caption' and caption_anchor(b,page)),float(bool(REFERENCE.search(tb))),
            float(bool(re.match(r'^\s*[•●▪■–-]\s',tb))),float(a['direction']==b['direction']),0. if column_transition else x[0]/width,0. if column_transition else y[0]/width,
            float(a['native_block']==b['native_block'] and any(u['id']==a['id'] and v['id']==b['id'] for u,v in zip(ap,ap[1:]))),float(column_transition),
            apos,bpos,0. if column_transition else inset,fill,float(list_marker(b,page)),
            float(terminal_sentence(ta) and inset>=.65),
            x[3]/page['height'] if column_transition else 0.,y[1]/page['height'] if column_transition else 0.,
            float(bool(re.match(r'^\s*(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+[A-Z]',tb))),
            float(ra==rb=='metadata' and bool(AFFILIATION_WORD.match(tb)) and not AFFILIATION_WORD.search(ta)),
            float(ta.count('[')>ta.count(']') and bool(re.fullmatch(r'[\d\s,;–—-]+\][.!?,;:]?',tb)))]


@lru_cache(maxsize=4)
def load_model(path=None):
    p=Path(path) if path else MODEL_PATH
    if not p.exists():
        return None
    model=json.loads(p.read_text())
    if model.get('role_features')!=ROLE_FEATURES or model.get('join_features')!=JOIN_FEATURES or model.get('roles')!=ROLES or model.get('feature_revision')!=FEATURE_REVISION:
        raise ValueError('Source structure model feature contract mismatch.')
    validate_head(model.get('role_head'),len(ROLE_FEATURES),len(ROLES))
    validate_head(model.get('join_head'),len(JOIN_FEATURES),2)
    if model.get('region_head'):
        import structure_regions as regions
        region=model['region_head']
        if region.get('revision')!=regions.REVISION or region.get('features')!=regions.FEATURES or region.get('classes')!=regions.CLASSES:
            raise ValueError('Source region model feature contract mismatch.')
        validate_head(region.get('network'),len(regions.FEATURES),len(regions.CLASSES))
        if not isinstance(region.get('threshold'),(int,float)) or not math.isfinite(region['threshold']) or not 0<=region['threshold']<=1:
            raise ValueError('Invalid source region threshold.')
    for key in ('role_threshold','join_threshold'):
        value=model.get(key)
        if not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:
            raise ValueError('Invalid structure threshold: '+key)
    return model


def validate_head(head,dimensions,classes):
    """Reject damaged parameters before inference can lose or hang on evidence."""
    def vector(value,n):
        return isinstance(value,list) and len(value)==n and all(isinstance(x,(int,float)) and math.isfinite(x) for x in value)
    def matrix(value,n,m):
        return isinstance(value,list) and len(value)==n and all(vector(row,m) for row in value)
    if not isinstance(head,dict):raise ValueError('Missing structure head.')
    if head.get('kind')=='extra-trees':
        trees=head.get('trees')
        if head.get('feature_count')!=dimensions or head.get('classes')!=classes or not isinstance(trees,list) or not trees:
            raise ValueError('Invalid structure forest dimensions.')
        for tree in trees:
            left=tree.get('left',[]);n=len(left)
            if not n or any(not isinstance(tree.get(k),list) or len(tree[k])!=n for k in ('right','feature','threshold','value')):
                raise ValueError('Invalid structure tree shape.')
            if not vector(tree['threshold'],n) or not matrix(tree['value'],n,classes):raise ValueError('Nonfinite tree parameters.')
            reached=set();stack=[0]
            while stack:
                node=stack.pop()
                if type(node) is not int or not 0<=node<n or node in reached:raise ValueError('Cyclic or invalid structure tree.')
                reached.add(node);l=left[node];r=tree['right'][node]
                if any(p<0 for p in tree['value'][node]) or abs(sum(tree['value'][node])-1)>1e-6:raise ValueError('Invalid tree probabilities.')
                if l==-1:
                    if r!=-1:raise ValueError('Invalid structure leaf.')
                else:
                    feature=tree['feature'][node]
                    if type(feature) is not int or not 0<=feature<dimensions:raise ValueError('Invalid tree feature.')
                    stack.extend([l,r])
            if len(reached)!=n:raise ValueError('Unreachable structure tree nodes.')
        return
    hidden=len(head.get('bias',[]))
    if not hidden or not vector(head.get('mean'),dimensions) or not vector(head.get('scale'),dimensions) or any(x<=0 for x in head['scale']) or not matrix(head.get('weights'),dimensions,hidden) or not vector(head.get('bias'),hidden) or not matrix(head.get('output'),hidden,classes) or not vector(head.get('output_bias'),classes):
        raise ValueError('Invalid structure network parameters or dimensions.')


def predict_python(head, rows):
    """Dependency-free inference, shared contract with vectorized inference."""
    if head.get('kind')=='extra-trees':
        return predict_forest(head,rows)
    result=[]
    for row in rows:
        if len(row)!=len(head['mean']) or not all(math.isfinite(x) for x in row):
            raise ValueError('Nonfinite or wrong-dimensional structure features.')
        normalized=[max(-12,min(12,(x-m)/s)) for x,m,s in zip(row,head['mean'],head['scale'])]
        hidden=[math.tanh(sum(x*w[j] for x,w in zip(normalized,head['weights']))+head['bias'][j]) for j in range(len(head['bias']))]
        logits=[sum(x*w[j] for x,w in zip(hidden,head['output']))+head['output_bias'][j] for j in range(len(head['output_bias']))]
        ex=[math.exp(x-max(logits)) for x in logits];total=sum(ex);result.append([x/total for x in ex])
    return result


def predict_many(head, rows):
    if not rows:
        return []
    if head.get('kind')=='extra-trees':
        return predict_forest(head,rows)
    try:
        import numpy as np
    except ImportError:
        return predict_python(head,rows)
    x=np.asarray(rows,dtype=float)
    if x.ndim!=2 or x.shape[1]!=len(head['mean']) or not np.isfinite(x).all():
        raise ValueError('Nonfinite or wrong-dimensional structure features.')
    x=np.clip((x-head['mean'])/head['scale'],-12,12)
    hidden=np.tanh(np.einsum('ni,ij->nj',x,np.asarray(head['weights']),optimize=False)+head['bias'])
    logits=np.einsum('ni,ij->nj',hidden,np.asarray(head['output']),optimize=False)+head['output_bias']
    ex=np.exp(logits-logits.max(axis=1,keepdims=True));return (ex/ex.sum(axis=1,keepdims=True)).tolist()


def role_decision(features, probabilities, threshold=.8, source_text=''):
    """Apply narrow structural rules after learned role scoring."""
    ranking=sorted(range(len(probabilities)),key=lambda i:probabilities[i],reverse=True)
    index=ranking[0];score=probabilities[index];margin=score-probabilities[ranking[1]]
    predicted=ROLES[index]
    damaged_text=bool(features[ROLE_FEATURES.index('bad_char')] or native_text_damaged(source_text))
    if damaged_text:
        math_like=(predicted=='equation' or
                   features[ROLE_FEATURES.index('display_equation_context')] or
                   features[ROLE_FEATURES.index('math_neighbor_context')])
        return {'predicted_role':predicted,'assigned_role':'body','score':score,'margin':margin,
                'review_required':True,
                'rule':'damaged-native-glyph-not-equation' if math_like else 'damaged-native-glyph-review'}
    if features[ROLE_FEATURES.index('repeated_furniture')] and features[ROLE_FEATURES.index('running_header_context')]:
        return {'predicted_role':predicted,'assigned_role':'metadata','score':score,'margin':margin,
                'review_required':False,'rule':'repeated-marginal-running-furniture'}
    if features[ROLE_FEATURES.index('filled_heading_context')]:
        return {'predicted_role':predicted,'assigned_role':'heading','score':score,'margin':margin,
                'review_required':False,'rule':'bold-source-heading-in-filled-panel-band'}
    if (features[ROLE_FEATURES.index('source_figure_band')] and features[ROLE_FEATURES.index('log_length')]<math.log1p(60)/6 and
            not any(features[ROLE_FEATURES.index(key)] for key in ('caption_start','explicit_caption_label','subfigure_caption_context','table_region','captioned_table_context'))):
        return {'predicted_role':predicted,'assigned_role':'label','score':score,'margin':margin,
                'review_required':False,'rule':'short-source-text-in-caption-bounded-graphic-band'}
    if (features[ROLE_FEATURES.index('title_band')] and features[ROLE_FEATURES.index('size_ratio')]>math.log(1.3) and
            features[ROLE_FEATURES.index('bold')] and features[ROLE_FEATURES.index('width')]>.35):
        return {'predicted_role':predicted,'assigned_role':'title','score':score,'margin':margin,
                'review_required':False,'rule':'large-bold-first-page-title-band'}
    if (predicted=='title' and features[ROLE_FEATURES.index('title_band')] and
            features[ROLE_FEATURES.index('size_ratio')]>=math.log(1.18) and
            features[ROLE_FEATURES.index('size_to_max')]>=.95 and
            features[ROLE_FEATURES.index('width')]>.45):
        return {'predicted_role':predicted,'assigned_role':'title','score':score,'margin':margin,
                'review_required':True,'rule':'learned-title-with-unknown-font-requires-review'}
    if features[ROLE_FEATURES.index('sidebar_metadata_context')]:
        return {'predicted_role':predicted,'assigned_role':'metadata','score':score,'margin':margin,
                'review_required':False,'rule':'small-ancillary-metadata-sidebar'}
    if features[ROLE_FEATURES.index('page_number_context')] or features[ROLE_FEATURES.index('footnote_context')]:
        return {'predicted_role':predicted,'assigned_role':'metadata','score':score,'margin':margin,
                'review_required':False,'rule':'page-number-or-small-source-footnote'}
    if features[ROLE_FEATURES.index('caption_start')] or features[ROLE_FEATURES.index('explicit_caption_label')] or features[ROLE_FEATURES.index('subfigure_caption_context')]:
        return {'predicted_role':predicted,'assigned_role':'caption','score':score,'margin':margin,
                'review_required':False,'rule':'explicit-caption-prefix-or-block-label'}
    if features[ROLE_FEATURES.index('captioned_table_context')]:
        return {'predicted_role':predicted,'assigned_role':'table','score':score,'margin':margin,
                'review_required':False,'rule':'table-caption-corroborated-grid-region'}
    if features[ROLE_FEATURES.index('explicit_heading_label')]:
        return {'predicted_role':predicted,'assigned_role':'heading','score':score,'margin':margin,
                'review_required':False,'rule':'explicit-heading-label'}
    if features[ROLE_FEATURES.index('reference_section_context')]:
        return {'predicted_role':predicted,'assigned_role':'reference','score':score,'margin':margin,
                'review_required':False,'rule':'reference-section-context'}
    if features[ROLE_FEATURES.index('section_heading_context')]:
        return {'predicted_role':predicted,'assigned_role':'heading','score':score,'margin':margin,
                'review_required':False,'rule':'numbered-section-heading-context'}
    if features[ROLE_FEATURES.index('inline_prose_math_context')] and not features[ROLE_FEATURES.index('table_region')]:
        return {'predicted_role':predicted,'assigned_role':'body','score':score,'margin':margin,
                'review_required':True,'rule':'inline-prose-math-retains-source-geometry'}
    if features[ROLE_FEATURES.index('table_region')]:
        return {'predicted_role':predicted,'assigned_role':'table','score':score,'margin':margin,
                'review_required':False,'rule':'source-table-cell-region'}
    # A high-confidence learned protected role can disambiguate a diagram label
    # containing '=' or a subfigure caption beginning '(a)'. Explicit source
    # caption/heading cues above still take precedence.
    if predicted in {'table','label','caption','reference'} and score>=.98 and margin>=.9:
        return {'predicted_role':predicted,'assigned_role':predicted,'score':score,'margin':margin,
                'review_required':False,'rule':'confident-learned-protected-role'}
    if features[ROLE_FEATURES.index('native_reference_context')] and features[ROLE_FEATURES.index('block_reference_density')]>=.08:
        return {'predicted_role':predicted,'assigned_role':'reference','score':score,'margin':margin,
                'review_required':False,'rule':'dense-source-reference-block'}
    if features[ROLE_FEATURES.index('list_start')] or features[ROLE_FEATURES.index('list_continuation_context')]:
        return {'predicted_role':predicted,'assigned_role':'list','score':score,'margin':margin,
                'review_required':False,'rule':'numbered-list-item-context'}
    if predicted=='list':
        return {'predicted_role':predicted,'assigned_role':'body','score':score,'margin':margin,
                'review_required':True,'rule':'reject-list-without-marker-or-continuation'}
    if features[ROLE_FEATURES.index('front_matter_metadata_context')]:
        return {'predicted_role':predicted,'assigned_role':'metadata','score':score,'margin':margin,
                'review_required':False,'rule':'title-to-abstract-front-matter-band'}
    if features[ROLE_FEATURES.index('before_title_band')] and features[ROLE_FEATURES.index('first_page')] and features[ROLE_FEATURES.index('top')]<.17 and features[ROLE_FEATURES.index('log_length')]<math.log1p(80)/6:
        return {'predicted_role':predicted,'assigned_role':'metadata','score':score,'margin':margin,
                'review_required':False,'rule':'first-page-eyebrow-before-title'}
    if features[ROLE_FEATURES.index('explicit_metadata_label')]:
        return {'predicted_role':predicted,'assigned_role':'metadata','score':score,'margin':margin,
                'review_required':False,'rule':'explicit-metadata-label'}
    if features[ROLE_FEATURES.index('author_line_context')]:
        return {'predicted_role':predicted,'assigned_role':'metadata','score':score,'margin':margin,
                'review_required':False,'rule':'front-matter-author-line'}
    if features[ROLE_FEATURES.index('affiliation_block_context')]:
        return {'predicted_role':predicted,'assigned_role':'metadata','score':score,'margin':margin,
                'review_required':False,'rule':'front-matter-affiliation-block'}
    if (not features[ROLE_FEATURES.index('first_page')] and features[ROLE_FEATURES.index('running_header_context')] and
            (features[ROLE_FEATURES.index('log_length')]>math.log1p(20)/6 or
             features[ROLE_FEATURES.index('size_ratio')]<math.log(.92) and features[ROLE_FEATURES.index('log_length')]>math.log1p(6)/6)):
        return {'predicted_role':predicted,'assigned_role':'metadata','score':score,'margin':margin,
                'review_required':False,'rule':'page-margin-running-furniture'}
    if features[ROLE_FEATURES.index('display_equation_context')] or features[ROLE_FEATURES.index('math_neighbor_context')]:
        return {'predicted_role':predicted,'assigned_role':'equation','score':score,'margin':margin,
                'review_required':False,'rule':'display-equation-font-and-layout'}
    if features[ROLE_FEATURES.index('graphic_context')]:
        return {'predicted_role':predicted,'assigned_role':'label','score':score,'margin':margin,
                'review_required':False,'rule':'short-text-inside-graphic-region'}
    accepted=score>=threshold and margin>=.2
    return {'predicted_role':predicted,'assigned_role':predicted if accepted else 'body','score':score,
            'margin':margin,'review_required':not accepted,'rule':None}


def predict_forest(head,rows):
    """Original portable traversal of learned tree arrays; no sklearn runtime."""
    classes=head['classes'];dimensions=head['feature_count'];trees=head['trees'];result=[]
    for row in rows:
        if len(row)!=dimensions or not all(math.isfinite(x) for x in row):
            raise ValueError('Nonfinite or wrong-dimensional structure features.')
        # Match the float32 input representation used during tree fitting.
        import struct
        values=[struct.unpack('f',struct.pack('f',x))[0] for x in row]
        probability=[0.]*classes
        for tree in trees:
            node=0
            while tree['left'][node]!=-1:
                node=tree['left'][node] if values[tree['feature'][node]]<=tree['threshold'][node] else tree['right'][node]
            for i,p in enumerate(tree['value'][node]):probability[i]+=p/len(trees)
        result.append(probability)
    return result


def order_regions(regions,width,mode='auto'):
    """Whitespace subdivision; geometry governs order, model never drops nodes."""
    if not regions:
        return []
    def gaps(items,axis):
        intervals=sorted((x['bbox'][axis],x['bbox'][axis+2]) for x in items)
        edge=intervals[0][1];out=[]
        for lo,hi in intervals[1:]:
            if lo>edge+.8:out.append((lo-edge,(lo+edge)/2))
            edge=max(edge,hi)
        return out
    def recurse(items,depth=0):
        if len(items)<2 or depth>30:
            return sorted(items,key=lambda x:(x['bbox'][1],x['bbox'][0]))
        if mode!='one':
            for gap,cut in sorted(gaps(items,0),reverse=True):
                left=[x for x in items if x['bbox'][2]<cut];right=[x for x in items if x['bbox'][0]>cut]
                # Dense proceedings can use a real gutter narrower than 6 pt.
                # Require multiple regions and a tall text envelope on BOTH sides;
                # a small gap between labels alone must not imply two columns.
                narrow_columns=(gap>=max(1,width*.002) and all(len(side)>=2 and
                    any(x['bbox'][3]-x['bbox'][1]>width*.10 for x in side) for side in [left,right]))
                if (gap>=max(6,width*.01) or narrow_columns) and left and right and all(union([x['bbox'] for x in side])[3]-union([x['bbox'] for x in side])[1]>25 for side in [left,right]):
                    return recurse(left,depth+1)+recurse(right,depth+1)
        horizontal=gaps(items,1)
        if horizontal:
            _,cut=max(horizontal);top=[x for x in items if x['bbox'][3]<cut];bottom=[x for x in items if x['bbox'][1]>cut]
            if top and bottom:return recurse(top,depth+1)+recurse(bottom,depth+1)
        return sorted(items,key=lambda x:(x['bbox'][1],x['bbox'][0]))
    return recurse(list(regions))


def join_gate(a,b,ra,rb,column_transition=False):
    x,y=a['bbox'],b['bbox'];size=max(1,(a['size']+b['size'])/2)
    if a['direction']!=b['direction'] or abs(a['direction'][1])>.05:return 'rotated-or-direction-change'
    if abs(math.log(max(.1,a['size'])/max(.1,b['size'])))>.18:return 'font-size-boundary'
    if ra!=rb:return 'role-boundary'
    if re.match(r'^\s*(?:Acknowledg(?:e)?ments?|References|Bibliography)\s*:',b['text'],re.I):return 'explicit-section-start'
    if ra=='metadata' and AFFILIATION_WORD.match(b['text'].strip()) and not AFFILIATION_WORD.search(a['text']):return 'author-to-affiliation-boundary'
    if ra=='heading' and re.match(r'^\s*(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+[A-Z]',b['text']):return 'new-numbered-heading'
    if ra in {'equation','label','table'}:return 'protected-structure'
    if column_transition:
        if ra not in {'body','reference'}:return 'column-transition-role-boundary'
    elif y[1]<x[1]+size*.35 or y[1]-x[3]>size*1.35:return 'non-adjacent-baselines'
    overlap=max(0,min(x[2],y[2])-max(x[0],y[0]))/max(1,min(x[2]-x[0],y[2]-y[0]))
    centered=(ra in {'title','heading','metadata'} or ra=='caption' and a['native_block']==b['native_block']) and abs((x[0]+x[2]-y[0]-y[2])/2)<size*2
    # A float or shaped paragraph can shift the left edge while its right edge
    # remains aligned. This admits a candidate; the learned head still decides.
    edge_aligned=ra in {'body','metadata','caption','reference','list'} and abs(x[2]-y[2])<size*.5 and a['native_block']==b['native_block']
    if not column_transition and (overlap<.6 or (abs(y[0]-x[0])>size*2.8 and not centered and not edge_aligned)):return 'column-or-indent-boundary'
    if (ra=='reference' and REFERENCE.search(b['text'])) or (rb=='caption' and caption_start(b['text'])):return 'new-numbered-item'
    if ra=='list' and LIST_START.match(b['text']) and not REFERENCE.match(b['text']) and not re.search(r'\b(?:fig(?:ure)?s?|tables?|eq(?:uation)?s?|no)\.\s*$',a['text'],re.I):return 'new-list-item'
    if not column_transition and ra=='body' and terminal_sentence(a['text']) and y[0]-x[0]>=size*.65:return 'paragraph-indent-after-terminal'
    return None


def cjk(char):
    return bool(char) and ('\u2e80'<=char<='\u9fff' or '\u3040'<=char<='\u30ff' or '\uac00'<=char<='\ud7a3')


def typography_text(line):
    """Serialize measured small raised/lowered numeric runs, retaining raw spans."""
    spans=line.get('spans',[])
    if not spans or ''.join(s.get('text','') for s in spans)!=line['text']:return line['text'],[]
    base=text_baseline(line);size=max(.1,line['size']);out=[];operations=[]
    supers=str.maketrans('0123456789+-=()','⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾');subs=str.maketrans('0123456789+-=()','₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎')
    for span in spans:
        text=span.get('text','');shift=span.get('origin',[0,base])[1]-base
        if span.get('size',size)<size*.83 and abs(shift)>size*.18 and text.strip() and all(c in '0123456789+-=() ' for c in text):
            converted=text.translate(supers if shift<0 else subs)
            operations.append({'operation':'serialize-measured-numeric-script','line_id':line['id'],'before':text,'after':converted,'font':span.get('font'),'baseline_shift_pt':shift,'font_size_pt':span.get('size')});text=converted
        # Adobe Symbol encoding maps code 0xB4 to multiply. Only this
        # explicitly named font is decoded; ordinary accents remain unchanged.
        if re.sub(r'^[A-Z]{6}\+','',span.get('font','')) in {'Symbol','SymbolMT'} and '´' in text:
            converted=text.replace('´','×');operations.append({'operation':'decode-adobe-symbol-multiply','line_id':line['id'],'before':text,'after':converted,'font':span['font']});text=converted
        out.append(text)
    return ''.join(out),operations


def compose(lines,lexicon):
    result='';operations=[]
    for index,line in enumerate(lines):
        raw,typography_operations=typography_text(line);operations.extend(typography_operations);text=raw.strip()
        if not suspect_native_encoding(text):text=text.translate(LIGATURES)
        if text!=raw:operations.append({'line_id':line['id'],'operation':'trim-edge-space-and-expand-print-ligatures','before':raw,'after':text})
        if not result:result=text;continue
        prev=lines[index-1];separator=' '
        if result.endswith('\u00ad'):
            result=result[:-1];separator='';operations.append({'line_id':prev['id'],'next_line_id':line['id'],'operation':'remove-explicit-soft-hyphen'})
        elif result.endswith(('-','‐')) and text[:1].islower():
            left=re.search(r'([^\W\d_]+)[-‐]$',result);right=re.match(r'([^\W\d_]+)',text)
            word=(left[1]+right[1]) if left and right else ''
            separator=''
            if word and word.casefold() in lexicon:
                result=result[:-1];operations.append({'line_id':prev['id'],'next_line_id':line['id'],'operation':'dehyphenate-with-unbroken-same-document-witness','witness':word})
            else:operations.append({'line_id':prev['id'],'next_line_id':line['id'],'operation':'retain-ambiguous-print-hyphen','review_candidate':word})
        elif result and text and cjk(result[-1]) and cjk(text[0]):separator=''
        operations.append({'line_id':prev['id'],'next_line_id':line['id'],'operation':'replace-physical-line-boundary','separator':separator})
        result+=separator+text
    return result,operations


def column_transition_pairs(lines,width,height,roles=None):
    """Candidate last-line -> first-line links across a verified column gutter."""
    narrow=[x for x in lines if (roles is None or roles.get(x['id']) in {'body','reference'}) and x['bbox'][2]-x['bbox'][0]<width*.48 and
            height*.06<x['bbox'][1] and x['bbox'][3]<height*.95 and len(x['text'].strip())>=3]
    if len(narrow)<2:return []
    tolerance=max(18,width*.035);clusters=[]
    for line in sorted(narrow,key=lambda x:x['bbox'][0]):
        if not clusters or line['bbox'][0]-clusters[-1][-1]['bbox'][0]>tolerance:
            clusters.append([line])
        else:
            clusters[-1].append(line)
    minimum=max(2,math.ceil(len(narrow)*.05)) if len(narrow)>=8 else 1
    columns_x=[cluster for cluster in clusters if len(cluster)>=minimum]
    if len(columns_x)<2:return []
    columns_x=sorted(sorted(columns_x,key=len,reverse=True)[:3],key=lambda c:statistics.median(x['bbox'][0] for x in c))
    cuts=[]
    for left,right in zip(columns_x,columns_x[1:]):
        cuts.append((max(x['bbox'][0] for x in left)+min(x['bbox'][0] for x in right))/2)
    centers=[statistics.median(x['bbox'][0] for x in cluster) for cluster in columns_x]
    columns=[[] for _ in range(len(cuts)+1)]
    for line in narrow:
        column=min(range(len(centers)),key=lambda i:abs(line['bbox'][0]-centers[i]))
        if abs(line['bbox'][0]-centers[column])<=max(tolerance*2,width*.07):
            columns[column].append(line)
    columns=[sorted(c,key=lambda x:(x['bbox'][1],x['bbox'][0])) for c in columns if c]
    result=[]
    for left,right in zip(columns,columns[1:]):
        prior=max(left,key=lambda x:x['bbox'][3]);following=min(right,key=lambda x:x['bbox'][1])
        if prior['bbox'][3]>=height*.48 and following['bbox'][1]<prior['bbox'][1]-max(1,prior['size'])*1.5 and prior['id']!=following['id']:
            result.append((prior,following))
    return result


def candidate_pairs(lines,width=None,height=None,roles=None):
    """Local vertical neighbors plus same-native-block pairs, before page order.

    Ordering all individual lines first interleaves columns when an abstract or
    figure spans a gutter. Group locally, then order complete text regions.
    """
    seen=set();pairs=[]
    by_block={}
    for line in lines:by_block.setdefault(line['native_block'],[]).append(line)
    for group in by_block.values():
        for a,b in zip(group,group[1:]):
            key=(a['id'],b['id'])
            if key not in seen:pairs.append((a,b));seen.add(key)
    for a in lines:
        size=max(1,a['size']);x=a['bbox'];neighbors=[]
        for b in lines:
            y=b['bbox']
            if b is a or not .35*size<y[1]-x[1]<3*size:continue
            overlap=max(0,min(x[2],y[2])-max(x[0],y[0]))/max(1,min(x[2]-x[0],y[2]-y[0]))
            centered=bool(roles and roles.get(a['id'])==roles.get(b['id']) and
                          roles.get(a['id']) in {'title','heading','metadata'} and
                          abs((x[0]+x[2]-y[0]-y[2])/2)<size*2)
            if overlap>=.6 and (abs(x[0]-y[0])<2.8*size or centered):neighbors.append(b)
        for b in sorted(neighbors,key=lambda b:(b['bbox'][1]-x[1],abs(b['bbox'][0]-x[0])))[:2]:
            key=(a['id'],b['id'])
            if key not in seen:pairs.append((a,b));seen.add(key)
    if width and height:
        for a,b in column_transition_pairs(lines,width,height,roles=roles):
            key=(a['id'],b['id'])
            if key not in seen:pairs.append((a,b));seen.add(key)
    return pairs


def reconstruct(page,profile,excluded=None,order='auto',model_path=None):
    model=load_model(model_path);lines=page['lines'];excluded=dict(excluded or {})
    excluded.update({x['id']:'native-whitespace-only' for x in lines if not x['text'].strip()})
    eligible=[x for x in lines if x['id'] not in excluded]
    features=[role_features(x,page,profile) for x in eligible]
    probabilities=predict_many(model['role_head'],features) if model else [[1]+[0]*(len(ROLES)-1) for _ in eligible]
    rolemap={};decisions=[];issues=[]
    for line,features_row,probs in zip(eligible,features,probabilities):
        decision=role_decision(features_row,probs,model.get('role_threshold',.8) if model else 1.1,line['text'])
        score=decision['score'];margin=decision['margin'];predicted=decision['predicted_role'];role=decision['assigned_role'];accepted=not decision['review_required']
        if abs(line['direction'][1])>.05 and role not in {'metadata','label'} and decision['rule'] is None:accepted=False;role='label'
        rolemap[line['id']]=role
        record={'line_id':line['id'],'predicted_role':predicted,'assigned_role':role,'score':round(score,6),'margin':round(margin,6),'review_required':not accepted}
        if decision['rule']:record['rule']=decision['rule']
        decisions.append(record)
        if not accepted:issues.append({'code':'structure-role-review','line_ids':[line['id']],'message':'Uncertain native-line role; preserved with provisional presentation, not certified.'})
    regions=[];region_context={};region_relations=[]
    if model and model.get('region_head'):
        import structure_regions as region_model
        decision_map={r['line_id']:r for r in decisions}
        region_context,_=region_model.refine(eligible,page,profile,decision_map,model['region_head'],predict_many)
        rolemap={lid:row['assigned_role'] for lid,row in decision_map.items()}
    # Rule-based role confidence must never hide a damaged native text mapping.
    # Preserve the glyph unchanged, but require source inspection before merging.
    decision_map={r['line_id']:r for r in decisions}
    for line in eligible:
        if native_text_damaged(line['text']):
            decision_map[line['id']]['review_required']=True
            decision_map[line['id']]['content_integrity']='unresolved-native-glyph'
            issues.append({'code':'structure-native-glyph-review','line_ids':[line['id']],
                           'message':'Native control/replacement glyph retained; role confidence does not verify its meaning.'})
    # Native objects may mix a bold heading with a complete body paragraph.
    # Keep that visual boundary even when their font size is identical.
    for line in eligible:
        if rolemap[line['id']]=='body' and line.get('flags',0)&16 and len(line['text'])<120 and not terminal_sentence(line['text']):
            following=[x for x in eligible if x['native_block']==line['native_block'] and 0<text_baseline(x)-text_baseline(line)<line['size']*1.8 and not x.get('flags',0)&16]
            if following:decision_map[line['id']].update(assigned_role='heading',semantic_role='heading',rule='measured-bold-heading-before-normal-prose')
        if re.match(r'^\s*(?:References|Bibliography)\s*:',line['text'],re.I):
            decision_map[line['id']].update(assigned_role='reference',semantic_role='reference',review_required=False,rule='explicit-inline-reference-heading')
    if model and model.get('region_head'):
        import figure_learning
        figure_learning.refine(page,profile,decisions)
        rolemap={r['line_id']:r['assigned_role'] for r in decisions}
        regions=region_model.structured_groups(eligible,decision_map,region_context)
        regions.extend(figure_learning.caption_groups(page,decisions) if figure_learning.load_model() else [])
        region_relations=region_model.note_anchors(regions,eligible)
    # Bibliographic entries are literal source paragraphs. Native serialisation
    # can split every journal/italic run into another block; a measured hanging
    # entry chain must not be translated as dozens of independent fragments.
    refs=[x for x in eligible if rolemap[x['id']]=='reference' and not REFERENCES_HEADING.fullmatch(x['text'].strip())]
    ref_groups=[]
    for row in sorted(refs,key=lambda x:(x['bbox'][1],x['bbox'][0])):
        choices=[]
        if not REFERENCE.match(row['text']):
            for group in ref_groups:
                prior=group[-1];size=max(1,row['size']);step=text_baseline(row)-text_baseline(prior)
                if (row['native_block']==prior['native_block'] and .35*size<=step<=1.8*size and
                    abs(math.log(max(.1,prior['size'])/size))<.1 and
                    abs(row['bbox'][0]-prior['bbox'][0])<size*3.5):choices.append(group)
        if choices:max(choices,key=lambda g:text_baseline(g[-1])).append(row)
        else:ref_groups.append([row])
    for group in ref_groups:
        if len(group)>1:regions.append({'id':'reference-'+group[0]['id'],'kind':'reference',
            'representation':'source-bibliography','bbox':union([x['bbox'] for x in group]),'members':group})
    import structure_regions as source_regions
    overlap_relations=source_regions.overlapping_layers(eligible)
    region_relations.extend(overlap_relations)
    for relation in overlap_relations:
        affected=[relation['native_line_id']]+relation['alternative_line_ids']
        for lid in affected:
            decision_map[lid]['review_required']=True
            decision_map[lid]['content_integrity']='competing-source-text-layers'
        issues.append({'code':'structure-competing-text-layers','line_ids':affected,
                       'message':'Damaged native mapping overlaps an alternative text layer. Inspect both against the source; no layer is silently accepted or discarded.'})
    structured_ids={row['id'] for region in regions for row in region['members']}
    review_ids={x['line_id'] for x in decisions if x['review_required']}
    transitions={(a['id'],b['id']) for a,b in column_transition_pairs(eligible,page['width'],page['height'],roles=rolemap)}
    pairs=candidate_pairs(eligible,page['width'],page['height'],roles=rolemap);pair_features=[join_features(a,b,page,(rolemap[a['id']],rolemap[b['id']]),(a['id'],b['id']) in transitions) for a,b in pairs]
    joins=predict_many(model['join_head'],pair_features) if model else [[1,0] for _ in pairs]
    candidates=[];relations=[]
    for (a,b),prob in zip(pairs,joins):
        transition=(a['id'],b['id']) in transitions
        gate=join_gate(a,b,rolemap[a['id']],rolemap[b['id']],transition);score=prob[1]
        uncertain_title_chain=(rolemap[a['id']]==rolemap[b['id']]=='title' and
            (a['native_block']==b['native_block'] or
             len(profile.get('title_band') or [])==2 and
             all(profile['title_band'][0]-.5<=row['bbox'][1] and row['bbox'][3]<=profile['title_band'][1]+.5 for row in [a,b]) and
             font_key(a['font'])==font_key(b['font'])) and
            all(decision['predicted_role']=='title' and
                (not decision['review_required'] or decision.get('rule')=='learned-title-with-unknown-font-requires-review')
                for decision in decisions if decision['line_id'] in {a['id'],b['id']}))
        if (rolemap[a['id']]==rolemap[b['id']]=='metadata' and
                furniture_key(a,page) in profile.get('repeated_furniture',[]) and
                furniture_key(b,page) in profile.get('repeated_furniture',[]) and
                font_key(a['font'])!=font_key(b['font'])):gate='running-furniture-typographic-boundary'
        if a['id'] in structured_ids or b['id'] in structured_ids:gate='spatial-or-literal-region-boundary'
        elif (a['id'] in review_ids or b['id'] in review_ids) and not uncertain_title_chain:gate='uncertain-role-requires-review'
        record={'from':a['id'],'to':b['id'],'join_score':round(score,6),'joined':False,'gate':gate};relations.append(record)
        if gate is None and model and score>=model.get('join_threshold',.94):candidates.append((score,a,b,record))
    # A path cover enforces at most one predecessor/successor and prevents cycles.
    successors={};predecessors={};lookup={x['id']:x for x in eligible}
    for score,a,b,record in sorted(candidates,key=lambda x:-x[0]):
        if a['id'] in successors or b['id'] in predecessors:continue
        # Do not skip a physically intervening line in the same aligned column.
        between=[x for x in eligible if a['bbox'][1]+.5<x['bbox'][1]<b['bbox'][1]-.5 and abs(x['bbox'][0]-a['bbox'][0])<a['size']*1.2 and x['bbox'][2]>a['bbox'][0]+a['size']*2]
        if between:record['gate']='intervening-physical-line';continue
        successors[a['id']]=b['id'];predecessors[b['id']]=a['id'];record['joined']=True
    groups=[]
    for line in eligible:
        if line['id'] in structured_ids:continue
        if line['id'] in predecessors:continue
        group=[line]
        while group[-1]['id'] in successors:group.append(lookup[successors[group[-1]['id']]])
        # Cross-column union boxes bridge the gutter and defeat XY-cut. Use
        # the first source column for ordering; preserve the full source box.
        head=[]
        for member in group:
            if head and (head[-1]['id'],member['id']) in transitions:break
            head.append(member)
        groups.append({'bbox':union([x['bbox'] for x in head]),'source_bbox':union([x['bbox'] for x in group]),'members':group})
    for region in regions:
        groups.append({'bbox':region['bbox'],'source_bbox':region['bbox'],'members':region['members'],
                       'semantic_role':region['kind'],'region_id':region['id'],'representation':region['representation']})
    narrative=[r for r in groups if rolemap[r['members'][0]['id']]=='body' and len(' '.join(x['text'] for x in r['members']))>100]
    narrative_box=union([r['bbox'] for r in narrative]) if narrative else None
    peripheral=[r for r in groups if r.get('semantic_role')=='footnote' or all(rolemap[x['id']]=='metadata' for x in r['members']) and
                (r['bbox'][1]>page['height']*.8 or any(abs(x['direction'][1])>.05 for x in r['members']) or
                 (narrative_box and r['bbox'][2]-r['bbox'][0]<page['width']*.32 and
                  (r['bbox'][2]<narrative_box[0]-2 or r['bbox'][0]>narrative_box[2]+2)))]
    groups=order_regions([r for r in groups if r not in peripheral],page['width'],order)+order_regions([r for r in peripheral if all(abs(x['direction'][1])<=.05 for x in r['members'])],page['width'],order)+[r for r in peripheral if any(abs(x['direction'][1])>.05 for x in r['members'])]
    lexicon=set(profile['native_words']);blocks=[];review_ids={x['line_id'] for x in decisions if x['review_required']}
    for region in groups:
        group=region['members'];role=rolemap[group[0]['id']]
        semantic=region.get('semantic_role') or decision_map[group[0]['id']].get('semantic_role')
        if semantic in {'code','equation'}:
            text='\n'.join(x['text'] for x in group)
            operations=[{'operation':'retain-source-line-and-spatial-boundaries','representation':region.get('representation'),'line_ids':[x['id'] for x in group]}]
        else:text,operations=compose(group,lexicon)
        if not text:
            excluded.update({x['id']:'native-whitespace-only' for x in group});continue
        ambiguities=[x for x in operations if x['operation']=='retain-ambiguous-print-hyphen']
        if ambiguities:issues.append({'code':'structure-hyphen-review','line_ids':[x['id'] for x in group],'message':'Printed line-end hyphen retained; source word requires inspection.','candidates':ambiguities})
        typography={'fonts':sorted({sp['font'] for x in group for sp in x['spans']}),'sizes_pt':sorted({round(sp['size'],4) for x in group for sp in x['spans']}),'dominant_size_pt':median([x['size'] for x in group]),'bold':any(x['flags']&16 for x in group)}
        block={'type':'heading' if role in {'title','heading'} else 'paragraph','role':role,'level':1 if role=='title' else 2,'text':text,'bbox':region['source_bbox'],'line_ids':[x['id'] for x in group],'native_line_ids':[lid for x in group for lid in x.get('native_line_ids',[x['id']])],'operations':operations,'typography':typography,'review_required':bool(review_ids.intersection(x['id'] for x in group)) or bool(ambiguities)}
        if semantic:block['semantic_role']=semantic
        if region.get('region_id'):block['region_id']=region['region_id']
        if semantic in {'code','equation'}:
            block['representation']=region.get('representation')
            block['source_lines']=[{'id':x['id'],'text':x['text'],'bbox':x['bbox'],'spans':x['spans']} for x in group]
            block['text_is_spatial_transcript']=semantic=='equation'
        blocks.append(block)
    assignments=[x for b in blocks for x in b['line_ids']]+list(excluded);expected=[x['id'] for x in lines]
    coverage={'physical_rows':len(expected),'assigned_rows':len(assignments),'missing':sorted(set(expected)-set(assignments)),'duplicates':[x for x,n in Counter(assignments).items() if n>1],'unexpected':sorted(set(assignments)-set(expected)),'excluded':excluded}
    native_expected=[x['id'] for x in page.get('native_lines',lines)];native_assigned=[lid for x in lines for lid in x.get('native_line_ids',[x['id']])]
    coverage['native_lines']=len(native_expected);coverage['native_missing']=sorted(set(native_expected)-set(native_assigned));coverage['native_duplicates']=[x for x,n in Counter(native_assigned).items() if n>1]
    coverage['native_unexpected']=sorted(set(native_assigned)-set(native_expected))
    coverage['pass']=not any(coverage[k] for k in ['missing','duplicates','unexpected','native_missing','native_duplicates','native_unexpected'])
    if not coverage['pass']:raise ValueError('Structure reconstruction lost or duplicated native lines.')
    return {'version':'1.0.2','model':model['id'] if model else None,'raw_sha256':page['raw_sha256'],'blocks':blocks,'line_roles':decisions,'relations':relations,'region_relations':region_relations,'coverage':coverage,'issues':issues,'review_status':'unreviewed; native-line coverage is not OCR, semantic, reading-order or visual proof'}
