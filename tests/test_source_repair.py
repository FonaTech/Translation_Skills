import argparse
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import translate as t
import source_repair
import publishing

class SourceRepairTests(unittest.TestCase):
 def fixture(self,root):
  r=root/'project'
  with contextlib.redirect_stdout(io.StringIO()):t.init(argparse.Namespace(project=str(r),title='Visible fragments',languages='zh-Hans',style='editorial',page_size='A4',columns=2))
  _,m,c=t.project(r)
  c['sources']=[{'id':'D001','name':'source.pdf','file':'sources/D001.pdf','sha256':'0'*64}]
  t.add_block(c,'D001','paragraph',{'page':1,'bbox':[0,0,10,10]},['The observed signal'])
  t.add_block(c,'D001','paragraph',{'page':1},['Page furniture'],presentation={'role':'metadata'})
  t.add_block(c,'D001','paragraph',{'page':2,'bbox':[0,0,10,10]},['remains unchanged.'])
  t.add_block(c,'D001','paragraph',{'page':2},[])
  t.write(r/'content.json',c);(r/'previews/source.png').write_bytes(b'inspected-image-fixture')
  ids=[c['blocks'][i]['units'][0]['id'] for i in [0,2]]
  p={'source_hash':t.source_snap(m,c),'reviewer':'fixture inspector','reason':'The sentence visibly crosses a page.','evidence':['previews/source.png'],'merges':[{'unit_ids':ids,'observation':'End of page 1 continues at start of page 2.'}]}
  return r,m,c,p
 def apply(self,r,p):
  packet=r/'join.json';t.write(packet,p)
  with contextlib.redirect_stdout(io.StringIO()):source_repair.join(argparse.Namespace(project=str(r),packet=str(packet)))
 def test_join_is_exact_with_new_id_and_each_original_locator(self):
  with tempfile.TemporaryDirectory() as folder:
   r,m,c,p=self.fixture(Path(folder));self.apply(r,p);_,_,joined=t.project(r)
   b=joined['blocks'][0];u=b['units'][0]
   self.assertEqual(u['source'],'The observed signal remains unchanged.')
   self.assertNotIn(u['id'],p['merges'][0]['unit_ids'])
   self.assertEqual([s['unit_id'] for s in u['source_segments']],p['merges'][0]['unit_ids'])
   self.assertEqual([s['locator']['page'] for s in u['source_segments']],[1,2])
   self.assertEqual(publishing.loc(b),'D001 · p1,2')
   self.assertEqual(joined['blocks'][-1],c['blocks'][-1])
   self.assertEqual(joined['blocks'][1],c['blocks'][1])
   self.assertEqual(len(joined['extraction_corrections'][-1]['joins']),1)
 def test_invalid_second_join_leaves_original_bytes_unchanged(self):
  with tempfile.TemporaryDirectory() as folder:
   r,m,c,p=self.fixture(Path(folder));before=(r/'content.json').read_bytes()
   p['merges'].append(copy.deepcopy(p['merges'][0]))
   with self.assertRaises(ValueError):self.apply(r,p)
   self.assertEqual((r/'content.json').read_bytes(),before)
 def test_empty_separator_preserves_split_identifier_without_new_words(self):
  with tempfile.TemporaryDirectory() as folder:
   r,m,c,p=self.fixture(Path(folder));c['blocks'][0]['units'][0]['source']='https://doi.org/';c['blocks'][2]['units'][0]['source']='10.0000/example'
   t.write(r/'content.json',c);p['source_hash']=t.source_snap(m,c);p['merges'][0]['separators']=[''];self.apply(r,p)
   self.assertEqual(t.project(r)[2]['blocks'][0]['units'][0]['source'],'https://doi.org/10.0000/example')
 def test_nonwhitespace_separator_is_rejected(self):
  with tempfile.TemporaryDirectory() as folder:
   r,m,c,p=self.fixture(Path(folder));p['merges'][0]['separators']=[' invented '];before=(r/'content.json').read_bytes()
   with self.assertRaises(ValueError):self.apply(r,p)
   self.assertEqual((r/'content.json').read_bytes(),before)
 def test_reference_join_refreshes_existing_parser_handoff(self):
  import fitz,structure_layout
  with tempfile.TemporaryDirectory() as folder:
   r,m,c,p=self.fixture(Path(folder));pdf=fitz.open();pdf.new_page();pdf.new_page();pdf.save(r/'sources/D001.pdf');pdf.close()
   for i in [0,2]:c['blocks'][i]['type']='reference';c['blocks'][i]['presentation']={'role':'bibliography'}
   c['sources'][0]['sha256']=t.sha(r/'sources/D001.pdf');structure_layout.write_map(r,c,c['sources'][0])
   t.write(r/'content.json',c);p['source_hash']=t.source_snap(m,c);self.apply(r,p)
   _,_,result=t.project(r);self.assertIsNotNone(structure_layout.read_map(r,result['sources'][0],result))
   self.assertEqual(result['blocks'][0]['type'],'reference')
 def test_stale_or_translated_or_skipped_narrative_is_rejected(self):
  for case in ['stale','translated','skipped','reversed','cross-document']:
   with self.subTest(case=case),tempfile.TemporaryDirectory() as folder:
    r,m,c,p=self.fixture(Path(folder))
    if case=='stale':p['source_hash']='stale'
    if case=='translated':c['blocks'][0]['units'][0]['translations']={'zh-Hans':{'faithful':'已有译文','interpretive':'已有译文'}}
    if case=='skipped':c['blocks'][1].pop('presentation')
    if case=='reversed':p['merges'][0]['unit_ids'].reverse()
    if case=='cross-document':c['blocks'][2]['source']['document_id']='D002'
    t.write(r/'content.json',c)
    if case!='stale':p['source_hash']=t.source_snap(m,c)
    before=(r/'content.json').read_bytes()
    with self.assertRaises(ValueError):self.apply(r,p)
    self.assertEqual((r/'content.json').read_bytes(),before)

 def test_replacement_text_and_malformed_evidence_are_atomic(self):
  for case in ['replacement-packet','replacement-merge','missing-evidence','string-evidence','missing-file','path-escape','bad-reviewer','bad-reason','bad-observation','unhashable-id']:
   with self.subTest(case=case),tempfile.TemporaryDirectory() as folder:
    r,m,c,p=self.fixture(Path(folder));before=(r/'content.json').read_bytes()
    if case=='replacement-packet':p['source']='An invented completion.'
    if case=='replacement-merge':p['merges'][0]['source']='An invented completion.'
    if case=='missing-evidence':p['evidence']=[]
    if case=='string-evidence':p['evidence']='previews/source.png'
    if case=='missing-file':p['evidence']=['previews/missing.png']
    if case=='path-escape':p['evidence']=['../outside.png']
    if case=='bad-reviewer':p['reviewer']=['inspector']
    if case=='bad-reason':p['reason']=None
    if case=='bad-observation':p['merges'][0]['observation']={'claim':'reviewed'}
    if case=='unhashable-id':p['merges'][0]['unit_ids'].append({})
    with self.assertRaises(ValueError):self.apply(r,p)
    self.assertEqual((r/'content.json').read_bytes(),before)
 def test_nested_join_retains_original_segments_and_unit_locator(self):
  with tempfile.TemporaryDirectory() as folder:
   r,m,c,p=self.fixture(Path(folder))
   t.add_block(c,'D001','paragraph',{'page':3},['under the tested conditions.'])
   t.write(r/'content.json',c);p['source_hash']=t.source_snap(m,c);self.apply(r,p)
   _,m,c=t.project(r);first=c['blocks'][0]['units'][0];last=c['blocks'][-1]['units'][0]
   original_ids=[*p['merges'][0]['unit_ids'],last['id']]
   p['source_hash']=t.source_snap(m,c);p['merges']=[{'unit_ids':[first['id'],last['id']],'observation':'Second inspected continuation; retain all earlier segment IDs.'}]
   self.apply(r,p);_,m,c=t.project(r);b=c['blocks'][0];u=b['units'][0]
   self.assertEqual(u['source'],'The observed signal remains unchanged. under the tested conditions.')
   self.assertEqual([s['unit_id'] for s in u['source_segments']],original_ids)
   self.assertEqual(publishing.source_pages(b),[1,2,3])
   u['translations']={'zh-Hans':{'faithful':'已观察信号在测试条件下保持不变。','interpretive':'已观察信号在测试条件下保持不变。'}}
   html=publishing.alignment_pair(b,u,'zh-Hans',['faithful','interpretive'],publishing.LABELS['zh'])
   self.assertIn('data-source-pages="1,2,3"',html)
   self.assertIn('D001 · p1,2,3',html)
   self.assertIn('data-source-pages="1,2,3"',publishing.uspan(u,'zh-Hans','faithful'))
