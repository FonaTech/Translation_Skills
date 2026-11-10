"""Exact glyph evidence for missing PDF Unicode maps; no generated words.

Font files are read from the source or local system and never redistributed.
Unresolved glyphs remain source evidence. Copyright 2026 Yufeng Zhan. MIT.
"""
from collections import defaultdict
from functools import lru_cache
import io
import hashlib
import os
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET

REVISION='1.0.3-glyph-evidence-10-origin-serialization'
BAD = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffd]')

def key(name):
    return re.sub(r'[^a-z0-9]','',re.sub(r'^[A-Z]{6}\+','',name).casefold().replace('psmt','').replace('ps-','').replace('mt',''))

def signature(font,name):
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    glyphs=font.getGlyphSet();pen=DecomposingRecordingPen(glyphs);glyphs[name].draw(pen)
    em=font['head'].unitsPerEm
    return (tuple((op,tuple(None if p is None else tuple(round(v/em,8) for v in p) for p in points)) for op,points in pen.value),round(glyphs[name].width/em,8))

def font_files():
    roots=[Path('/System/Library/Fonts'),Path('/System/Library/Fonts/Supplemental'),Path('/Library/Fonts'),
           Path.home()/'Library/Fonts',Path('/usr/share/fonts'),Path('/usr/local/share/fonts'),
           Path.home()/'.local/share/fonts',Path(os.getenv('WINDIR','C:/Windows'))/'Fonts']
    explicit=[Path(p).expanduser() for p in os.getenv('DOCUMENT_REFERENCE_FONTS','').split(os.pathsep) if p]
    return explicit+[p for root in roots if root.is_dir() for p in root.rglob('*') if p.suffix.lower() in {'.ttf','.otf'}]

def cmap_index(face):
    from fontTools.agl import toUnicode
    index=defaultdict(set);by_name=defaultdict(set)
    for cp,name in (face.getBestCmap() or {}).items():
        if unicodedata.category(chr(cp)) not in {'Cc','Co','Cf'}:by_name[name].add(cp)
    for name,cps in by_name.items():
        # Canonical glyph names disambiguate cmap aliases using font metadata.
        # No language, script or ASCII preference is inferred from the prose.
        canonical=toUnicode(name)
        choices={ord(canonical)} if len(canonical)==1 and (ord(canonical) in cps or any(unicodedata.normalize('NFKC',canonical)==unicodedata.normalize('NFKC',chr(cp)) for cp in cps)) else cps
        try:index[signature(face,name)].update(choices)
        except Exception:continue
    by_gid={}
    for name,cps in by_name.items():
        canonical=toUnicode(name)
        choices={ord(canonical)} if len(canonical)==1 and (ord(canonical) in cps or any(unicodedata.normalize('NFKC',canonical)==unicodedata.normalize('NFKC',chr(cp)) for cp in cps)) else cps
        try:by_gid[face.getGlyphID(name)]=(signature(face,name),choices)
        except Exception:continue
    return dict(index),by_gid

@lru_cache(maxsize=24)
def reference_index(path,mtime,size):
    from fontTools.ttLib import TTFont
    with TTFont(path) as face:return cmap_index(face)

@lru_cache(maxsize=8)
def document_maps(path,mtime,size):
    import fitz
    from fontTools.ttLib import TTFont
    maps={};evidence=[]
    with fitz.open(path) as pdf:
        fonts={f[0]:f for page in pdf for f in page.get_fonts(full=True)}
        embedded=[];embedded_data=[]
        for xref,f in fonts.items():
            try:
                data=pdf.extract_font(xref)[3]
                face=TTFont(io.BytesIO(data));cmap=face.getBestCmap() or {}
                if cmap:
                    embedded.append((key(f[3]),cmap_index(face)))
                    embedded_data.append((key(f[3]),data))
                    face.close()
                else:face.close()
            except Exception:continue
        local=font_files()
        for xref,f in fonts.items():
            if f[2]!='Type0' or pdf.xref_get_key(xref,'Encoding')!=('name','/Identity-H') or pdf.xref_get_key(xref,'ToUnicode')[0]!='null':continue
            maps[xref]={}
            descendants=re.findall(r'(\d+)\s+0\s+R',pdf.xref_get_key(xref,'DescendantFonts')[1])
            if len(descendants)!=1:continue
            child=int(descendants[0])
            if pdf.xref_get_key(child,'Subtype')==('name','/CIDFontType0'):
                try:
                    if __package__:
                        from .cff_font_recovery import recover
                    else:
                        from cff_font_recovery import recover
                    mapping,proof=recover(pdf.extract_font(xref)[3],embedded_data,local,key)
                except Exception:
                    # Unsupported CFF programs or missing optional font/image
                    # libraries retain native glyph evidence, never guessed text.
                    continue
                if mapping:
                    maps[xref]=mapping
                    evidence.append({'font_xref':xref,'font':f[3],
                        'mapped_glyphs':len(mapping),**proof})
                continue
            if pdf.xref_get_key(child,'Subtype')!=('name','/CIDFontType2') or pdf.xref_get_key(child,'CIDToGIDMap') not in {('name','/Identity'),('null','null')}:continue
            try:face=TTFont(io.BytesIO(pdf.extract_font(xref)[3]))
            except Exception:continue
            index=defaultdict(set);gid_index=defaultdict(list)
            family=key(f[3]);aliases={family}
            if 'name' in face:
                for item in face['name'].names:
                    if item.nameID in {1,4,6}:
                        try:aliases.add(key(item.toUnicode()))
                        except UnicodeError:pass
            for name,reference in embedded:
                if name in aliases:
                    by_shape,by_gid=reference
                    for sig,cps in by_shape.items():index[sig].update(cps)
                    for gid,item in by_gid.items():gid_index[gid].append(item)
            for file in local:
                candidate=key(file.stem)
                if candidate not in aliases:continue
                try:
                    stat=file.stat()
                    by_shape,by_gid=reference_index(str(file),stat.st_mtime_ns,stat.st_size)
                    for sig,cps in by_shape.items():index[sig].update(cps)
                    for gid,item in by_gid.items():gid_index[gid].append(item)
                except Exception:continue
            mapping={}
            for gid,name in enumerate(face.getGlyphOrder()):
                try:sig=signature(face,name);cps=index.get(sig,set())
                except Exception:continue
                # Retained source GID, family and exact outline jointly resolve
                # homoglyph aliases without assuming a language or inventing text.
                at_gid=set().union(*(values for outline,values in gid_index.get(gid,[]) if outline==sig))
                if len(at_gid)==1:cps=at_gid
                # Remaining ambiguities stay unresolved.
                if len(cps)==1 and (sig[0] or next(iter(cps))==32):mapping[gid]=chr(next(iter(cps)))
            face.close()
            maps[xref]=mapping
            if mapping:
                evidence.append({'font_xref':xref,'font':f[3],'mapped_glyphs':len(mapping),'method':'exact-outline-and-advance-with-canonical-font-metadata'})
    return maps,evidence

def _recover_cid_lines(page,lines):
    """Replace only mapped glyphs at matching measured trace positions."""
    path=Path(page.parent.name or '')
    if not path.is_file():return []
    # Avoid font analysis on normal PDFs, even when math uses control glyphs.
    if not any(f[2]=='Type0' and page.parent.xref_get_key(f[0],'ToUnicode')[0]=='null' for f in page.get_fonts(full=True)):return []
    stat=path.stat();maps,evidence=document_maps(str(path.resolve()),stat.st_mtime_ns,stat.st_size)
    if not maps:return []
    # Match exact trace names on this page, keeping Unicode-bearing fonts out.
    # Family aliases may be used for reference selection, never font identity.
    def identity(name):return re.sub(r'^[A-Z]{6}\+','',name).casefold().replace(' ','')
    page_maps=defaultdict(list);valid_fonts=set()
    trace_names={item['font_xref']:item.get('trace_font_names',[]) for item in evidence}
    for font in page.get_fonts(full=True):
        alias=identity(font[3])
        if font[0] in maps:
            for name in {alias,*[identity(n) for n in trace_names.get(font[0],[])]}:
                page_maps[name].append(maps[font[0]])
        elif page.parent.xref_get_key(font[0],'ToUnicode')[0]!='null':valid_fonts.add(alias)
    positions={}
    native_positions=set()
    for trace in page.get_texttrace():
        family=identity(trace['font'])
        if family not in page_maps or family in valid_fonts:continue
        for codepoint,gid,origin,_ in trace['chars']:
            position=(family,round(origin[0],2),round(origin[1],2))
            # A simple WinAnsi font and a missing-map CID font can share a
            # trace family name. An actual Unicode-bearing trace at this exact
            # position takes precedence over family-level recovery proposals.
            # Never turn readable native letters into unknown-glyph artwork.
            if (0<=codepoint<=0x10ffff and codepoint!=0xfffd and
                unicodedata.category(chr(codepoint)) not in {'Cc','Co','Cs'}):
                native_positions.add(position)
                continue
            for mapping in page_maps[family]:positions.setdefault(position,set()).add(mapping.get(gid))
    for position in native_positions:positions.pop(position,None)
    count=0;unresolved=0;confirmed=0
    for line in lines:
        for span in line['spans']:
            for char in span.get('chars',[]):
                xy=char.get('origin',[])
                choices=positions.get((identity(span.get('font','')),round(xy[0],2),round(xy[1],2))) if len(xy)==2 else None
                value=next(iter(choices)) if choices and len(choices)==1 else None
                if choices and value is None and char['c'].strip():
                    char['unicode_unresolved']=True;unresolved+=1
                if value is not None:
                    confirmed+=1;char['unicode_recovered']=True
                    char.pop('unicode_unresolved',None)
                if value is not None and value!=char['c']:
                    char['native_c']=char['c'];char['c']=value;count+=1
            span['text']=''.join(c['c'] for c in span.get('chars',[]))
        line['unicode_unresolved']=any(c.get('unicode_unresolved') for s in line['spans'] for c in s.get('chars',[]))
        if any('native_c' in c for s in line['spans'] for c in s.get('chars',[])):
            line['unrecovered_native_text']=line['text'];line['text']=''.join(s['text'] for s in line['spans'])
            line['glyph_recovery']=REVISION
    return [{'revision':REVISION,'characters_recovered':count,'characters_supported':confirmed,'fonts':evidence,'unresolved_characters':unresolved,'source_bytes_unchanged':True,'semantic_certification':False}] if count or unresolved or confirmed else []


@lru_cache(maxsize=4096)
def outline_ink_bounds(path_data, matrix):
    """Exact Bézier extrema in page space; absent optional tools never guess."""
    try:
        from fontTools.pens.boundsPen import BoundsPen
        from fontTools.pens.transformPen import TransformPen
        from fontTools.svgLib.path import parse_path
        pen=BoundsPen(None)
        parse_path(path_data,TransformPen(pen,matrix))
        box=pen.bounds
        if box and all(__import__('math').isfinite(v) for v in box):return tuple(box)
    except (ImportError,ValueError,TypeError,KeyError,IndexError,AssertionError):
        pass
    return None


def math_ink_geometry(row):
    """Correct only extended mathematical glyph geometry, preserving native data.

    Some TeX extension fonts declare a one-em box for a delimiter spanning
    several em below its origin. An exact source outline is needed before
    replacing that glyph's declared box. Its centre supplies a math-axis
    estimate (a nominal quarter-em offset), not recovered text or a new glyph.
    Normal prose, rotated text and unsupported outlines keep native geometry.
    """
    if abs(row.get('direction',[1,0])[1])>.05:return None
    boxes=[];axes=[];evidence=[]
    for span in row.get('spans',[]):
        chars=span.get('chars',[])
        if not chars:
            if span.get('bbox'):boxes.append(span['bbox'])
            continue
        for char in chars:
            box=char.get('bbox');glyph=char.get('native_glyph',{})
            ink=glyph.get('ink_bbox');size=max(.1,span.get('size',row.get('size',10)))
            mathematical=bool(re.search(r'cmex|mtex|math|symbol',span.get('font',''),re.I))
            if (mathematical and ink and box and ink[3]-ink[1]>size*1.6 and
                    max(box[1]-ink[1],ink[3]-box[3])>size*.5):
                boxes.append(ink);axes.append((ink[1]+ink[3])/2+size*.25)
                evidence.append({'origin':char.get('origin'),'declared_bbox':box,
                                 'ink_bbox':ink,'outline_sha256':glyph.get('sha256')})
            elif box:boxes.append(box)
    if not axes or not boxes:return None
    import statistics
    return {'bbox':[min(b[0] for b in boxes),min(b[1] for b in boxes),
                    max(b[2] for b in boxes),max(b[3] for b in boxes)],
            'axis_baseline_estimate':statistics.median(axes),
            'method':'exact-source-outline-bounds-with-nominal-math-axis',
            'axis_is_estimate':True,'glyphs':evidence,'native_bbox_unchanged':True}


def source_glyph_outlines(page, lines, preserve_all=False):
    """Retain exact ink for an unresolved glyph, never infer its Unicode.

    This serializes a font outline already present in the source SVG. It is
    neither OCR nor an image crop. Only one unambiguous visible use at the
    measured font/GID/origin is accepted. Clipped or transformed ancestor
    groups remain unresolved rather than silently changing their appearance.
    """
    def identity(name):return re.sub(r'^[A-Z]{6}\+','',name).casefold().replace(' ','')
    traces=defaultdict(set);unmapped_positions=set()
    if hasattr(page,'get_texttrace'):
        for trace in page.get_texttrace():
            if trace.get('type',0)>=3 or trace.get('opacity',1)<=0:continue
            for cp,gid,origin,_ in trace['chars']:
                position=(identity(trace['font']),round(origin[0],2),round(origin[1],2))
                traces[position].add(gid)
                if cp==0xfffd or cp<32 or 0x7f<=cp<=0x9f:
                    unmapped_positions.add(position)
    pending=[]
    for line in lines:
        for span in line.get('spans',[]):
            for char in span.get('chars',[]):
                origin=char.get('origin',[])
                position=(identity(span.get('font','')),round(origin[0],2),round(origin[1],2)) if len(origin)==2 else None
                unresolved=(char.get('unicode_unresolved') or BAD.search(char.get('c','')) or
                            position in unmapped_positions and 'native_c' not in char and not char.get('unicode_recovered'))
                if unresolved:char['unicode_unresolved']=True
                if unresolved or preserve_all:pending.append((line,span,char))
        line['unicode_unresolved']=any(c.get('unicode_unresolved') for s in line.get('spans',[]) for c in s.get('chars',[]))
    if not pending or not hasattr(page,'get_svg_image') or getattr(page,'rotation',0):return 0
    root=ET.fromstring(page.get_svg_image(text_as_path=True))
    ns='{http://www.w3.org/2000/svg}';xlink='{http://www.w3.org/1999/xlink}href'
    parents={child:parent for parent in root.iter() for child in parent}
    definitions={item.get('id'):item for item in root.iter() if item.get('id')}
    uses=defaultdict(list)
    for use in root.iter(ns+'use'):
        match=re.fullmatch(r'matrix\(([^)]+)\)',use.get('transform',''))
        href=use.get(xlink,use.get('href',''))
        gid=re.search(r'_(\d+)$',href)
        if not match or not gid:continue
        try:matrix=[float(n) for n in re.split(r'[ ,]+',match.group(1).strip())]
        except ValueError:continue
        if len(matrix)!=6:continue
        uses[(round(matrix[4],2),round(matrix[5],2),int(gid.group(1)))].append(use)
    count=0
    for line,span,char in pending:
        box=char.get('bbox');origin=char.get('origin',[])
        if (char.get('synthetic') or not box or len(origin)!=2 or
                box[2]<=box[0] or box[3]<=box[1] or line.get('direction',[1,0])!=[1,0]):continue
        gids=traces.get((identity(span.get('font','')),round(origin[0],2),round(origin[1],2)),set())
        if len(gids)!=1:continue
        gid=next(iter(gids))
        # Native float32 origins and SVG decimal serialization can straddle a
        # half-cent boundary (e.g. 415.065002 versus 415.065). Look in adjacent
        # bins, then require the actual transform origin to agree within the
        # SVG serialization tolerance. Never choose a nearest ambiguous use.
        candidates={id(use):use for dx in (-.01,0,.01) for dy in (-.01,0,.01)
            for use in uses.get((round(origin[0]+dx,2),round(origin[1]+dy,2),gid),[])}
        matches=[]
        for use in candidates.values():
            transform=[float(n) for n in re.split(r'[ ,]+',
                re.fullmatch(r'matrix\(([^)]+)\)',use.get('transform','')).group(1).strip())]
            if max(abs(transform[4]-origin[0]),abs(transform[5]-origin[1]))<=.0001:
                matches.append(use)
        if len(matches)!=1:continue
        use=matches[0];href=use.get(xlink,use.get('href',''));path=definitions.get(href.lstrip('#'))
        if path is None or path.tag!=ns+'path' or path.get('d') is None or list(path):continue
        chain=[];node=parents.get(use)
        while node is not None and node is not root:
            chain.append(node);node=parents.get(node)
        if any(set(n.attrib)&{'transform','clip-path','mask','filter'} for n in chain):continue
        if set(use.attrib)&{'clip-path','mask','filter'}:continue
        # Preserve opacity composition in the ancestor chain instead of
        # flattening multipliers into a single inherited value.
        markup=ET.Element(ns+'svg',{'viewBox':' '.join(str(v) for v in [box[0],box[1],box[2]-box[0],box[3]-box[1]]),'overflow':'visible'})
        current=markup
        for node in reversed(chain):
            attrs={k:v for k,v in node.attrib.items() if k in {'fill','fill-opacity','stroke','stroke-width','stroke-opacity','opacity','fill-rule'}}
            if attrs:current=ET.SubElement(current,ns+'g',attrs)
        attrs={k:v for k,v in path.attrib.items() if k!='id'}
        attrs.update({k:v for k,v in use.attrib.items() if k in {'transform','fill','fill-opacity','stroke','stroke-width','stroke-opacity','opacity','fill-rule'}})
        ET.SubElement(current,ns+'path',attrs)
        svg=ET.tostring(markup,encoding='unicode').replace('ns0:','').replace(':ns0','')
        if __package__:
            from .vector_assets import validate_svg
        else:
            from vector_assets import validate_svg
        validate_svg(svg)
        char['native_glyph']={'svg':svg,'sha256':hashlib.sha256(svg.encode('utf-8')).hexdigest(),
            'bbox':list(box),'origin':list(origin),'font':span.get('font',''),'glyph_id':next(iter(gids)),
            'method':'exact-source-font-outline-at-native-origin','unicode_inferred':False,
            'empty_outline':not bool(path.get('d','').strip())}
        matrix=tuple(float(n) for n in re.split(r'[ ,]+',re.fullmatch(r'matrix\(([^)]+)\)',use.get('transform','')).group(1).strip()))
        ink=outline_ink_bounds(path.get('d',''),matrix)
        if ink:char['native_glyph']['ink_bbox']=list(ink)
        count+=1
    return count


def recover_lines(page, lines):
    report=_recover_cid_lines(page,lines)
    outlines=source_glyph_outlines(page,lines)
    unresolved=sum(bool(c.get('unicode_unresolved')) for line in lines for span in line.get('spans',[]) for c in span.get('chars',[]))
    if not report and not unresolved:return []
    if not report:report=[{'revision':REVISION,'characters_recovered':0,'fonts':[],
                           'source_bytes_unchanged':True,'semantic_certification':False}]
    report[0].update(unresolved_characters=unresolved,source_glyph_outlines=outlines,
                     outlines_are_unicode_recovery=False)
    return report
