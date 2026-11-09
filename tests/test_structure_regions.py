"""Original fixtures for code, spatial math and note ownership (MIT)."""
import copy,gzip,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'skills/document-translation/scripts')]
import source_structure as s
import structure_regions as r
import train_structure_regions as region_trainer
import structure_ingest as ingest
import translate as t
import publishing
from test_source_structure import line


def styled(lid,text,x,y,size=10,font='Times-Roman',block=0,index=0):
    a=line(lid,text,x,y,min(230,max(12,len(text)*size*.45)),block,index)
    a.update(size=size,font=font);a['bbox'][3]=y+size
    a['spans']=[{'text':text,'size':size,'font':font,'flags':0,'bbox':a['bbox'][:],'origin':[x,y+size*.8]}]
    return a


def note(lid='note',marker='10',x=40,y=600):
    a=styled(lid,marker+'Original source note.',x,y,8)
    a['spans']=[{'text':marker,'size':7,'font':'Times-Roman','flags':0,'bbox':[x,y-2,x+5,y+5],'origin':[x,y+3]},
                {'text':'Original source note.','size':8,'font':'Times-Roman','flags':0,'bbox':[x+6,y,x+140,y+8],'origin':[x+6,y+6.4]}]
    return a


def page(rows):return {'page':3,'width':600,'height':800,'lines':rows,'table_regions':[],'raw_sha256':s.digest(rows)}
def profile(p):
    d=s.document_profile([p]);d.update(body_size=10);return d

def decisions(rows):return {a['id']:{'line_id':a['id'],'assigned_role':'body','review_required':True} for a in rows}
def probabilities(kinds):
    return [[.999 if k==kind else .001/(len(r.CLASSES)-1) for k in r.CLASSES] for kind in kinds]


class RegionsTests(unittest.TestCase):
    def test_specialist_ignores_missing_and_unresolved_labels(self):
        rows=[styled(str(i),'An original source paragraph.',40,100+i*14) for i in range(4)]
        for row in rows:row.update(_specialist='prose',_group=row['id'])
        rows[1].pop('_specialist');rows[2]['_specialist_unresolved']=True;rows[3]['_role_unresolved']=True
        p=page(rows)
        samples=region_trainer.examples([{'id':'masks','pages':[p],'profile':profile(p)}])
        self.assertEqual([x['id'] for x in samples],['0'])

    def test_specialist_separates_test_from_development_validation(self):
        def doc(name,split,identity,parents=None):
            return {'id':name,'split':split,'source_sha256':identity*64,
                    'source_parent_sha256':parents or [],'pages':[]}
        docs=[doc('fit','train','a'),doc('dev','validation','b'),doc('blind','test','c')]
        groups=region_trainer.partition_documents(docs,{})
        self.assertEqual([d['id'] for d in groups['validation']],['dev'])
        self.assertEqual([d['id'] for d in groups['test']],['blind'])
        with self.assertRaisesRegex(ValueError,'base model'):
            region_trainer.partition_documents(docs,{'training':{'real_train_source_sha256':['c'*64]}})
        derived=doc('derived','test','d',['a'*64])
        with self.assertRaisesRegex(ValueError,'source family'):
            region_trainer.partition_documents(docs+[derived],{})

    def test_wider_region_head_has_requested_parameter_shape(self):
        samples=[]
        for i in range(4):
            features=[0.0]*len(r.FEATURES);features[i]=float(i+1)
            samples.append({'x':features,'y':i%2,'cost':[0.0]*len(r.CLASSES),
                            'importance':1.0,'group':str(i)})
        network,_=region_trainer.fit(samples,173,1,hidden=128)
        self.assertEqual(len(network['mean']),len(r.FEATURES))
        self.assertEqual(len(network['weights'][0]),128)
        with self.assertRaisesRegex(ValueError,'Hidden units'):
            region_trainer.fit(samples,173,1,hidden=513)

    def test_feature_contract_is_finite_and_source_only(self):
        rows=[styled('a','An original measured value remains unchanged.',40,100),note()];p=page(rows);pr=profile(p)
        context=r.context(p,pr);a=r.features(rows[0],p,pr,context)
        self.assertEqual(len(a),len(r.FEATURES))
        annotated=copy.deepcopy(p)
        for row in annotated['lines']:row.update(_specialist='incorrect',_role='equation',_group='false')
        self.assertEqual(a,r.features(annotated['lines'][0],annotated,pr,r.context(annotated,pr)))

    def test_code_assignment_is_not_math_despite_equals(self):
        rows=[styled('a','module original(a);',40,100,font='CourierNew'),styled('b','begin : named a = b & ~c;',60,115,font='CourierNew'),styled('c','endmodule',40,130,font='CourierNew')]
        p=page(rows);pr=profile(p);ds=decisions(rows)
        ctx,_=r.refine(rows,p,pr,ds,{'network':{},'threshold':.9},lambda *args:probabilities(['code']*3))
        groups=r.structured_groups(rows,ds,ctx)
        self.assertEqual(len(groups),1);self.assertEqual(groups[0]['kind'],'code')
        self.assertEqual([x['text'] for x in groups[0]['members']],[x['text'] for x in rows])
        self.assertEqual(groups[0]['members'][1]['bbox'][0],60)

    def test_damaged_code_seed_is_retained_but_never_promoted_or_propagated(self):
        rows=[styled('bad','module \x03original(a);',40,100,font='CourierNew'),
              styled('end','}',40,115,font='CourierNew')]
        p=page(rows);pr=profile(p);ds=decisions(rows)
        ctx,proposals=r.refine(rows,p,pr,ds,{'network':{},'threshold':.9},
                               lambda *args:probabilities(['code','code']))
        self.assertIn('unresolved-native-glyph',proposals['bad']['blocked_by'])
        self.assertFalse(proposals['bad']['applied'])
        self.assertNotEqual(ds['bad'].get('semantic_role'),'code')
        self.assertNotEqual(ds['end'].get('semantic_role'),'code')
        self.assertFalse(r.structured_groups(rows,ds,ctx))

    def test_prose_between_examples_prevents_code_bridge(self):
        rows=[styled('a','module original(a);',40,100,font='CourierNew'),styled('p','The next independent example starts below.',40,120),styled('b','module another(b);',40,140,font='CourierNew')]
        ctx=r.context(page(rows),profile(page(rows)))
        self.assertNotEqual(ctx['a']['code_group'],ctx['b']['code_group']);self.assertIsNone(ctx['p']['code_group'])

    def test_monospaced_table_is_not_code(self):
        rows=[styled('a','Value    Range    Error',40,100,font='CourierNew'),styled('b','12.5     0-20     0.2',40,112,font='CourierNew')]
        p=page(rows);self.assertTrue(all(not x['code_group'] for x in r.context(p,profile(p)).values()))

    def test_same_native_block_does_not_assign_small_note_to_list(self):
        a=styled('list','(3) Preserve the source.',310,590,block=8);n=note(y=590);n['native_block']=8
        tail=styled('tail','and its qualification.',40,602,8,block=8,index=2)
        p=page([a,n,tail]);ctx=r.context(p,profile(p))
        self.assertTrue(ctx['list']['list_chain']);self.assertFalse(ctx['tail']['list_chain'])
        self.assertEqual(ctx['note']['note_group'],ctx['tail']['note_group'])

    def test_note_seed_decodes_complete_aligned_chain(self):
        rows=[note(),styled('tail','with the original qualification.',40,612,8)]
        p=page(rows);ds=decisions(rows)
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},lambda *args:probabilities(['footnote','retain']))
        groups=r.structured_groups(rows,ds,ctx)
        self.assertEqual(len(groups),1);self.assertEqual(len(groups[0]['members']),2)
        self.assertEqual(ds['tail']['rule'],'learned-seed-with-source-region-chain')

    def test_damaged_footnote_seed_cannot_claim_clean_continuation(self):
        damaged=note();damaged['text']='10Original source \x03 note.'
        rows=[damaged,styled('tail','with a separate qualification.',40,612,8)]
        p=page(rows);pr=profile(p);ds=decisions(rows)
        ctx,proposals=r.refine(rows,p,pr,ds,{'network':{},'threshold':.9},
                               lambda *args:probabilities(['footnote','footnote']))
        self.assertIsNone(ctx[damaged['id']]['note_group'])
        self.assertIsNone(ctx[rows[1]['id']]['note_group'])
        self.assertFalse(proposals[damaged['id']]['applied'])
        self.assertNotEqual(ds[rows[1]['id']].get('semantic_role'),'footnote')

    def test_next_marker_starts_a_distinct_note(self):
        rows=[note('a','10'),note('b','11',y=625),styled('tail','Its continuation.',40,637,8)]
        ctx=r.context(page(rows),profile(page(rows)))
        self.assertNotEqual(ctx['a']['note_group'],ctx['b']['note_group']);self.assertEqual(ctx['tail']['note_group'],ctx['b']['note_group'])

    def test_note_matches_actual_marker_and_rejects_fraction_exponent(self):
        n=note(marker='1');anchor=styled('a','The observation.1',300,150)
        anchor['spans'].append({'text':'1','size':7,'font':'Times-Roman','bbox':[400,147,405,154],'origin':[400,152]})
        exponent=styled('e','S1/2',40,100)
        exponent['spans']=[{'text':'S','font':'CambriaMath','size':10,'bbox':[40,100,45,110],'origin':[40,108]},
                            {'text':'1','font':'Times-Roman','size':7,'bbox':[45,97,49,104],'origin':[45,103]},
                            {'text':'/2','font':'CambriaMath','size':7,'bbox':[49,97,56,104],'origin':[49,103]}]
        groups=[{'id':'footnote:n','kind':'footnote','members':[n]}]
        rel=r.note_anchors(groups,[n,anchor,exponent])[0]
        self.assertEqual([a['line_id'] for a in rel['anchors']],['a']);self.assertEqual(rel['status'],'source-marker-matched')

    def test_footnote_marker_before_math_variable_is_not_rejected_as_exponent(self):
        n=note(marker='8')
        anchor=styled('a','finds8 J = E',300,150)
        anchor['spans']=[
            {'text':'finds','size':10,'font':'CMR10','bbox':[300,150,327,160],'origin':[300,158]},
            {'text':'8','size':7,'font':'CMR6','bbox':[327,147,331,154],'origin':[327,153]},
            {'text':'J','size':10,'font':'CMMI10','bbox':[332,150,338,160],'origin':[332,158]},
            {'text':' = E','size':10,'font':'CMMI10','bbox':[338,150,355,160],'origin':[338,158]}]
        groups=[{'id':'footnote:n','kind':'footnote','members':[n]}]
        rel=r.note_anchors(groups,[n,anchor])[0]
        self.assertEqual(rel['status'],'source-marker-matched')

    def test_damaged_source_line_cannot_be_confirmed_as_a_footnote_anchor(self):
        n=note(marker='1')
        anchor=styled('damaged','The observation.\x031',300,150)
        anchor['spans'].append({'text':'1','size':7,'font':'Times-Roman','bbox':[400,147,405,154],'origin':[400,152]})
        groups=[{'id':'footnote:n','kind':'footnote','members':[n]}]
        rel=r.note_anchors(groups,[n,anchor])[0]
        self.assertEqual(rel['status'],'unresolved-no-source-marker')
        self.assertEqual(rel['anchors'],[])

    def test_duplicate_markers_are_ambiguous_not_verified_ownership(self):
        n=note();anchors=[]
        for i in range(2):
            a=styled(str(i),'The source note.10',300,100+i*20)
            a['spans'].append({'text':'10','size':7,'font':'Times-Roman','bbox':[400,97+i*20,407,104+i*20],'origin':[400,102+i*20]});anchors.append(a)
        rel=r.note_anchors([{'id':'n','kind':'footnote','members':[n]}],[n]+anchors)[0]
        self.assertEqual(rel['status'],'ambiguous-multiple-source-markers')

    def test_formula_retains_denominator_as_spatial_member(self):
        rows=[styled('n','−ℏ²',140,200,font='CambriaMath'),styled('d','2 m',140,215,8),styled('eq','d² ψ = E ψ',180,207,font='CambriaMath'),styled('num','(2.1)',400,207)]
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertEqual(len({ctx[x['id']]['math_group'] for x in rows}),1)
        ds=decisions(rows)
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},lambda *args:probabilities(['math','retain','retain','retain']))
        ds['d']['review_required']=True
        group=r.structured_groups(rows,ds,ctx)[0]
        self.assertEqual(group['representation'],'source-spatial-region');self.assertEqual(len(group['members']),4)

    def test_numbered_equation_envelope_keeps_damaged_glyphs_without_transcribing(self):
        rows=[styled('math','x = y',100,200,font='Times-Roman'),
              styled('fragment',chr(16),145,200,font='MTEXNC01'),
              styled('number','(4.2)',510,200,font='Times-Roman')]
        p=page(rows);pr=profile(p);ctx=r.context(p,pr)
        self.assertEqual(ctx['math']['math_group'],ctx['fragment']['math_group'])
        ds=decisions(rows)
        ctx,_=r.refine(rows,p,pr,ds,{'network':{},'threshold':.9},lambda *args:probabilities(['math']*3))
        groups=r.structured_groups(rows,ds,ctx)
        self.assertEqual(len(groups),1)
        damaged=next(row for row in groups[0]['members'] if row['id']=='fragment')
        self.assertEqual(damaged['text'],chr(16))
        self.assertTrue(ds['fragment']['review_required'])
        self.assertEqual(ds['fragment']['rule'],'source-spatial-equation-region-unresolved-glyph')

    def test_unnumbered_math_font_fragment_joins_spatial_region_but_stays_unresolved(self):
        rows=[styled('math','∇ρ = 0',220,200,font='CambriaMath'),
              styled('fragment',chr(16),243,200,font='MTEXNC01')]
        ctx=r.context(page(rows),profile(page(rows)))
        self.assertEqual(ctx['math']['math_group'],ctx['fragment']['math_group'])
        self.assertEqual(rows[1]['text'],chr(16))

    def test_unnumbered_display_formula_is_grouped_without_fabricating_linear_math(self):
        rows=[styled('n','∂ρ',220,200,font='CambriaMath'),styled('d','∂t',220,214,font='CambriaMath'),
              styled('rhs','= −∇·J',248,207,font='CambriaMath')]
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertEqual(len({ctx[x['id']]['math_group'] for x in rows}),1)
        ds=decisions(rows)
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},lambda *args:probabilities(['math','retain','retain']))
        groups=r.structured_groups(rows,ds,ctx)
        self.assertEqual(len(groups),1);self.assertEqual(groups[0]['representation'],'source-spatial-region')

    def test_short_inline_prose_equality_is_not_an_unnumbered_display(self):
        row=styled('inline','at q = 0.',40,112,font='Times-Roman')
        preceding=styled('body','The source paragraph ends with a short measured condition',40,100,font='Times-Roman')
        p=page([preceding,row]);ctx=r.context(p,profile(p))
        self.assertTrue(ctx['inline']['prose_tail']);self.assertIsNone(ctx['inline']['math_group'])

    def test_damaged_mapping_with_operator_glyphs_is_not_equation_evidence(self):
        row=styled('bad','\x17a = \x03 b + \x1c',180,200,font='Times-Roman')
        p=page([row]);ctx=r.context(p,profile(p))
        self.assertIsNone(ctx['bad']['math_group'])

    def test_inline_math_tail_is_not_a_display_region(self):
        rows=[styled('p','The measured response remains continuous under the conditions',40,100,block=4),styled('tail','at q = 0.',40,112,block=4,index=1)]
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertTrue(ctx['tail']['prose_tail']);self.assertIsNone(ctx['tail']['math_group'])

    def test_rotated_repeated_axis_label_is_not_running_furniture(self):
        row=styled('axis','Pressure',40,100);row['direction']=[0,1];p=page([row]);pr=profile(p);pr['repeated_furniture']=['pressure']
        self.assertFalse(r.context(p,pr)['axis']['repeated_margin'])

    def test_overlapping_damaged_text_layers_are_flagged_without_dropping_either(self):
        damaged=styled('damaged','The measured response \x03 retained source text.',40,100)
        alternative=styled('alternative','The measured response is retained source text.',40,100)
        matches=r.overlapping_layers([damaged,alternative])
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['native_line_id'],'damaged')
        self.assertEqual(matches[0]['alternative_line_ids'],['alternative'])
        p=page([damaged,alternative]);result=s.reconstruct(p,profile(p))
        self.assertEqual({x['id'] for x in result['blocks'][0]['source_lines']} if result['blocks'] and result['blocks'][0].get('source_lines') else {x for b in result['blocks'] for x in b['line_ids']},{'damaged','alternative'})
        self.assertTrue(any(issue['code']=='structure-competing-text-layers' for issue in result['issues']))
        self.assertTrue(all(x.get('content_integrity')=='competing-source-text-layers' for x in result['line_roles']))

    def test_two_damaged_overlapping_layers_are_still_reported_as_competitors(self):
        first=styled('first','The measured response \x03 retained source text.',40,100,font='Times-Roman')
        second=styled('second','The measured response \x04 retained source text.',40,100,font='AltFont')
        matches=r.overlapping_layers([first,second])
        self.assertEqual(len(matches),1)
        self.assertTrue(matches[0]['both_layers_may_be_damaged'])

    def test_unsafe_native_glyph_remains_in_evidence_and_requests_review(self):
        row=styled('a','Original \x03 native glyph.',40,100);p=page([row])
        result=s.reconstruct(p,profile(p))
        self.assertIn('\x03',result['blocks'][0]['text']);self.assertTrue(result['line_roles'][0]['review_required'])
        self.assertTrue(any(i['code']=='structure-native-glyph-review' for i in result['issues']))

    def test_code_html_escapes_and_retains_spatial_indentation(self):
        b={'id':'D-B1','type':'paragraph','format':'code','source':{'document_id':'D','page':3},'source_lines':[{'bbox':[40,100,100,110]},{'bbox':[60,112,150,122]}],
           'units':[{'id':'U','translations':{'zh':{'faithful':'if (a < b) {\nreturn a;'}}}],'typography':{'dominant_size_pt':10}}
        text=publishing.block_html(Path('.'),b,'zh','faithful',{})
        self.assertIn('<pre',text);self.assertIn('a &lt; b',text);self.assertIn('padding-inline-start:2.0em',text);self.assertEqual(text.count('data-uid='),1)

    def test_code_fragments_on_same_baseline_remain_on_one_visual_line(self):
        b={'id':'D-B1','type':'paragraph','format':'code','source':{'document_id':'D','page':3},
           'source_lines':[{'bbox':[40,100,100,110]},{'bbox':[120,100,170,110]}],
           'units':[{'id':'U','translations':{'zh':{'faithful':'Generated by:\nEngine'}}}],
           'typography':{'dominant_size_pt':10}}
        text=publishing.block_html(Path('.'),b,'zh','faithful',{})
        self.assertEqual(text.count('class="code-visual-row"'),1)
        self.assertIn('margin-inline-start:2.0em',text)

    def test_spatial_formula_ingest_exports_source_svg_and_png(self):
        try:import fitz
        except ImportError:self.skipTest('PyMuPDF unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pdf=fitz.open();pg=pdf.new_page();pg.insert_text((120,200),'1');pg.insert_text((120,220),'3');pg.draw_line((116,205),(132,205));source=root/'original.pdf';pdf.save(source);pdf.close()
            region={'type':'paragraph','role':'equation','semantic_role':'equation','representation':'source-spatial-region','region_id':'eq','text':'1\n3',
                    'bbox':[110,185,140,225],'line_ids':['n','d'],'native_line_ids':['n','d'],'typography':{},'level':2,'review_required':False,'operations':[]}
            result={'blocks':[region],'issues':[],'region_relations':[]};content={'sources':[{'id':'D001'}],'blocks':[],'issues':[]}
            prepared={'pages':{1:{'page':1,'lines':[],'raw_sha256':'sourcehash'}},'profile':{},'model_path':'unused','model_sha256':'model','pipeline_sha256':'pipeline','source_file':str(source)}
            with patch.object(s,'reconstruct',return_value=result):ingest.append_page(root,content,'D001',1,prepared,'auto',t.add_block,t.split_text)
            block=content['blocks'][0]
            self.assertEqual(block['type'],'equation');self.assertEqual(block['units'],[]);self.assertEqual(block['native_spatial_transcript'],'1\n3')
            self.assertTrue((root/block['asset']).exists());self.assertTrue((root/block['asset_fallback']).exists())
            self.assertIn('<path',(root/block['asset']).read_text())

if __name__=='__main__':unittest.main()
