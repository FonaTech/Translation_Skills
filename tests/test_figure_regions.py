"""Original geometry fixtures verify automatic crops and parser/layout handoff."""
import argparse, contextlib, copy, io, json, sys, tempfile, unittest
from unittest import mock
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'skills/document-translation/scripts'),str(ROOT/'tools')]
import figure_regions as f
import translate as t
import layout_engine

class FigureRegionTests(unittest.TestCase):
 def test_single_parser_band_does_not_erase_measured_multiple_columns(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=self.fixture(root)
   c={'sources':[{'id':'D001','file':'source.pdf','name':'source.pdf'}],'blocks':[]}
   m={'layout':{}}
   measured=layout_engine.profile(source);measured['columns']=2;measured['features']['columns']=2
   for bands,expected in [(1,2),(2,2),(3,3)]:
    parsed={'pages':[{'columns':bands}],'review_status':'pending'}
    c['sources'][0]['layout_ir']={'file':'fixture.json','sha256':'fixture'}
    with mock.patch('layout_engine.profile',return_value=copy.deepcopy(measured)),mock.patch('structure_layout.read_map',return_value=parsed):
     result=layout_engine.plan(root,m,c)
    self.assertEqual(result['documents'][0]['design']['columns'],expected)
    self.assertEqual(result['profiles']['D001']['features']['columns'],expected)

 def test_uncaptioned_automatic_crop_is_audit_only_and_keeps_prose(self):
  import fitz
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);d=fitz.open();page=d.new_page(width=600,height=800)
   page.draw_rect(fitz.Rect(40,100,260,220));page.insert_text((70,145),'Uncaptioned source object',fontsize=9)
   c={'sources':[{'id':'D001'}],'blocks':[]}
   prose=t.add_block(c,'D001','paragraph',{'page':1,'bbox':[40,260,540,280]},['The visible source prose remains selected.'])
   before=copy.deepcopy(prose)
   records=f.append_page(root,c,'D001',page,t.add_block)
   self.assertTrue(records);self.assertTrue(all(not x['translation_eligible'] for x in records))
   self.assertEqual(c['blocks'],[before]);self.assertTrue(all(x['block_id'] is None for x in records))
   self.assertTrue(all((root/x['asset']).is_file() and (root/x['crop_text']['file']).is_file() for x in records))
   ledger=t.read(root/'reports/figure-regions/D001-p0001.json')
   self.assertFalse(ledger['native_units_removed']);d.close()

 def test_legacy_filter_keeps_manual_crops_equations_and_source_units(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);c={'sources':[{'id':'D001'}],'blocks':[]}
   caption=t.add_block(c,'D001','paragraph',{'page':1},['Figure 1. Visible caption.'])
   prose=t.add_block(c,'D001','paragraph',{'page':1},['Source body remains complete.'])
   bound=t.add_block(c,'D001','image',{'page':1},[],figure_region={},caption_block_ids=[caption['id']])
   manual=t.add_block(c,'D001','image',{'page':1},[],asset='assets/manual.png')
   equation=t.add_block(c,'D001','equation',{'page':1},['E = mc²'],figure_region={})
   bad=t.add_block(c,'D001','image',{'page':1},['Uncaptioned artifact label'],figure_region={},caption_block_ids=[])
   bad['units'][0]['translations']={'zh-Hans':{'faithful':'原有标签','interpretive':'原有标签'}}
   dangling=t.add_block(c,'D001','image',{'page':1},[],figure_region={},caption_block_ids=['missing'])
   wrong_page=t.add_block(c,'D001','image',{'page':2},[],figure_region={},caption_block_ids=[caption['id']])
   expected=copy.deepcopy([caption,prose,bound,manual,equation]);saved=copy.deepcopy(bad)
   excluded=f.archive_unbound(root,c)
   self.assertEqual(set(excluded),{bad['id'],dangling['id'],wrong_page['id']});self.assertEqual(c['blocks'],expected)
   archive=t.read(root/'reports/figure-regions/excluded-automatic-images.json')
   self.assertEqual(archive['blocks'][0],saved);self.assertFalse(archive['native_prose_removed'])
   self.assertEqual(f.archive_unbound(root,c),[])
   self.assertEqual(t.read(root/'reports/figure-regions/excluded-automatic-images.json'),archive)

 def test_task_packets_do_not_reintroduce_unbound_crop_context(self):
  import agent_packets
  c={'sources':[{'id':'D001'}],'blocks':[]}
  label=t.add_block(c,'D001','paragraph',{'page':1},['Visible native label'],structure={'semantic_role':'label'})
  bad=t.add_block(c,'D001','image',{'page':1},['Artifact label'],figure_region={},caption_block_ids=[],crop_text={'file':'audit.json'})
  items=agent_packets.prepare(c,'zh-Hans',['faithful','interpretive'],True,lambda s:[s])
  self.assertEqual([x['id'] for x in items],[label['units'][0]['id']])
  self.assertEqual(items[0]['context']['related_figures'],[])

 def fixture(self,root):
  import fitz
  d=fitz.open();p=d.new_page(width=600,height=800)
  p.insert_text((40,40),'Source geometry fixture',fontsize=16)
  p.draw_rect(fitz.Rect(40,100,260,220),color=(0,0,0));p.draw_line((45,200),(230,120))
  p.insert_text((70,145),'Signal A',fontsize=9)
  p.insert_text((40,242),'Figure 1. Original measured signal.',fontsize=9)
  p.insert_text((40,280),'The source paragraph remains separate and must not enter the image crop.',fontsize=10)
  file=root/'source.pdf';d.save(file);d.close();return file
 def test_vector_only_autocrop_archives_text_fonts_and_caption_candidates(self):
  import fitz
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=self.fixture(root);p=root/'project'
   with contextlib.redirect_stdout(io.StringIO()):
    t.init(argparse.Namespace(project=str(p),title='Source',languages='zh-Hans',style='editorial',page_size='A4',columns=1))
    t.ingest(t.parser().parse_args(['ingest',str(p),str(source)]))
   _,m,c=t.project(p);images=[b for b in c['blocks'] if b['type']=='image'];self.assertEqual(len(images),1)
   b=images[0];self.assertTrue(b['asset'].endswith('.svg'));self.assertTrue(b['caption_block_ids'])
   data=t.read(p/b['crop_text']['file']);self.assertIn('Signal A',data['plain_text']);self.assertNotIn('source paragraph',data['plain_text'])
   self.assertTrue(any('Figure 1.' in row['text'] for row in data['nearby_context']))
   self.assertIn('font',data['lines'][0]['spans'][0]);self.assertIn('chars',data['lines'][0]['spans'][0])
   self.assertFalse(any('Signal A' in u['source'] for _,u in t.units(c)))
   archived=[x for image in images for x in image.get('source_label_blocks',[])]
   self.assertTrue(any('Signal A' in u['source'] for x in archived for u in x['units']))
   self.assertTrue(any('source paragraph' in u['source'] for _,u in t.units(c)))
   plan=layout_engine.plan(p,m,c);self.assertIn('parser_layout',plan['profiles']['D001'])
   self.assertTrue(all('layout_hint' in x for x in c['blocks']))
   tasks=t.parser().parse_args(['tasks',str(p),'--language','zh-Hans','--all'])
   with contextlib.redirect_stdout(io.StringIO()):tasks.fn(tasks)
   context=t.read(p/'tasks/zh-Hans-figure-context.json');self.assertEqual(len(context['figures']),1)
   (p/b['crop_text']['text_file']).write_text('tampered')
   self.assertIn('crop-text-evidence',[x['code'] for x in t.audit_data(p,m,c)['errors']])
 def test_scan_preserves_page_image_and_marks_native_text_unknown(self):
  import fitz
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);d=fitz.open(self.fixture(root));pix=d[0].get_pixmap();scan=fitz.open();p=scan.new_page(width=600,height=800);p.insert_image(p.rect,pixmap=pix)
   proposals=f.propose(p,[]);self.assertEqual(len(proposals),1)
   evidence=f.export_region(p,p.rect,root/'crop',root)
   data=t.read(root/evidence['crop_text']['file']);self.assertEqual(data['lines'],[]);self.assertTrue(data['ocr_required_if_visible_text_missing'])
   self.assertEqual(proposals[0]['caption_block_ids'],[]);scan.close();d.close()
 def test_caption_in_other_column_does_not_bind(self):
  import fitz
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);d=fitz.open(self.fixture(root));p=d[0]
   blocks=[{'id':'cap','type':'paragraph','source':{'bbox':[330,230,550,250]},'units':[{'source':'Figure 2. Unrelated.'}],'presentation':{'role':'caption'}}]
   self.assertTrue(all(not x['caption_block_ids'] for x in f.propose(p,blocks)));d.close()
 def test_cross_column_caption_groups_disconnected_panels_and_keeps_labels(self):
  import fitz
  with tempfile.TemporaryDirectory() as directory:
   d=fitz.open();p=d.new_page(width=600,height=800)
   for box in [(40,100,240,180),(330,100,540,180),(40,220,240,300),(330,220,540,300)]:p.draw_rect(fitz.Rect(box))
   blocks=[{'id':'cap','type':'paragraph','source':{'bbox':[40,340,285,350]},'units':[{'source':'Figure 1. Four independent panels on one source plate.'}],'presentation':{'role':'caption'}},
    {'id':'continuation','type':'paragraph','source':{'bbox':[310,340,560,350]},'units':[{'source':'The continuation at the same baseline describes these panels.'}]},
    {'id':'label','type':'paragraph','source':{'bbox':[42,305,150,315]},'units':[{'source':'Clock cycle 5'}],'structure':{'semantic_role':'table'}}]
   proposals=f.propose(p,blocks);self.assertEqual(len(proposals),1);b=proposals[0]['bbox']
   self.assertLessEqual(b[0],40);self.assertGreaterEqual(b[2],540);self.assertGreaterEqual(b[3],315)
   self.assertEqual(proposals[0]['caption_block_ids'],['cap']);d.close()
 def test_narrative_figure_reference_is_not_caption(self):
  import fitz
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);d=fitz.open(self.fixture(root));p=d[0]
   b={'id':'body','type':'paragraph','source':{'bbox':[40,240,290,260]},'units':[{'source':'Figure 1 shows the original observation in a narrative paragraph.'}]}
   self.assertTrue(all(not x['caption_block_ids'] for x in f.propose(p,[b])));d.close()
 def test_low_score_full_width_caption_admits_near_panels_but_not_across_caption(self):
  import fitz
  d=fitz.open();p=d.new_page(width=600,height=800)
  for box in [(40,80,260,180),(330,80,550,180),(40,220,260,320),(330,220,550,320),(40,430,550,530)]:p.draw_rect(fitz.Rect(box))
  blocks=[{'id':'first','type':'paragraph','source':{'bbox':[40,330,560,355]},'units':[{'source':'Figure 1. A complete plate with four panels.'}],'presentation':{'role':'caption'}},
   {'id':'second','type':'paragraph','source':{'bbox':[40,545,560,570]},'units':[{'source':'Figure 2. A separate plate.'}],'presentation':{'role':'caption'}}]
  learned={'id':'fixture','link_head':{},'link_threshold':.7}
  with mock.patch('figure_learning.load_model',return_value=learned),mock.patch('figure_learning.predict',return_value=[.01]):proposals=f.propose(p,blocks)
  first=next(x for x in proposals if x['caption_block_ids']==['first'])
  second=next(x for x in proposals if x['caption_block_ids']==['second'])
  self.assertLessEqual(first['bbox'][0],40);self.assertGreaterEqual(first['bbox'][2],550)
  self.assertLess(first['bbox'][3],330);self.assertGreater(second['bbox'][1],355)
  self.assertIn('bounded-caption-band',first['association_routes']);d.close()
 def test_stale_parser_layout_rejected(self):
  import structure_layout
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'map.json').write_text('{}')
   with self.assertRaises(ValueError):structure_layout.read_map(root,{'layout_ir':{'file':'map.json','sha256':'bad'},'sha256':'source'})
 def test_layout_map_rejects_changed_source_blocks_but_allows_translation(self):
  import structure_layout
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=self.fixture(root)
   c={'sources':[],'blocks':[]};s={'id':'D001','file':'source.pdf','sha256':t.sha(source)};c['sources']=[s]
   b=t.add_block(c,'D001','paragraph',{'page':1,'bbox':[40,40,300,65]},['Source heading.'])
   structure_layout.write_map(root,c,s)
   self.assertIsNotNone(structure_layout.read_map(root,s,c))
   b['units'][0]['translations']={'zh-Hans':{'faithful':'标题。','interpretive':'标题。'}}
   self.assertIsNotNone(structure_layout.read_map(root,s,c))
   b['source']['bbox'][0]=41
   with self.assertRaisesRegex(ValueError,'stale'):structure_layout.read_map(root,s,c)
if __name__=='__main__':unittest.main()
