"""Original font fixtures test glyph evidence; no licensed font is distributed."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
from recover_pdf_font_mapping import select_unicode,build_cmap,recover


class FontPolicyTests(unittest.TestCase):
    def test_homoglyphs_require_explicit_policy_and_missing_glyphs_stay_unresolved(self):
        self.assertIsNone(select_unicode([0x41,0x391,0x410])[0])
        self.assertEqual(select_unicode([0x41,0x391,0x410],script='Latin')[0],0x41)
        self.assertIsNone(select_unicode([0x6f,0x1d0f],script='Latin')[0])
        self.assertEqual(select_unicode([0x6f,0x1d0f],prefer_ascii=True)[0],0x6f)
        self.assertIsNone(select_unicode([])[0])
        self.assertIsNone(select_unicode([32,160])[0])
        self.assertEqual(select_unicode([32,160,0xf870],canonical_space=True)[0],32)

    def test_non_bmp_destination_uses_utf16_surrogate_pair(self):
        cmap=build_cmap({5:0x1f600,6:0x41})
        self.assertIn(b'<0005> <D83DDE00>',cmap)
        self.assertIn(b'<0006> <0041>',cmap)


@unittest.skipUnless(importlib.util.find_spec('fontTools') and importlib.util.find_spec('fitz'),'optional local font/PDF tooling')
class FontRecoveryIntegrationTests(unittest.TestCase):
    def test_missing_unicode_map_restores_original_fixture_text_and_preserves_pixels(self):
        import fitz
        from fontTools.fontBuilder import FontBuilder
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);font=base/'original-fixture.ttf'
            builder=FontBuilder(1000,isTTF=True);names=['.notdef','space','A','B'];builder.setupGlyphOrder(names)
            glyphs={}
            for name in names:
                pen=TTGlyphPen(None)
                if name=='A':pen.moveTo((0,0));pen.lineTo((300,700));pen.lineTo((600,0));pen.closePath()
                if name=='B':pen.moveTo((0,0));pen.lineTo((0,700));pen.lineTo((400,700));pen.lineTo((500,350));pen.lineTo((400,0));pen.closePath()
                glyphs[name]=pen.glyph()
            builder.setupGlyf(glyphs);builder.setupHorizontalMetrics({name:(650,0) for name in names});builder.setupHorizontalHeader(ascent=800,descent=-200);builder.setupCharacterMap({32:'space',65:'A',66:'B'});builder.setupNameTable({'familyName':'OriginalFixture','styleName':'Regular','uniqueFontIdentifier':'OriginalFixture-1','fullName':'OriginalFixture','psName':'OriginalFixture'});builder.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200);builder.setupPost();builder.setupMaxp();builder.save(font)
            source=base/'missing-map.pdf'
            with fitz.open() as pdf:
                page=pdf.new_page(width=400,height=300);page.insert_font(fontname='fixture',fontfile=str(font));page.insert_text((40,80),'AB A',fontname='fixture',fontsize=20)
                xref=page.get_fonts()[0][0];pdf.xref_set_key(xref,'ToUnicode','null');pdf.save(source)
            initial=hashlib.sha256(source.read_bytes()).hexdigest();out=base/'recovered.pdf';report=base/'evidence.json'
            result=recover(source,out,report,[font],canonical_space=True)
            self.assertTrue(result['appearance_preserved']);self.assertFalse(result['source_text_correctness_certified'])
            self.assertEqual(initial,hashlib.sha256(source.read_bytes()).hexdigest())
            with fitz.open(out) as pdf:self.assertIn('AB A',pdf[0].get_text())
            evidence=json.loads(report.read_text());self.assertTrue(evidence['review_required'])
            with self.assertRaises(FileExistsError):recover(source,out,report,[font])
            with self.assertRaisesRegex(ValueError,'No supported missing mapping'):recover(out,base/'second.pdf',base/'second.json',[font])


if __name__=='__main__':unittest.main()
