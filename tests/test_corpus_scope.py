"""Real temporary PDF fixtures verify sample scope without translation autofill."""
import argparse,contextlib,io,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'skills/document-translation/scripts')]
import pdf_corpus_regression as corpus
import translate as t
class CorpusScopeTests(unittest.TestCase):
 def make_pdf(self,root):
  import fitz
  p=root/'corpus';p.mkdir();d=fitz.open()
  for n in range(5):d.new_page().insert_text((45,70),f'Page {n+1}: Original source instruction. Do not exceed 12.5 V.')
  d.save(p/'source.pdf');d.close();return p
 def prepare(self,root,scope):
  src=self.make_pdf(root);out=root/'run'
  with contextlib.redirect_stdout(io.StringIO()):corpus.prepare(argparse.Namespace(pdf_root=str(src),output_root=str(out),count=1,seed=173,language='zh-Hans',scope=scope))
  return out,json.loads((out/'selection.json').read_text())
 def test_full_scope_ingests_every_source_page_without_translations(self):
  with tempfile.TemporaryDirectory() as name:
   out,m=self.prepare(Path(name),'full');self.assertEqual(m['samples'][0]['selected_pages'],[1,2,3,4,5]);self.assertFalse(m['semantic_translation_complete'])
   _,_,c=t.project(out/'sample-01');self.assertEqual({b['source']['page'] for b in c['blocks']},{1,2,3,4,5});self.assertTrue(all(not u['translations'] for _,u in t.units(c)))
 def test_first_middle_scope_is_explicit(self):
  with tempfile.TemporaryDirectory() as name:
   out,m=self.prepare(Path(name),'first-middle');self.assertEqual(m['samples'][0]['selected_pages'],[1,3]);self.assertEqual(m['scope'],'first-middle')
 def test_checker_rejects_partial_scope_marked_full(self):
  with tempfile.TemporaryDirectory() as name:
   out,m=self.prepare(Path(name),'first-middle');m['scope']='full';t.write(out/'selection.json',m)
   with contextlib.redirect_stdout(io.StringIO()):code=corpus.check(argparse.Namespace(output_root=str(out)))
   report=json.loads((out/'regression-report.json').read_text());self.assertEqual(code,1);codes={e['code'] for e in report['samples'][0]['errors']};self.assertIn('full-document-scope-incomplete',codes);self.assertIn('real-packet-coverage-missing',codes);self.assertFalse(report['pass'])
 def test_pdf_image_size_is_source_relative(self):
  import fitz
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);im=fitz.open();im.new_page(width=100,height=60).insert_text((5,25),'Plot');pix=im[0].get_pixmap();src=root/'source.pdf';d=fitz.open();p=d.new_page(width=600,height=800);p.insert_text((40,30),'Source');p.insert_image(fitz.Rect(40,80,250,206),pixmap=pix);p.insert_text((40,224),'Figure 1. Original plot.',fontsize=9);d.save(src);d.close();im.close();project=root/'project'
   with contextlib.redirect_stdout(io.StringIO()):
    t.init(argparse.Namespace(project=str(project),title='Fixture',languages='zh-Hans',style='editorial',page_size='A4',columns=1));t.ingest(argparse.Namespace(project=str(project),files=[str(src)],pages=None,password=None,order='auto',tables=False))
   _,_,c=t.project(project);b=next(b for b in c['blocks'] if b['type']=='image');self.assertAlmostEqual(b['width_mm'],74.1,places=1);self.assertEqual(b['presentation']['span'],'column')
if __name__=='__main__':unittest.main()
