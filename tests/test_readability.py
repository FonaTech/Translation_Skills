"""Source-colour and repeated alignment furniture regressions from real papers."""
import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'skills/document-translation/scripts'))
import layout_engine as le,publishing as pub
class ReadabilityTests(unittest.TestCase):
 def test_white_watermark_is_not_heading_ink(self):
  self.assertEqual(le.readable_accent('#fff6f6'),'#304659')
  self.assertEqual(le.readable_accent('#ffffff',None),None)
  self.assertEqual(le.readable_accent('#234567'),'#234567')
 def test_pdf_profile_ignores_pale_watermark(self):
  import fitz
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/'source.pdf';d=fitz.open();p=d.new_page();p.insert_text((30,40),'Visible body paragraph.',color=(0,0,0));p.insert_text((30,80),'Pale watermark '*8,color=(1,.965,.965));d.save(f);d.close()
   self.assertEqual(le.pdf_profile(f)['accent'],'#304659')
 def test_alignment_row_keeps_ids_text_without_repeating_headings(self):
  b={'id':'D001-B1','source':{'document_id':'D001','page':1}};u={'id':'U1','source':'Original <text>.','translations':{'zh-Hans':{'faithful':'忠实内容。','interpretive':'译写内容。'}}}
  html=pub.alignment_pair(b,u,'zh-Hans',['faithful','interpretive'],pub.LABELS['zh'])
  for x in ['U1:source','U1:faithful','U1:interpretive','Original &lt;text&gt;.','忠实内容。','译写内容。']:self.assertIn(x,html)
  self.assertNotIn('class="pair-label"',html);self.assertIn('aria-label="原文"',html)
