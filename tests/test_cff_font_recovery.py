"""Owned font outlines exercise CFF recovery without proprietary font assets."""
import copy
import hashlib
import io
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/document-translation/scripts'))
import cff_font_recovery as cff
import pdf_text_recovery as recovery


def shape(index=0):
    width = 240+index*12
    return {'path': f'M0 0H{width}V500H0Z', 'bbox': (0, 0, width, 500),
            'advance': width+60}


def test_outline_match_rejects_missing_stroke_advance_and_font_geometry():
    source = shape()
    assert cff.compare_outlines(source, source)
    assert cff.compare_outlines(source, {**source, 'advance': source['advance']+2}) is None
    assert cff.compare_outlines(source, {**source, 'bbox': (0, 0, 250, 500)}) is None
    # Same bbox and advance, but an internal aperture was removed.
    changed = {**source, 'path': source['path']+'M30 30V470H210V30Z'}
    assert cff.compare_outlines(source, changed) is None


def test_homoglyph_needs_complete_subset_correspondence_not_single_gid():
    source = [{**shape(), 'cid': 1}]
    glyphs = [{**shape(), 'gid': 1, 'cps': [65]},
              {**shape(), 'gid': 2, 'cps': [913]}]
    mapping, evidence = cff.choose_mappings(source, [{'sha256': 'owned', 'glyphs': glyphs}])
    assert not mapping
    assert not evidence['correspondence']['owned']['accepted']


def test_correspondence_rejects_permuted_cids_and_keeps_empty_nonspace_unknown():
    source = [{**shape(i), 'cid': i+1} for i in range(20)]
    glyphs = [{**shape(i), 'gid': i+1, 'cps': [65+i]} for i in range(20)]
    # Add a shape-identical second alphabet and an uninked glyph.
    glyphs += [{**shape(i), 'gid': i+101, 'cps': [0x391+i]} for i in range(20)]
    source.append({'cid': 21, 'bbox': None, 'path': '', 'advance': 250})
    glyphs += [{'gid': 21, 'cps': [32], 'bbox': None, 'path': '', 'advance': 250},
               {'gid': 22, 'cps': [160], 'bbox': None, 'path': '', 'advance': 250}]
    mapping, evidence = cff.choose_mappings(source, [{'sha256': 'owned', 'glyphs': glyphs}])
    assert mapping == {**{i+1: chr(65+i) for i in range(20)}, 21: ' '}
    assert evidence['correspondence']['owned']['accepted']
    for item in source:
        item['cid'] += 1
    mapping, evidence = cff.choose_mappings(source, [{'sha256': 'owned', 'glyphs': glyphs}])
    assert not mapping
    assert not evidence['correspondence']['owned']['accepted']


def owned_fonts(family='Fixture'):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    from fontTools.cffLib import FDArrayIndex, FontDict, FDSelect
    names = ['.notdef']+[chr(65+i) for i in range(20)]+['space']
    widths = {name: (300+i*12, 0) for i, name in enumerate(names)}
    outlines = {}
    charstrings = {}
    for i, name in enumerate(names):
        ttpen, cpen = TTGlyphPen(None), T2CharStringPen(widths[name][0], None)
        if name != 'space':
            for pen in [ttpen, cpen]:
                pen.moveTo((0, 0)); pen.lineTo((240+i*12, 0))
                pen.lineTo((240+i*12, 500)); pen.lineTo((0, 500)); pen.closePath()
        outlines[name] = ttpen.glyph()
        charstrings[name] = cpen.getCharString()
    references = []
    for truetype in [True, False]:
        builder = FontBuilder(1000, isTTF=truetype)
        builder.setupGlyphOrder(names)
        builder.setupCharacterMap({**{65+i: chr(65+i) for i in range(20)}, 32: 'space'})
        builder.setupHorizontalMetrics(widths)
        builder.setupHorizontalHeader(ascent=800, descent=-200)
        builder.setupNameTable({'familyName': family, 'styleName': 'Regular',
                                'uniqueFontIdentifier': family, 'fullName': family, 'psName': family})
        builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
        builder.setupPost()
        if truetype:
            builder.setupGlyf(outlines)
            stream = io.BytesIO(); builder.save(stream); references.append(stream.getvalue())
        else:
            builder.setupCFF(family, {'FullName': family, 'FamilyName': family,
                                       'Weight': 'Regular'}, charstrings, {})
            fontset = builder.font['CFF '].cff
            top = fontset[fontset.fontNames[0]]
            cid_names = ['.notdef']+['cid'+str(i).zfill(5) for i in range(1, len(names))]
            top.CharStrings.charStrings = {new: top.CharStrings.charStrings[old]
                                            for old, new in zip(names, cid_names)}
            top.charset = cid_names
            top.ROS = ('Adobe', 'Identity', 0); top.CIDCount = len(names)
            fd = FontDict(); fd.Private = top.Private; fd.FontName = family
            top.FDArray = FDArrayIndex(); top.FDArray.append(fd)
            top.FDSelect = FDSelect(format=3); top.FDSelect.gidArray = [0]*len(names)
            del top.Private
            stream = io.BytesIO(); fontset.compile(stream, builder.font); references.append(stream.getvalue())
    return references


def source_pdf(path, cff_bytes):
    import fitz
    with fitz.open() as document:
        page = document.new_page(width=400, height=200)
        def obj(text):
            xref = document.get_new_xref(); document.update_object(xref, text); return xref
        program = obj('<< /Subtype /CIDFontType0C >>'); document.update_stream(program, cff_bytes)
        descriptor = obj(f'<< /Type /FontDescriptor /FontName /Fixture /Flags 4 '
                         f'/FontBBox [0 -200 1000 800] /Ascent 800 /Descent -200 '
                         f'/CapHeight 700 /StemV 80 /ItalicAngle 0 /FontFile3 {program} 0 R >>')
        widths = ' '.join(str(300+i*12) for i in range(22))
        child = obj(f'<< /Type /Font /Subtype /CIDFontType0 /BaseFont /Fixture '
                    f'/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> '
                    f'/FontDescriptor {descriptor} 0 R /W [0 [{widths}]] >>')
        font = obj(f'<< /Type /Font /Subtype /Type0 /BaseFont /Fixture-Identity-H '
                   f'/Encoding /Identity-H /DescendantFonts [{child} 0 R] >>')
        resources = obj(f'<< /Font << /F1 {font} 0 R >> >>')
        document.xref_set_key(page.xref, 'Resources', f'{resources} 0 R')
        content = obj('<< >>')
        encoded = ''.join(f'{i:04x}' for i in range(1, 22))
        document.update_stream(content, f'BT /F1 12 Tf 30 100 Td <{encoded}> Tj ET'.encode('ascii'))
        document.xref_set_key(page.xref, 'Contents', f'{content} 0 R')
        document.save(path)


def test_real_cid_cff_missing_map_recovers_from_owned_local_reference(tmp_path):
    import fitz
    import source_structure
    reference, program = owned_fonts()
    fontfile = tmp_path/'Fixture.ttf'; fontfile.write_bytes(reference)
    source = tmp_path/'source.pdf'; source_pdf(source, program)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    recovery.document_maps.cache_clear()
    with patch.object(recovery, 'font_files', return_value=[fontfile]):
        with fitz.open(source) as document:
            pixels = document[0].get_pixmap().samples
            page = source_structure.raw_page(document[0])
            text = ''.join(row['text'] for row in page['native_lines'])
            assert text.rstrip() == 'ABCDEFGHIJKLMNOPQRST'
            assert document[0].get_pixmap().samples == pixels
            proof = page['glyph_recovery'][0]
            assert proof['characters_recovered'] >= 20
            assert proof['fonts'][0]['method'] == 'bounded-cff-reference-outlines-and-advance'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_different_family_and_absent_reference_do_not_guess(tmp_path):
    reference, program = owned_fonts()
    fontfile = tmp_path/'Unrelated.ttf'; fontfile.write_bytes(reference)
    mapping, proof = cff.recover(program, [], [fontfile], recovery.key)
    assert mapping == {} and proof is None


def test_reference_filename_cannot_override_its_actual_font_identity(tmp_path):
    _, program = owned_fonts()
    unrelated, _ = owned_fonts('Unrelated')
    fontfile = tmp_path/'Fixture.ttf'; fontfile.write_bytes(unrelated)
    mapping, proof = cff.recover(program, [], [fontfile], recovery.key)
    assert mapping == {} and proof is None
