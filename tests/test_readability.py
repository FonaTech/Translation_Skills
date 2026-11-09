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
 def test_pdf_accent_prefers_coloured_title_over_near_black_body(self):
  import fitz
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/'source.pdf';d=fitz.open();p=d.new_page()
   p.insert_text((30,45),'A source title',fontsize=16,color=(.2,.2,.7))
   for y in range(80,500,14):p.insert_text((30,y),'Long body text dominates the raw colour count.',fontsize=10,color=(.14,.12,.13))
   d.save(f);d.close();profile=le.pdf_profile(f)
   with fitz.open(f) as source:
    title_colour=source[0].get_text('dict')['blocks'][0]['lines'][0]['spans'][0]['color']
   self.assertEqual(profile['accent'],le.color(title_colour))
   self.assertLess(profile['body_pt'],12)
 def test_alignment_row_keeps_ids_text_without_repeating_headings(self):
  b={'id':'D001-B1','source':{'document_id':'D001','page':1}};u={'id':'U1','source':'Original <text>.','translations':{'zh-Hans':{'faithful':'忠实内容。','interpretive':'译写内容。'}}}
  html=pub.alignment_pair(b,u,'zh-Hans',['faithful','interpretive'],pub.LABELS['zh'])
  for x in ['U1:source','U1:faithful','U1:interpretive','Original &lt;text&gt;.','忠实内容。','译写内容。']:self.assertIn(x,html)
  self.assertNotIn('class="pair-label"',html);self.assertIn('aria-label="原文"',html)

 def test_only_final_alignment_row_receives_an_explicit_block_keep(self):
  b={'id':'B1','presentation':{'keep_next':True},'source':{'document_id':'D001','page':2}}
  u={'id':'U1','source':'Then:','translations':{'zh-Hans':{'faithful':'于是：','interpretive':'据此：'}}}
  earlier=pub.alignment_pair(b,u,'zh-Hans',['faithful','interpretive'],pub.LABELS['zh'])
  final=pub.alignment_pair(b,u,'zh-Hans',['faithful','interpretive'],pub.LABELS['zh'],last_in_block=True)
  self.assertIn('data-keep-next="false"',earlier)
  self.assertIn('data-keep-next="true"',final)
  self.assertIn('data-source-page="2"',final)
  b['presentation']['keep_next']=False
  self.assertIn('data-keep-next="false"',pub.alignment_pair(b,u,'zh-Hans',['faithful','interpretive'],pub.LABELS['zh'],last_in_block=True))

 def test_monospace_presentation_reaches_actual_reader_css(self):
  import refinement
  self.assertEqual(refinement.design_patch({'font':'mono'}),{'font':'mono'})
  design={'page_mm':[210,297],'margin_x_mm':20,'margin_y_mm':20,'body_pt':11,'line_height':1.6,'columns':1,'accent':'#304659','font':'mono'}
  css=le.design_css({'documents':[{'document_id':'D001','route':'source','design':design}]})
  self.assertIn('font-family:"Noto Sans Mono","Courier New",monospace',css)
  self.assertNotIn('font-family:"Noto Serif"',css)

 def test_bibliography_role_is_preserved_for_legible_css(self):
  import refinement
  block={'id':'D1-B1','type':'paragraph','presentation':{'role':'bibliography'},'source':{'document_id':'D1','page':2},'units':[]}
  self.assertEqual(refinement.validate_blocks({'blocks':[block]}),[])
  self.assertIn('block-bibliography',pub.block_attrs(block))
  self.assertNotIn('block-metadata',pub.block_attrs(block))

 def test_bibliography_publishing_uses_existing_unit_boundaries(self):
  block={'id':'D1-B1','type':'paragraph','presentation':{'role':'bibliography'},'source':{'document_id':'D1','page':2},'units':[{'id':'r1','source':'[1] A. Title. 1999.','translations':{'zh-Hans':{'faithful':'[1] A. 题名。1999。'}}},{'id':'r2','source':'[2] B. Bad printed 2008.2-3185, 2002.','translations':{'zh-Hans':{'faithful':'[2] B. 原文异常 2008.2-3185，2002。'}}}]}
  html=pub.block_html(None,block,'zh-Hans','faithful',pub.LABELS['zh'])
  self.assertEqual(html.count('data-reference-entry="true"'),2)
  self.assertEqual(html.count('data-uid="r1"'),1)
  self.assertEqual(html.count('data-uid="r2"'),1)
  self.assertIn('2008.2-3185，2002。',html)

 def test_existing_title_beats_raw_filename_without_changing_source(self):
  import copy
  source={'id':'D1','name':'long_raw_filename_which_is_not_a_document_title.pdf'}
  block={'id':'D1-B1','type':'heading','level':1,'source':{'document_id':'D1'},'units':[{'id':'u1','source':'A title.','translations':{'zh-Hans':{'faithful':'已有标题。','interpretive':'已有标题的译写。'}}}]}
  content={'blocks':[block]};before=copy.deepcopy(content)
  self.assertEqual(pub.source_presentation(content,source,'zh-Hans','alignment')['display_title'],'已有标题。')
  self.assertEqual(pub.source_presentation(content,source,'zh-Hans','interpretive')['display_title'],'已有标题的译写。')
  explicit={**source,'display_title':'Explicit display title'}
  self.assertIs(pub.source_presentation(content,explicit,'zh-Hans','alignment'),explicit)
  self.assertIs(pub.source_presentation({'blocks':[]},source,'zh-Hans','alignment'),source)
  self.assertEqual(content,before)
  self.assertNotIn('display_title',source)

 def test_heading_ratio_drives_visible_title_size_until_explicit_override(self):
  meta={'editions':['faithful','interpretive'],'title':'Collection'}
  source={'id':'D1','name':'source.pdf'}
  design={'family':'source','page_mm':[210,297],'margin_x_mm':20,'margin_y_mm':20,'columns':1,'body_pt':10,'line_height':1.6,'accent':'#304659','heading_ratio':1.8}
  settings=pub.document_section(meta,source,design,'zh-Hans','faithful',pub.LABELS['zh'])
  self.assertEqual(settings['design']['titleSize'],18)
  self.assertEqual(pub.document_section(meta,source,{**design,'title_pt':25},'zh-Hans','faithful',pub.LABELS['zh'])['design']['titleSize'],25)

 def test_explicit_numbered_entries_do_not_fragment_journal_abbreviations(self):
  import translate as t
  text='[1] A. Author, J. Appl. Phys. 2020, 1, 2.\n[2] B. Author, Nat. Commun.\n2021, 2, 3.'
  parts=t.split_numbered_entries(text)
  self.assertEqual(parts,['[1] A. Author, J. Appl. Phys. 2020, 1, 2.','[2] B. Author, Nat. Commun.\n2021, 2, 3.'])
  self.assertEqual(''.join(text.split()),''.join(''.join(parts).split()))
  for ambiguous in ['A paragraph cites [1] and [2].','[1] A.\n[3] C.','Intro\n[1] A.\n[2] B.','[1] A.']:
   self.assertIsNone(t.split_numbered_entries(ambiguous))
