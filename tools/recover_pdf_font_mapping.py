#!/usr/bin/env python3
"""Recover missing Identity-H Unicode maps by exact reference glyph outlines.

Copyright 2026 Yufeng Zhan. MIT. Never downloads or distributes reference fonts.
The source stays immutable. A repaired copy remains subject to source review.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def font_key(name):
    return re.sub(r'[^\w]','',re.sub(r'^[A-Z]{6}\+','',name)).casefold()


def glyph_signature(font,name):
    """Outline commands and advance, normalized by source units per em."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    glyphs=font.getGlyphSet();pen=DecomposingRecordingPen(glyphs);glyphs[name].draw(pen)
    em=font['head'].unitsPerEm
    commands=tuple((operator,tuple(None if point is None else tuple(round(v/em,8) for v in point)
                                  for point in points)) for operator,points in pen.value)
    return commands,round(glyphs[name].width/em,8)


def select_unicode(candidates,script=None,canonical_space=False,prefer_ascii=False):
    """Ambiguities stay unresolved unless an explicit script/spacing policy applies."""
    candidates=sorted(set(candidates))
    if len(candidates)==1:return candidates[0],'unique-outline-and-advance'
    if candidates and all(chr(c).isspace() or unicodedata.category(chr(c)) in {'Co','Cf'} for c in candidates) and canonical_space and 32 in candidates:
        return 32,'explicit-canonical-space-policy'
    if prefer_ascii and len([c for c in candidates if 33<=c<=126])==1:
        return next(c for c in candidates if 33<=c<=126),'explicit-ascii-homoglyph-policy'
    if script and candidates and all(unicodedata.category(chr(c)).startswith('L') for c in candidates):
        scoped=[c for c in candidates if script.upper() in unicodedata.name(chr(c),'')]
        if len(scoped)==1:return scoped[0],'explicit-script-policy'
    return None,'ambiguous-outline' if candidates else 'no-exact-reference-glyph'


def build_cmap(mapping):
    """Identity-H CIDs have two-byte source codes; destinations may be UTF-16 pairs."""
    lines=['/CIDInit /ProcSet findresource begin','12 dict begin','begincmap',
           '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def',
           '/CMapName /RecoveredOutlineEvidence def','/CMapType 2 def',
           '1 begincodespacerange','<0000> <FFFF>','endcodespacerange']
    items=sorted(mapping.items())
    for start in range(0,len(items),100):
        batch=items[start:start+100];lines.append(str(len(batch))+' beginbfchar')
        lines.extend(f'<{cid:04X}> <{chr(cp).encode("utf-16-be").hex().upper()}>' for cid,cp in batch)
        lines.append('endbfchar')
    lines.extend(['endcmap','CMapName currentdict /CMap defineresource pop','end','end'])
    return ('\n'.join(lines)+'\n').encode('ascii')


def reference_index(files):
    from fontTools.ttLib import TTFont,TTCollection
    index=defaultdict(set);references=[]
    for path in files:
        path=Path(path).resolve()
        fonts=TTCollection(str(path)).fonts if path.suffix.lower() in {'.ttc','.otc'} else [TTFont(str(path))]
        references.append({'filename':path.name,'sha256':sha(path),'faces':len(fonts)})
        for font in fonts:
            cache={}
            for cp,name in (font.getBestCmap() or {}).items():
                if cp>0x10ffff or 0xd800<=cp<=0xdfff or unicodedata.category(chr(cp))=='Cc':continue
                if name not in cache:cache[name]=glyph_signature(font,name)
                index[cache[name]].add(cp)
            font.close()
    return index,references


def recover(source,output,report,reference_fonts,script=None,canonical_space=False,prefer_ascii=False,reviewed_map=None):
    import fitz
    from fontTools.ttLib import TTFont
    source=Path(source).resolve();output=Path(output).resolve();report=Path(report).resolve()
    if source==output or output.exists() or report.exists():raise FileExistsError('Preserve source and prior artifacts; choose new output and report paths.')
    if report in {source,output}:raise ValueError('Use separate source, output and report files.')
    manual={}
    if reviewed_map:
        labels=json.loads(Path(reviewed_map).read_text(encoding='utf-8'))
        if labels.get('source_sha256')!=sha(source):raise ValueError('Reviewed mapping source identity mismatch.')
        for item in labels.get('glyphs',[]):
            cp=int(item['unicode'][2:],16)
            if not item.get('evidence') or type(item.get('page')) is not int or not 1<=item['page'] or not 0<=cp<=0x10ffff or 0xd800<=cp<=0xdfff or unicodedata.category(chr(cp))=='Cc':raise ValueError('Reviewed mappings require a valid Unicode character, source page and inspection evidence.')
            key=(item['font_xref'],item['cid'])
            if key in manual:raise ValueError('Duplicate reviewed glyph mapping.')
            manual[key]=item
    index,references=reference_index(reference_fonts);fonts={};usage=defaultdict(set);used_manual=set()
    with fitz.open(source) as doc:
        if doc.is_encrypted or doc.needs_pass:raise ValueError('Use an authorized unlocked source copy.')
        for page in doc:
            for font in page.get_fonts(full=True):fonts[font[0]]=font
            for trace in page.get_texttrace():usage[font_key(trace['font'])].update(c[1] for c in trace['chars'])
        records=[]
        for xref,font in sorted(fonts.items()):
            _,ext,kind,name,*_=font;record={'font_xref':xref,'name':name,'status':'skipped'}
            records.append(record)
            if kind!='Type0' or doc.xref_get_key(xref,'Encoding')!=('name','/Identity-H'):
                record['reason']='Only Identity-H Type0 fonts are supported.';continue
            if doc.xref_get_key(xref,'ToUnicode')[0]!='null':
                record['reason']='Existing Unicode maps are preserved.';continue
            descendants=re.findall(r'(\d+)\s+0\s+R',doc.xref_get_key(xref,'DescendantFonts')[1])
            if len(descendants)!=1:record['reason']='Unsupported descendant font tree.';continue
            child=int(descendants[0])
            if doc.xref_get_key(child,'Subtype')!=('name','/CIDFontType2') or doc.xref_get_key(child,'CIDToGIDMap') not in {('name','/Identity'),('null','null')}:
                record['reason']='Only CIDFontType2 explicit/default identity glyph maps are supported.';continue
            embedded=doc.extract_font(xref)[3]
            if not embedded:record['reason']='No embedded font program.';continue
            try:face=TTFont(io.BytesIO(embedded))
            except Exception as error:record['reason']='Unsupported font program: '+str(error);continue
            aliases={font_key(name)}
            if 'name' in face:
                for entry in face['name'].names:
                    if entry.nameID in {4,6}:
                        try:aliases.add(font_key(entry.toUnicode()))
                        except UnicodeError:pass
            gids=set().union(*(usage.get(alias,set()) for alias in aliases))
            # Trace names vary in punctuation; avoid inventing a correspondence.
            if not gids:record['reason']='No unambiguous trace-name correspondence.';face.close();continue
            mapping={};evidence=[];recovered_count=0
            for gid in sorted(gids):
                if not 0<=gid<len(face.getGlyphOrder()):continue
                try:signature=glyph_signature(face,face.getGlyphName(gid))
                except Exception:continue
                choices=sorted(index.get(signature,[]));cp,reason=select_unicode(choices,script,canonical_space,prefer_ascii)
                # Empty outlines supply no letter evidence. Only the explicitly
                # selected whitespace normalization may recover such a glyph.
                if not signature[0]:
                    if cp==32 and canonical_space:reason='explicit-canonical-space-policy'
                    else:cp=None;reason='empty-outline-unresolved'
                authored=manual.get((xref,gid))
                if authored:
                    if authored['page']>len(doc):raise ValueError('Reviewed mapping page outside the source.')
                    witnessed=any(font_key(t['font']) in aliases and any(c[1]==gid for c in t['chars']) for t in doc[authored['page']-1].get_texttrace())
                    if not witnessed:raise ValueError('Reviewed glyph is not present on its recorded source page.')
                    used_manual.add((xref,gid))
                    cp=int(authored['unicode'][2:],16);reason='explicit-source-inspected-glyph-mapping'
                if cp is not None:mapping[gid]=cp;recovered_count+=1
                else:mapping[gid]=0xfffd
                evidence.append({'cid':gid,'unicode_candidates':[f'U+{v:04X}' for v in choices],
                    'selected':f'U+{cp:04X}' if cp is not None else None,'reason':reason,
                    'outline_signature_sha256':hashlib.sha256(repr(signature).encode()).hexdigest(),
                    **({'source_inspection':authored} if authored else {})})
            face.close();record.update(used_glyphs=len(gids),mapped_glyphs=recovered_count,glyph_evidence=evidence)
            if not recovered_count:record['reason']='No uniquely supported mappings.';continue
            cmap=doc.get_new_xref();doc.update_object(cmap,'<< >>');doc.update_stream(cmap,build_cmap(mapping));doc.xref_set_key(xref,'ToUnicode',f'{cmap} 0 R');record['status']='partial-map-added';record['unresolved_used_glyphs']=len(gids)-recovered_count
        if set(manual)!=used_manual:raise ValueError('Some reviewed glyph mappings do not match supported source-font evidence.')
        if not any(r['status']=='partial-map-added' for r in records):raise ValueError('No supported missing mapping recovered; preserve source and use OCR/source review.')
        output.parent.mkdir(parents=True,exist_ok=True);doc.save(output,garbage=0,deflate=True)
    visual=[];pages=[]
    with fitz.open(source) as before,fitz.open(output) as after:
        for i in range(len(before)):
            bp=before[i].get_pixmap(matrix=fitz.Matrix(1,1),alpha=False);ap=after[i].get_pixmap(matrix=fitz.Matrix(1,1),alpha=False)
            same=bp.width==ap.width and bp.height==ap.height and bp.samples==ap.samples;visual.append(same)
            text=after[i].get_text();pages.append({'page':i+1,'appearance_pixels_identical_at_72dpi':same,
                'native_characters':len(text),'replacement_characters':text.count('\ufffd'),
                'control_characters':sum(ord(c)<32 and c not in '\t\r\n' for c in text),
                'text_sha256':hashlib.sha256(text.encode()).hexdigest()})
    result={'version':'1.0.3','source_sha256':sha(source),'output_sha256':sha(output),'reference_fonts':references,
        'explicit_script_policy':script,'explicit_canonical_space_policy':canonical_space,'explicit_ascii_homoglyph_policy':prefer_ascii,
        'reviewed_map_sha256':sha(reviewed_map) if reviewed_map else None,'fonts':records,'pages':pages,
        'appearance_preserved':all(visual),'source_text_correctness_certified':False,
        'review_required':True,'meaning':'Exact outline/advance evidence with explicit ambiguity policies. Pixel identity checks unchanged appearance, not Unicode correctness. Inspect every recovered source passage; unresolved glyphs still require source-based OCR or transcription. No source words are supplied by a language model.'}
    report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if not result['appearance_preserved']:raise ValueError('Recovered copy changed rendered appearance; inspect the preserved evidence and do not release it.')
    return {'mapped_fonts':sum(r['status']=='partial-map-added' for r in records),'pages':len(pages),
            'appearance_preserved':result['appearance_preserved'],'source_text_correctness_certified':False,'report':str(report)}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--reference-font',type=Path,action='append',required=True);p.add_argument('--script',choices=['Latin','Greek','Cyrillic','Arabic','Hebrew']);p.add_argument('--canonical-space',action='store_true');p.add_argument('--prefer-ascii',action='store_true');p.add_argument('--reviewed-map',type=Path);a=p.parse_args()
    print(json.dumps(recover(a.source,a.output,a.report,a.reference_font,a.script,a.canonical_space,a.prefer_ascii,a.reviewed_map),ensure_ascii=False))


if __name__=='__main__':
    from cli_encoding import configure_utf8
    configure_utf8()
    main()
