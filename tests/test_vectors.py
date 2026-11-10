"""Regression checks for vector crops and asset publication."""
import argparse,contextlib,io,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import translate as t,publishing,vector_assets as v
class VectorTests(unittest.TestCase):
 def test_visible_pixel_change_rejects_destructive_pruning(self):
  import fitz
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as folder,fitz.open() as doc:
   page=doc.new_page(width=100,height=100)
   page.draw_rect(fitz.Rect(20,20,80,80),color=None,fill=(0,0,0))
   def damaged_clip(target,rect):
    target.draw_rect(target.rect,color=None,fill=(1,1,1))
   with patch.object(fitz.Page,'clip_to_rect',damaged_clip):
    result=v.export_crop(page,[10,10,90,90],Path(folder)/'safe')
   self.assertFalse(result['metadata']['offscreen_content_pruned'])
   self.assertTrue(result['metadata']['pruning_rejected_visible_pixel_change'])
   with fitz.open(result['vector']) as svg:
    self.assertLess(max(svg[0].get_pixmap().pixel(30,30)[:3]),10)
 def test_pruned_crop_retains_inside_art_and_drops_offscreen_page_content(self):
  import fitz
  from PIL import Image
  with tempfile.TemporaryDirectory() as folder,fitz.open() as doc:
   p=doc.new_page(width=600,height=800)
   p.insert_text((22,50),'Outside header')
   p.insert_text((42,165),'Inside figure')
   p.draw_rect(fitz.Rect(30,130,190,200),color=(0,0,1))
   p.draw_rect(fitz.Rect(350,400,500,700),color=(1,0,0),fill=(1,0,0))
   stream=io.BytesIO();Image.new('RGB',(300,300),(0,255,0)).save(stream,'PNG')
   p.insert_image(fitz.Rect(350,50,550,250),stream=stream.getvalue())
   source=p.get_pixmap().samples
   result=v.export_crop(p,[20,120,210,215],Path(folder)/'compact')
   self.assertTrue(result['metadata']['offscreen_content_pruned'])
   with fitz.open(result['vector']) as svg:
    pix=svg[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
    self.assertGreater(sum(min(pix.pixel(x,y)[:3])<100 for x in range(20,350,3) for y in range(20,160,3)),40)
   self.assertLess(result['vector'].stat().st_size,60000)
   self.assertEqual(source,p.get_pixmap().samples)
 def test_active_and_external_svg_rejected(self):
  for body in ['<script>alert(1)</script>','<image href="https://example.org/a.png"/>','<path onload="alert(1)"/>','<path fill="url(https://example.org/p)"/>','<foreignObject><p>unsafe</p></foreignObject>']:
   with self.subTest(body=body),self.assertRaises(ValueError):v.validate_svg('<svg xmlns="'+v.SVG_NS+'">'+body+'</svg>')
 def test_internal_svg_references_allowed(self):
  d=v.validate_svg('<svg xmlns="'+v.SVG_NS+'"><defs><path id="p" d="M0 0L10 10"/></defs><use href="#p"/></svg>');self.assertEqual(d.tag,'{'+v.SVG_NS+'}svg')
 def test_actual_crop_publication_and_fallback_hash(self):
  import fitz
  with tempfile.TemporaryDirectory() as folder:
   r=Path(folder)/'project'
   with contextlib.redirect_stdout(io.StringIO()):t.init(argparse.Namespace(project=str(r),title='Vector test',languages='zh-Hans',style='editorial',page_size='A4',columns=1))
   d=fitz.open();pg=d.new_page(width=400,height=400);pg.draw_rect(fitz.Rect(45,50,330,260),color=(.1,.2,.3));pg.insert_text((60,90),'Input signal');source=r/'sources/D001.pdf';d.save(source);d.close()
   _,m,c=t.project(r);c['sources']=[{'id':'D001','name':'source.pdf','file':'sources/D001.pdf','sha256':t.sha(source)}];t.write(r/'content.json',c)
   with contextlib.redirect_stdout(io.StringIO()):t.crop(argparse.Namespace(project=str(r),document='D001',page=1,bbox='40,40,340,280',kind='image',width=150,caption='',format='auto'))
   _,m,c=t.project(r);b=c['blocks'][0];self.assertTrue(b['asset'].endswith('.svg'));self.assertGreater(b['vector']['svg_paths'],0);self.assertEqual(b['label_policy'],'unreviewed');html=publishing.block_html(r,b,'zh-Hans','faithful',publishing.LABELS['zh']);self.assertIn('data:image/svg+xml;base64,',html);self.assertIn('data-raster-fallback="data:image/png;base64,',html);(r/b['asset_fallback']).write_bytes(b'changed');self.assertIn('asset-fallback-hash',[e['code'] for e in t.audit_data(r,m,c)['errors']])
 def test_crop_defaults_to_source_width_and_relative_span(self):
  import fitz
  with tempfile.TemporaryDirectory() as folder:
   r=Path(folder)/'project'
   with contextlib.redirect_stdout(io.StringIO()):t.init(argparse.Namespace(project=str(r),title='Source scale',languages='zh-Hans',style='editorial',page_size='A4',columns=2))
   d=fitz.open();d.new_page(width=600,height=500);source=r/'sources/D001.pdf';d.save(source);d.close()
   _,_,c=t.project(r);c['sources']=[{'id':'D001','name':'source.pdf','file':'sources/D001.pdf','sha256':t.sha(source)}];t.write(r/'content.json',c)
   for bbox,width,expected_width,span in [('50,50,250,200',None,70.56,'column'),('50,50,450,200',None,141.11,'all'),('50,50,250,200',90,90,'column')]:
    with self.subTest(bbox=bbox,width=width):
     with contextlib.redirect_stdout(io.StringIO()):t.crop(argparse.Namespace(project=str(r),document='D001',page=1,bbox=bbox,kind='image',width=width,caption='',format='png'))
     _,_,content=t.project(r);b=content['blocks'][-1]
     self.assertEqual(b['width_mm'],expected_width);self.assertEqual(b['presentation']['span'],span)
 def test_rotated_crop_declines(self):
  import fitz
  d=fitz.open();p=d.new_page(width=400,height=300);p.draw_line((10,10),(100,100));p.set_rotation(90)
  with tempfile.TemporaryDirectory() as folder,self.assertRaises(ValueError):v.export_crop(p,[0,0,200,200],Path(folder)/'figure')
  d.close()
 def test_sparse_vector_inventory(self):
  import fitz
  d=fitz.open();p=d.new_page();p.draw_rect(fitz.Rect(50,60,260,200));r=v.inventory(p);self.assertEqual(r['vector_paths'],1);self.assertEqual(len(r['regions']),1);self.assertEqual(r['regions'][0]['review'],'unreviewed');d.close()
