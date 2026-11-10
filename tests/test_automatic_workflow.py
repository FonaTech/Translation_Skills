"""Owned fixtures exercise generic repairs, never private paper coordinates."""
import argparse,contextlib,copy,io,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import figure_learning as f,source_structure as s,translate as t,region_ocr,source_review,workflow

def line(i,text,x,y,w=160,block=0):
    return {'id':i,'text':text,'bbox':[x,y-11,x+w,y+3],'native_block':block,'size':9,'font':'Times-Roman','flags':0,'spans':[{'text':text,'size':9,'font':'Times-Roman','origin':[x,y]}]}

class AutomaticWorkflowTests(unittest.TestCase):
    def test_caption_baselines_allow_overlapping_ascent_boxes(self):
        a=line('a','Figure 3. Source caption',40,100);b=line('b','A continued source sentence.',40,110)
        self.assertTrue(f.continuation(a,b))
        decisions=[{'line_id':x['id'],'assigned_role':'caption'} for x in [a,b]]
        self.assertEqual(len(f.caption_groups({'lines':[b,a]},decisions)),1)

    def test_caption_stops_at_other_caption_and_explicit_section(self):
        a=line('a','Figure 1. A caption.',40,100)
        for text in ['Figure 2. Another caption.','Acknowledgements: Support.','References: [1] A. Author.']:
            self.assertFalse(f.continuation(a,line('b',text,40,110)))

    def test_shaped_caption_uses_shared_right_edge(self):
        a=line('a','Table 2. A source caption',160,100,120);b=line('b','The rest follows the shared right edge.',80,110,200)
        self.assertTrue(f.continuation(a,b))

    def test_numeric_scripts_follow_font_and_baseline_not_literal_tokens(self):
        a=line('a','10'+'6',40,100)
        a['spans']=[{'text':'10','size':9,'font':'Times-Roman','origin':[40,100]}, {'text':'6','size':6,'font':'Times-Roman','origin':[50,97]}]
        text,ops=s.typography_text(a);self.assertEqual(text,'10⁶');self.assertTrue(ops)
        a['spans'][1]['origin'][1]=100;self.assertEqual(s.typography_text(a)[0],'106')
        a['text']='´';a['spans']=[{'text':'´','font':'Times-Roman','size':9,'origin':[40,100]}]
        self.assertEqual(s.typography_text(a)[0],'´');a['spans'][0]['font']='SymbolMT';self.assertEqual(s.typography_text(a)[0],'×')

    def test_ocr_boxes_are_converted_before_table_assembly(self):
        items=[{'text':text,'confidence':.9,'bbox':[x,y,.15,.07]} for text,x,y in [('Name',.02,.8),('Value',.6,.8),('Limit',.02,.5),('12',.6,.5)]]
        rows,converted=region_ocr.grid(items,[100,200,300,400]);self.assertEqual([[c['text'] for c in row] for row in rows],[['Name','Value'],['Limit','12']])
        self.assertTrue(all(x['bbox_units']=='PDF page points; top-left' for x in converted))

    def project(self,root):
        with contextlib.redirect_stdout(io.StringIO()):t.init(argparse.Namespace(project=str(root),title='Fixture',languages='zh-Hans',style='editorial',page_size='A4',columns=1))
        r,m,c=t.project(root);(r/'sources/source.txt').write_text('Visible text.', encoding='utf-8');c['sources']=[{'id':'D001','file':'sources/source.txt','name':'source.txt','sha256':t.sha(r/'sources/source.txt')}]
        b=t.add_block(c,'D001','paragraph',{'element':'p1'},['Visible text.']);c['issues']=[{'code':'fixture-review','status':'open'}];t.write(r/'content.json',c);(r/'previews/source.txt').write_text('Original fixture evidence', encoding='utf-8');return r,m,c,b

    def test_source_review_is_atomic_and_rejects_stale_packets(self):
        with tempfile.TemporaryDirectory() as d:
            r,m,c,b=self.project(Path(d)/'project');packet={'source_hash':t.source_snap(m,c),'reviewer':'test agent','evidence':['previews/source.txt'],'operations':[{'op':'correct-unit','unit_id':b['units'][0]['id'],'before':'Visible text.','after':'Correct visible text.','observation':'Source image explicitly contains the additional word.'},{'op':'unsupported','observation':'An invalid action must not partially apply.'}]}
            p=r/'tasks/checked.json';t.write(p,packet)
            with self.assertRaises(ValueError):source_review.apply(r,p)
            self.assertEqual(t.read(r/'content.json'),c)
            packet['operations']=packet['operations'][:1];t.write(p,packet);source_review.apply(r,p)
            with self.assertRaises(ValueError):source_review.apply(r,p)

    def test_workflow_requests_agent_review_without_certifying(self):
        with tempfile.TemporaryDirectory() as d:
            r,m,c,b=self.project(Path(d)/'project')
            with contextlib.redirect_stdout(io.StringIO()):workflow.run(argparse.Namespace(project=str(r),advance=False,browser=None))
            result=t.read(r/'reports/workflow.json');self.assertEqual(result['stage'],'source-review');self.assertFalse(result['complete']);self.assertFalse(result['external_model_required'])
            packet=t.read(r/'tasks/source-review.json');self.assertEqual(packet['operations'],[]);self.assertEqual(packet['reviewer'],'')

    def test_shared_caption_requires_explicit_same_figure_group(self):
        from refinement import validate_blocks
        c={'sources':[{'id':'D001'}],'blocks':[]};cap=t.add_block(c,'D001','paragraph',{'page':1},['Figure 1. A plate.'])
        for _ in range(2):t.add_block(c,'D001','image',{'page':1},[],caption_block_ids=[cap['id']],figure_group_id=cap['id'])
        self.assertEqual(validate_blocks(c),[]);c['blocks'][-1].pop('figure_group_id');self.assertTrue(validate_blocks(c))

    def test_caption_label_stays_with_its_sentence(self):
        self.assertEqual(t.split_text('Fig. 12. Complete source caption. Next sentence.'),['Fig. 12. Complete source caption.','Next sentence.'])

    def test_owned_images_preserve_overlapping_panels_without_neighbor(self):
        import fitz
        from PIL import Image
        from vector_assets import source_crop_page
        with tempfile.TemporaryDirectory() as d,fitz.open() as doc:
            d=Path(d);Image.new('RGB',(40,40),'red').save(d/'a.png');Image.new('RGB',(40,40),'blue').save(d/'b.png')
            p=doc.new_page(width=200,height=200);a=p.insert_image(fitz.Rect(10,10,110,110),filename=str(d/'a.png'));p.insert_image(fitz.Rect(90,20,190,120),filename=str(d/'b.png'))
            original=p.get_pixmap().samples
            with source_crop_page(p,raster_xrefs=[a]) as isolated:
                pix=isolated.get_pixmap();im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                self.assertEqual(im.getpixel((105,50)),(255,0,0));self.assertEqual(im.getpixel((150,50)),(255,255,255))
            self.assertEqual(p.get_pixmap().samples,original)

    def test_host_agent_can_transcribe_table_without_local_ocr(self):
        with tempfile.TemporaryDirectory() as d:
            r,m,c,b=self.project(Path(d)/'project');b['presentation']={'role':'caption'};b['source']['page']=1;t.write(r/'content.json',c)
            f='reports/region-ocr/proposal.json';t.write(r/f,{'kind':'raster-table','caption_block_id':b['id'],'source_page':1,'bbox':[10,20,90,60]})
            packet={'source_hash':t.source_snap(m,c),'reviewer':'fixture agent','evidence':['previews/source.txt',f],'operations':[{'op':'transcribe-table','evidence_file':f,'rows':[['Label','Value'],['Empty','']],'observation':'Observed two columns and an explicitly blank last cell.'}]};p=r/'tasks/checked.json';t.write(p,packet);source_review.apply(r,p)
            _,m,c=t.project(r);table=next(x for x in c['blocks'] if x['type']=='table');self.assertEqual([u['source'] for u in table['units']],['Label','Value','Empty',''])
            packet['source_hash']=t.source_snap(m,c);t.write(p,packet)
            with self.assertRaises(ValueError):source_review.apply(r,p)

    def test_pdf_scan_transcription_is_rejected_without_changing_source(self):
        import fitz
        with tempfile.TemporaryDirectory() as d:
            r,m,c,b=self.project(Path(d)/'project');pdf=r/'sources/scan.pdf'
            with fitz.open() as doc:
                doc.new_page(width=200,height=300);doc.save(pdf)
            c['sources'][0].update(file='sources/scan.pdf',name='scan.pdf',sha256=t.sha(pdf),page_count=1);c['blocks']=[];t.write(r/'content.json',c)
            (r/'previews/D001-p0001.png').write_bytes(b'owned inspected preview fixture')
            op={'op':'transcribe-page','document_id':'D001','page':1,'evidence_file':'previews/D001-p0001.png','regions':[{'text':'Only visible source text.','bbox':[10,20,180,55],'type':'heading','level':1}],'observation':'Read the visible heading directly from the source-page preview.'}
            packet={'source_hash':t.source_snap(m,c),'reviewer':'test agent','evidence':['previews/D001-p0001.png'],'operations':[op]};p=r/'tasks/scan.json';t.write(p,packet)
            with self.assertRaisesRegex(ValueError,'PDF OCR/transcription is disabled'):source_review.apply(r,p)
            self.assertEqual(t.read(r/'content.json'),c)

    def test_heading_alignment_keeps_next_and_preserves_separate_notes(self):
        import publishing
        b={'id':'b','type':'heading','source':{'document_id':'D001','page':1}}
        u={'id':'u','source':'Original.','translations':{'zh-Hans':{'faithful':'忠实。','interpretive':'译写。'}},'notes':[{'language':'zh-Hans','note':'Source discrepancy.'}]}
        out=publishing.alignment_pair(b,u,'zh-Hans',['faithful','interpretive'],publishing.LABELS['zh'],last_in_block=True)
        self.assertIn('data-keep-next="true"',out);self.assertIn('Source discrepancy.',out);self.assertIn('<aside class="editor-note">',out)

    def test_changed_render_artifacts_invalidate_review_and_build(self):
        import publishing
        with tempfile.TemporaryDirectory() as d:
            r,m,c,b=self.project(Path(d)/'project');inventory={}
            for ed in m['editions']+['alignment']:
                f=f'zh-Hans-{ed}.html';(r/'outputs'/f).write_text(ed, encoding='utf-8');inventory[f]=t.sha(r/'outputs'/f)
            t.write(r/'reports/build.json',{'snapshot':t.snap(m,c),'pipeline_fingerprint':publishing.pipeline_fingerprint(),'artifacts':inventory})
            self.assertTrue(publishing.artifacts_current(r,m,c,'build'))
            (r/'outputs/zh-Hans-faithful.html').write_text('Changed output', encoding='utf-8')
            self.assertFalse(publishing.artifacts_current(r,m,c,'build'))
            self.assertFalse(workflow.valid_review(r,m,c,'visual',{'kind':'visual','snapshot':t.snap(m,c),'scope':'all','evidence':{}}))

    def test_non_pdf_source_can_enter_visual_review(self):
        import review_evidence
        with tempfile.TemporaryDirectory() as d:
            r,m,c,b=self.project(Path(d)/'project');t.write(r/'reports/layout.json',{'snapshot':t.snap(m,c),'outputs':[]})
            out=r/'tasks/visual.json'
            with contextlib.redirect_stdout(io.StringIO()):review_evidence.create(r,'visual',out)
            self.assertEqual(t.read(out)['source_evidence'][0]['file'],'sources/source.txt')
            self.assertEqual(t.read(out)['source_evidence'][0]['observation'],'')
