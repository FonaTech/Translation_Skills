import argparse,contextlib,io,json,sys,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(R/'skills/document-translation/scripts'),str(R/'tools')]
import translate as t,publishing as p,install,fetch_pdf
class WorkflowTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.r=Path(self.tmp.name)/'project'
  with contextlib.redirect_stdout(io.StringIO()):t.init(argparse.Namespace(project=str(self.r),title='Fixture',languages='zh-Hans,ar',style='editorial',page_size='A4',columns=1))
 def tearDown(self):self.tmp.cleanup()
 def seed(self,text='Do not exceed 12.5 V.'):
  r,m,c=t.project(self.r);f=r/'sources/a.txt';f.write_text(text);c['sources']=[{'id':'D001','name':'a.txt','file':'sources/a.txt','sha256':t.sha(f)}];b=t.add_block(c,'D001','paragraph',{'element':'1'},[text]);t.write(r/'content.json',c);return r,m,c,b
 def apply(self,items,**extra):
  f=self.r/'packet.json';t.write(f,{'language':'zh-Hans','items':items,**extra})
  with contextlib.redirect_stdout(io.StringIO()):t.apply(argparse.Namespace(project=str(self.r),packet=str(f)))
 def test_safe_paths(self):
  with self.assertRaises(ValueError):t.safe(self.r,'../../escape')
  self.assertEqual(t.safe(self.r,'assets/x').parent,(self.r/'assets').resolve())
 def test_no_overwrite_init(self):
  with self.assertRaises(ValueError):t.init(argparse.Namespace(project=str(self.r)))
 def test_bcp47_and_rtl(self):
  _,m,_=t.project(self.r);self.assertEqual(m['direction']['ar'],'rtl');self.assertEqual(m['direction']['zh-Hans'],'ltr')
 def test_apply_atomic_on_missing_edition(self):
  r,m,c,b=self.seed();before=(r/'content.json').read_bytes();uid=b['units'][0]['id']
  with self.assertRaises(ValueError):self.apply([{'id':uid,'faithful':'电压不得超过 12.5 V。'}])
  self.assertEqual(before,(r/'content.json').read_bytes())
 def test_duplicate_unknown_id_atomic(self):
  r,m,c,b=self.seed();uid=b['units'][0]['id'];i={'id':uid,'faithful':'甲','interpretive':'乙'};before=(r/'content.json').read_bytes()
  for packet in [[i,i],[i,dict(i,id='unknown')]]:
   with self.assertRaises(ValueError):self.apply(packet)
   self.assertEqual(before,(r/'content.json').read_bytes())
 def test_reapplying_note_is_idempotent(self):
  r,m,c,b=self.seed();uid=b['units'][0]['id'];item={'id':uid,'faithful':'不得超过 12.5 V。','interpretive':'电压不得高于 12.5 V。','note':'Source wording retained.'}
  self.apply([item]);self.apply([item]);_,_,c=t.project(r)
  self.assertEqual(len(c['blocks'][0]['units'][0]['notes']),1)
 def test_reviewed_note_replacement_is_language_scoped_and_logged(self):
  r,m,c,b=self.seed();u=b['units'][0];uid=u['id'];u['notes']=[{'language':'zh-Hans','note':'Old paraphrase.'},{'language':'ar','note':'Keep Arabic.'}];t.write(r/'content.json',c);before=t.source_snap(m,c)
  item={'id':uid,'faithful':'不得超过 12.5 V。','interpretive':'电压不得高于 12.5 V。','replace_notes':['Verified source anomaly.']}
  self.apply([item]);_,m,c=t.project(r)
  self.assertEqual(t.source_snap(m,c),before)
  self.assertEqual([(n['language'],n['note']) for n in c['blocks'][0]['units'][0]['notes']],[('ar','Keep Arabic.'),('zh-Hans','Verified source anomaly.')])
  log=t.read(r/'reports/translation-applications.json')[-1]['note_replacements'][0]
  self.assertEqual(log['before'][0]['note'],'Old paraphrase.')
  self.apply([dict(item,replace_notes=[])]);_,_,c=t.project(r)
  self.assertEqual(c['blocks'][0]['units'][0]['notes'],[{'language':'ar','note':'Keep Arabic.'}])
 def test_invalid_note_replacement_is_atomic(self):
  r,m,c,b=self.seed();uid=b['units'][0]['id'];before=(r/'content.json').read_bytes()
  base={'id':uid,'faithful':'甲','interpretive':'乙'}
  for extra in [{'replace_notes':['']},{'replace_notes':['duplicate','duplicate']},{'replace_notes':None},{'replace_notes':[], 'note':'Both are ambiguous.'}]:
   with self.assertRaises(ValueError):self.apply([{**base,**extra}])
   self.assertEqual((r/'content.json').read_bytes(),before)
 def test_malformed_notes_block_build_before_browser_or_translation_mutation(self):
  r,m,c,b=self.seed();u=b['units'][0];uid=u['id']
  for lang in m['target_languages']:u['translations'][lang]={'faithful':'12.5 V','interpretive':'12.5 V'}
  for malformed in [['Source anomaly.'],[{'note':3}],[{'note':'  '}],None,[{'note':'Source anomaly.','language':False}]]:
   u['notes']=malformed;t.write(r/'content.json',c);before=(r/'content.json').read_bytes()
   self.assertTrue(any(x['code']=='invalid-notes' and x['id']==uid for x in t.audit_data(r,m,c)['errors']))
   with self.assertRaisesRegex(ValueError,'Build blocked'):p.build(r,browser='unavailable-test-browser')
   with self.assertRaisesRegex(ValueError,'Invalid existing notes'):self.apply([{'id':uid,'faithful':'甲','interpretive':'乙'}])
   self.assertEqual((r/'content.json').read_bytes(),before)
 def test_nonstring_or_blank_packet_note_is_atomic(self):
  r,m,c,b=self.seed();uid=b['units'][0]['id'];before=(r/'content.json').read_bytes()
  for bad in [None,False,{},['Source anomaly.'],'  ']:
   with self.assertRaisesRegex(ValueError,'note requires'):self.apply([{'id':uid,'faithful':'甲','interpretive':'乙','note':bad}])
   self.assertEqual((r/'content.json').read_bytes(),before)
 def test_source_freshness_and_translation_independence(self):
  r,m,c,b=self.seed();old=t.source_snap(m,c);c['blocks'][0]['units'][0]['translations']={'ar':{'faithful':'أ','interpretive':'ب'}}
  self.assertEqual(old,t.source_snap(m,c));c['blocks'][0]['units'][0]['source']='Different source';t.write(r/'content.json',c)
  with self.assertRaises(ValueError):self.apply([],source_hash=old)
 def test_source_hash_excludes_layout_only_metadata(self):
  r,m,c,b=self.seed();before=t.source_snap(m,c);b['presentation']={'role':'abstract','span':'all'};b['width_mm']=120;c['sources'][0]['display_title']='Edited title';c['sources'][0]['running_title']='Short title'
  self.assertEqual(before,t.source_snap(m,c));b['units'][0]['source']='Changed source';self.assertNotEqual(before,t.source_snap(m,c))
 def test_refinement_changes_presentation_only_and_rejects_text(self):
  import refinement
  r,m,c,b=self.seed();asset=r/'previews/source.png';asset.parent.mkdir(exist_ok=True);asset.write_text('source evidence');before=t.source_snap(m,c);translation={'zh-Hans':{'faithful':'不得超过12.5 V。','interpretive':'电压不应超过12.5 V。'}};b['units'][0]['translations']=translation;t.write(r/'content.json',c)
  patch=r/'patch.json';t.write(patch,{'reason':'The source paragraph is an abstract and should span the page.','evidence':['previews/source.png'],'documents':{'D001':{'columns':2}},'blocks':{b['id']:{'presentation':{'role':'abstract','span':'all'}}}})
  with contextlib.redirect_stdout(io.StringIO()):refinement.apply_patch(argparse.Namespace(project=str(r),patch=str(patch)))
  _,m,c=t.project(r);self.assertEqual(before,t.source_snap(m,c));self.assertEqual(c['blocks'][0]['units'][0]['translations'],translation)
  invalid=r/'invalid.json';t.write(invalid,{'reason':'Attempted translation mutation.','evidence':['previews/source.png'],'blocks':{b['id']:{'text':'Invented prose'}}});prior=(r/'content.json').read_bytes()
  with self.assertRaises(ValueError):refinement.apply_patch(argparse.Namespace(project=str(r),patch=str(invalid)))
  self.assertEqual(prior,(r/'content.json').read_bytes())
 def test_caption_binding_requires_unique_same_page_source(self):
  import refinement
  _,_,c,b=self.seed();img=t.add_block(c,'D001','image',{'page':1},[],asset='assets/f.png');caption=t.add_block(c,'D001','paragraph',{'page':1},['Figure one']);img['caption_block_ids']=[caption['id']];self.assertEqual(refinement.validate_blocks(c),[])
  other=t.add_block(c,'D001','paragraph',{'page':2},['Other caption']);img['caption_block_ids']=[other['id']];self.assertIn('invalid-caption-reference',[x['code'] for x in refinement.validate_blocks(c)])
  second=t.add_block(c,'D001','image',{'page':1},[],asset='assets/g.png');second['caption_block_ids']=[caption['id']];img['caption_block_ids']=[caption['id']];self.assertIn('duplicate-caption-binding',[x['code'] for x in refinement.validate_blocks(c)])
 def test_success_does_not_imply_review(self):
  r,m,c,b=self.seed();self.apply([{'id':b['units'][0]['id'],'faithful':'不得超过 12.5 V。','interpretive':'应将电压控制在 12.5 V 以内。'}]);self.assertFalse((r/'reports/reviews.json').exists())
 def test_task_context_includes_already_translated_heading(self):
  r,m,c,b=self.seed('Section heading');b['type']='heading';b['units'][0]['translations']={'zh-Hans':{'faithful':'节标题','interpretive':'节标题'}}
  following=t.add_block(c,'D001','paragraph',{'page':2},['Do not exceed 12.5 V.']);t.write(r/'content.json',c)
  with contextlib.redirect_stdout(io.StringIO()):t.tasks(argparse.Namespace(project=str(r),language='zh-Hans',size=6,all=False,max_chars=1000,context_chars=100))
  packet=t.read(r/'tasks/zh-Hans-0001.json');self.assertEqual(len(packet['items']),1);item=packet['items'][0]
  self.assertEqual(item['context']['preceding_heading'],'Section heading');self.assertEqual(item['context']['neighbors_for_context_only']['previous']['id'],b['units'][0]['id']);self.assertIn('12.5',item['source_checks']['numbers'])
 def test_task_character_budget_never_truncates_long_unit(self):
  import agent_packets
  items=[{'id':str(i),'source':text,'locator':{'document_id':doc}} for i,(doc,text) in enumerate([('D1','x'*10),('D1','y'*90),('D1','z'*250),('D2','w'*20)])]
  batches=list(agent_packets.batches(items,6,100));self.assertEqual([len(x) for x in batches],[2,1,1]);self.assertEqual(''.join(i['source'] for batch in batches for i in batch),''.join(i['source'] for i in items))
 def test_task_resume_index_excludes_completed_units(self):
  r,m,c,b=self.seed();self.apply([{'id':b['units'][0]['id'],'faithful':'不得超过 12.5 V。','interpretive':'电压应控制在 12.5 V 以内。'}])
  with contextlib.redirect_stdout(io.StringIO()):t.tasks(argparse.Namespace(project=str(r),language='zh-Hans',size=6,all=False))
  index=t.read(r/'tasks/zh-Hans-index.json');self.assertEqual(index['pending_units'],0);self.assertEqual(index['task_files'],[])
 def test_task_resume_keeps_empty_targets_pending(self):
  import agent_packets
  _,_,c,b=self.seed('Do not exceed 12.5 V.')
  u=b['units'][0]
  for value in ['', '  \n ', None, 0]:
   u['translations']={'zh-Hans':{'faithful':value,'interpretive':'电压不得超过12.5 V。'}}
   self.assertEqual(len(agent_packets.prepare(c,'zh-Hans',['faithful','interpretive'],False,lambda x:[x])),1)
  u['source']=''
  u['translations']={'zh-Hans':{'faithful':'','interpretive':''}}
  self.assertEqual(agent_packets.prepare(c,'zh-Hans',['faithful','interpretive'],False,lambda x:[x]),[])
 def test_zero_na_and_blank_distinct(self):
  r,m,c,b=self.seed('0 / N/A');u=b['units'][0];u['translations']={'zh-Hans':{'faithful':'0 / N/A','interpretive':'0 / N/A'},'ar':{'faithful':'0 / N/A','interpretive':'0 / N/A'}}
  self.assertFalse(t.audit_data(r,m,c)['errors']);self.assertEqual(u['source'],'0 / N/A')
 def test_numbers_warning_not_auto_correction(self):
  r,m,c,b=self.seed();u=b['units'][0];u['translations']={'zh-Hans':{'faithful':'不超过 125 V。','interpretive':'不超过 12.5 V。'}};a=t.audit_data(r,m,c)
  self.assertTrue(any(x['code']=='number-tokens' for x in a['warnings']));self.assertEqual(u['translations']['zh-Hans']['faithful'],'不超过 125 V。')
 def test_hash_change_detected(self):
  r,m,c,b=self.seed();(r/'sources/a.txt').write_text('Changed');self.assertTrue(any(x['code']=='source-hash' for x in t.audit_data(r,m,c)['errors']))
 def test_table_ids_unique_after_reorder(self):
  r,m,c,b=self.seed();tab=t.add_block(c,'D001','table',{'page':1},[],rows=[]);c['blocks'].remove(tab);x=t.add_block(c,'D001','paragraph',{'page':1},['Other']);c['blocks'].append(tab)
  self.assertEqual(len({z['id'] for z in c['blocks']}),len(c['blocks']))
 def test_empty_content_blocks_release(self):
  r,m,c=t.project(self.r);self.assertIn('empty-content',[x['code'] for x in t.audit_data(r,m,c)['errors']])
 def test_html_script_injection_escaped(self):
  text='<script>alert("source command")</script>';self.assertNotIn('<script>',p.h(text));parser=t.StaticHTML();parser.feed('<p>Keep me</p>'+text);parser.flush();self.assertEqual([x[1] for x in parser.blocks],['Keep me'])
 def test_visual_blank_detection_ignores_white_vector_fill(self):
  import fitz
  doc=fitz.open();page=doc.new_page();page.draw_rect(page.rect,color=None,fill=(1,1,1));self.assertTrue(p.page_is_visually_empty(page));page.draw_line((10,10),(100,100),color=(0,0,0));self.assertFalse(p.page_is_visually_empty(page));doc.close()
 def test_page_scope_validation(self):
  self.assertEqual(t.page_selection('1,3-4',4),[0,2,3]);self.assertRaises(ValueError,t.page_selection,'0',4);self.assertRaises(ValueError,t.page_selection,'5',4)
 def test_two_column_order(self):
  bs=[{'bbox':[310,y,580,y+20],'label':'R'+str(y)} for y in [50,80,110]]+[{'bbox':[20,y,280,y+20],'label':'L'+str(y)} for y in [50,80,110]]
  self.assertEqual([x['label'][0] for x in t.order_blocks(bs,600,'auto')],list('LLLRRR'))
 def test_two_columns_with_single_tall_block(self):
  bs=[{'bbox':[310,60,580,700],'label':'R'}]+[{'bbox':[20,y,280,y+90],'label':'L'} for y in [65,200,350]]
  self.assertEqual([x['label'] for x in t.order_blocks(bs,600,'auto')],list('LLLR'))
 def test_initials_and_figure_reference_stay_in_sentence(self):
  parts=t.split_text('L. Hemanth Krishna and B. Srinivasu use Fig. 13 for comparison. The second result follows.')
  self.assertEqual(len(parts),2);self.assertTrue(parts[0].startswith('L. Hemanth Krishna'));self.assertIn('Fig. 13',parts[0]);self.assertIn('The second result',parts[1])
 def test_sentence_before_protected_abbreviation_and_funding_numbers(self):
  self.assertEqual(t.split_text('One result is shown. Fig. 3 shows another. This is a result.'),['One result is shown.','Fig. 3 shows another.','This is a result.'])
  self.assertEqual(len(t.split_text('Supported by the foundation (Nos. 123 and 456), and a fellowship (NO. 789). The authors thank the facility.')),2)
 def test_review_becomes_stale(self):
  r,m,c,b=self.seed();old=t.snap(m,c);c['blocks'][0]['units'][0]['translations']['zh-Hans']={'faithful':'新','interpretive':'新'};self.assertNotEqual(old,t.snap(m,c))
 def test_minimum_and_maximum_abbreviations_keep_following_terms(self):
  self.assertEqual(t.split_text('The min. CGP is smaller than the max. CGP. This was measured.'),['The min. CGP is smaller than the max. CGP.','This was measured.'])
 def test_release_rejects_unreviewed(self):
  self.seed()
  with contextlib.redirect_stdout(io.StringIO()):code=t.release(argparse.Namespace(project=str(self.r),zip=None))
  self.assertEqual(code,1);self.assertFalse(t.read(self.r/'reports/release.json')['released'])
 def test_installer_four_clients_and_backup(self):
  home=Path(self.tmp.name)/'home';project=Path(self.tmp.name)/'client'
  for target in ['codex','claude','opencode','clouds']:
   dest=install.destinations(target,project,home,None);self.assertFalse(install.install(target,dest)['applied']);self.assertFalse(dest.exists());res=install.install(target,dest,True);self.assertTrue(res['applied']);self.assertTrue((dest/'SKILL.md').exists());res=install.install(target,dest,True);self.assertTrue(Path(res['backup']).exists())
   if target=='clouds':self.assertIn('runtime_contract:',(dest/'SKILL.md').read_text())
 def test_installer_symlink_not_followed(self):
  target=Path(self.tmp.name)/'real';target.mkdir();link=Path(self.tmp.name)/'sym';link.symlink_to(target,target_is_directory=True)
  self.assertRaises(ValueError,install.install,'codex',link,True)
 def test_expected_packet_coverage(self):
  r,m,c,b=self.seed();uid=b['units'][0]['id'];before=(r/'content.json').read_bytes()
  with self.assertRaises(ValueError):self.apply([],expected_ids=[uid])
  self.assertEqual(before,(r/'content.json').read_bytes())
 def test_glossary_advisory_preserves_text(self):
  import terminology
  r,m,c,b=self.seed('Keep user_id.');u=b['units'][0];u['translations']={'zh-Hans':{'faithful':'保留用户编号。','interpretive':'保留 user_id。'}};t.write(r/'content.json',c);g=r/'glossary.json';t.write(g,{'terms':[{'source':'user_id','targets':{'zh-Hans':['user_id']}}]});before=(r/'content.json').read_bytes();report=terminology.check(r,g)
  self.assertEqual(len(report['findings']),1);self.assertEqual(before,(r/'content.json').read_bytes())
 def complete_release_fixture(self):
  r,m,c,b=self.seed();u=b['units'][0];u['translations']={l:{'faithful':u['source'],'interpretive':u['source']} for l in m['target_languages']};t.write(r/'content.json',c)
  for l in m['target_languages']:
   (r/'outputs'/f'{l}-alignment.csv').write_text('unit_id,source,faithful,interpretive')
   for e in m['editions']+['alignment']:
    for ext in ['html','pdf']:(r/'outputs'/f'{l}-{e}.{ext}').write_text('Owned test artifact')
  records=[]
  for l in m['target_languages']:
   for e in m['editions']+['alignment']:
    h=r/'outputs'/f'{l}-{e}.html';p=h.with_suffix('.pdf');records.append({'file':h.name,'pdf':p.name,'html_sha256':t.sha(h),'pdf_sha256':t.sha(p)})
  t.write(r/'reports/layout.json',{'snapshot':t.snap(m,c),'pass':True,'outputs':[dict(x,pages=1,layout={'pages':[{'source_pages':['1'],'block_ids':[b['id']]}]}) for x in records]})
  import layout_engine,shutil
  t.write(r/'reports/layout-plan.json',layout_engine.plan(r,m,c));editor=layout_engine.ASSETS/'document-layout-editor.html';shutil.copy2(editor,r/'outputs/document-layout-editor.html');t.write(r/'reports/editor.json',{'sha256':t.sha(editor)})
  import fitz
  for lang in m['target_languages']:
   for ed in m['editions']+['alignment']:
    stem=f'{lang}-{ed}';folder=r/'reports/pages'/stem;folder.mkdir(parents=True,exist_ok=True);doc=fitz.open();doc.new_page().insert_text((40,40),'Rendered fixture');doc.save(r/'outputs'/f'{stem}.pdf');img=r/'previews'/f'{stem}.png';img.parent.mkdir(exist_ok=True);doc[0].get_pixmap().save(folder/'page-0001.png');doc.close()
    for rec in records:
     if rec['file']==stem+'.html':rec['pdf']=stem+'.pdf';rec['pdf_sha256']=t.sha(r/'outputs'/f'{stem}.pdf')
  source_preview=r/'previews/D001-p0001.png';doc=fitz.open();doc.new_page().get_pixmap().save(source_preview);doc.close()
  t.write(r/'reports/layout.json',{'snapshot':t.snap(m,c),'pass':True,'outputs':[dict(x,pages=1,layout={'pages':[{'source_pages':['1'],'block_ids':[b['id']]}]}) for x in records]})
  import publishing
  layout=t.read(r/'reports/layout.json');layout['pipeline_fingerprint']=publishing.pipeline_fingerprint();t.write(r/'reports/layout.json',layout)
  t.write(r/'reports/build.json',{'snapshot':t.snap(m,c),'pipeline_fingerprint':publishing.pipeline_fingerprint(),'artifacts':{f.name:t.sha(f) for f in (r/'outputs').iterdir() if f.suffix in {'.html','.csv'}}})
  manifests={
   'extraction':{'reviewer':'fixture','snapshot':t.snap(m,c),'summary':'Each source block and extracted locator checked.','block_reviews':[{'block_id':z['id'],'status':'checked','observation':'Fixture extraction locator inspected.'} for z in c['blocks']],'findings':[]},
   'semantic':{'reviewer':'fixture','snapshot':t.snap(m,c),'summary':'Both edition strings checked against the test source.','editions':m['editions'],'unit_reviews':[{'unit_id':v['id'],'faithful':'Compared.','interpretive':'Compared.','observation':'Fixture test.'} for _,v in t.units(c)],'findings':[]},
   'visual':{'reviewer':'fixture','snapshot':t.snap(m,c),'summary':'All rendered fixture pages compared.','pages':[],'source_evidence':[{'file':'previews/D001-p0001.png','sha256':t.sha(source_preview),'observation':'Synthetic fixture source page.'}],'findings':[]}}
  for rec in records:
   manifest=manifests['visual'];pdf=rec['pdf'];folder=r/'reports/pages'/Path(pdf).stem;manifest['pages'].append({'pdf':pdf,'page':1,'preview':f'reports/pages/{Path(pdf).stem}/page-0001.png','sha256':t.sha(folder/'page-0001.png'),'observation':'Synthetic fixture output page.','structural_status':'pass'})
  for kind,evidence in manifests.items():
   evidence_path=r/f'{kind}-evidence.json';t.write(evidence_path,evidence)
   with contextlib.redirect_stdout(io.StringIO()):t.review(argparse.Namespace(project=str(r),kind=kind,reviewer='fixture',scope='all',notes='Synthetic unit test record; not an actual document review.',evidence=str(evidence_path)))
  return r,m,c
 def release_report(self):
  with contextlib.redirect_stdout(io.StringIO()):code=t.release(argparse.Namespace(project=str(self.r),zip=None))
  return code,t.read(self.r/'reports/release.json')
 def test_release_complete_fixture_and_stale_pdf(self):
  r,m,c=self.complete_release_fixture();self.assertEqual(self.release_report()[0],0);(r/'outputs/zh-Hans-faithful.pdf').write_text('Changed artifact');code,report=self.release_report();self.assertEqual(code,1);self.assertIn('render-artifact-stale',[x['code'] for x in report['errors']]);self.assertIn('visual-review-stale',[x['code'] for x in report['errors']])
 def test_release_requires_alignment_artifacts(self):
  r,m,c=self.complete_release_fixture();(r/'outputs/zh-Hans-alignment.pdf').unlink();self.assertEqual(self.release_report()[0],1)
 def test_release_blocks_open_issues_and_unreviewed_labels(self):
  r,m,c=self.complete_release_fixture();asset=r/'assets/fixture.png';asset.write_bytes(b'test');t.add_block(c,'D001','image',{'page':1},[],asset='assets/fixture.png',label_policy='unreviewed');c['issues'].append({'status':'open','code':'ocr-required'});t.write(r/'content.json',c);code,report=self.release_report();codes=[x['code'] for x in report['errors']];self.assertIn('unresolved-source-issues',codes);self.assertIn('unreviewed-asset-labels',codes)
 def test_download_rejects_bad_schemes(self):
  for url in ['file:///private/file','https://user:pass@example.com/a.pdf','data:application/pdf,a']:
   self.assertRaises(ValueError,fetch_pdf.check_url,url)
if __name__=='__main__':unittest.main(verbosity=2)
