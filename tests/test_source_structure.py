"""Source-structure invariants use original tiny fixtures, never private PDFs."""
import argparse
import contextlib
import copy
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'skills/document-translation/scripts')]
import source_structure as s
import train_source_structure as trainer
import translate as t
import structure_corpus as corpus
import structure_ingest as adapter


def line(lid,text,x,y,width=180,block=0,index=0):
    bbox=[x,y,x+width,y+10]
    return {'id':lid,'text':text,'bbox':bbox,'native_block':block,'native_line':index,
            'direction':[1,0],'size':10,'font':'Times-Roman','flags':0,'wmode':0,
            'spans':[{'text':text,'font':'Times-Roman','size':10,'flags':0,'bbox':bbox,'origin':[x,y+8]}]}


class StructureTests(unittest.TestCase):
    def test_detached_reference_marker_is_rejoined_without_losing_native_ids(self):
        marker=line('marker','[12]',40,100,14,block=1)
        text=line('text','Smith, A. An original measured result, Journal 2025.',60,100,230,block=2)
        other=line('other','Unrelated text in another column.',330,100,220,block=3)
        rows=s.physical_rows([marker,text,other])
        self.assertEqual(len(rows),2)
        entry=next(x for x in rows if x['id']=='text')
        self.assertEqual(entry['text'],'[12] Smith, A. An original measured result, Journal 2025.')
        self.assertEqual(set(entry['native_line_ids']),{'marker','text'})
        self.assertEqual(next(x for x in rows if x['id']=='other')['text'],other['text'])

    def test_sparse_waveform_grid_below_caption_is_not_a_data_table(self):
        cap=line('caption','Fig. 2 | The measured register waveforms.',40,300,500)
        grid={'bbox':[320,80,550,200],'rows':10,'columns':10,
              'cells':[[320+i*23,80+j*12,343+i*23,92+j*12] for i in range(10) for j in range(10)]}
        rows=[cap,line('clock','CLK',325,85,15),line('time','Time (ms)',390,190,50)]
        kept,rejected=s.filter_table_regions(rows,[grid],600,800)
        self.assertEqual(kept,[]);self.assertEqual(len(rejected),1)

    def test_caption_flows_across_columns_but_reference_does_not_seed_caption(self):
        import figure_learning as f
        a=line('a','Fig. 2 | Original caption ending in an unfinished',40,300,245,block=1)
        b=line('b','description of the measured',40,314,245,block=1,index=1)
        c=line('c','signal in the independent source figure.',310,300,240,block=2)
        d=line('d','The final observation remains visible.',310,314,240,block=2,index=1)
        p={'page':2,'width':600,'height':800,'lines':[a,b,c,d]}
        chains=f.caption_column_continuations(p,{'a','b'})
        self.assertEqual([[x['id'] for x in right] for left,right in chains],[['c','d']])
        self.assertTrue(f.REFERENCE.match('Table 1 for details). This is source body text.'))
        self.assertFalse(f.REFERENCE.match('Table 1. Measured response values.'))

    def test_narrow_persistent_gutter_does_not_interleave_tall_columns(self):
        regions=[{'id':'left-top','bbox':[40,100,298,300]},
                 {'id':'right-top','bbox':[300,100,556,210]},
                 {'id':'left-lower','bbox':[40,310,298,740]},
                 {'id':'right-lower','bbox':[300,220,556,740]}]
        self.assertEqual([x['id'] for x in s.order_regions(regions,600)],
                         ['left-top','left-lower','right-top','right-lower'])

    def test_split_thin_rectangle_rules_form_caption_bounded_narrow_table(self):
        rules=s.coalesce_horizontal_rules([(40,130,102),(102.2,130.2,190),(190,130,280),
            (40,145,280),(40,180,102),(102,180,280)],600)
        self.assertEqual(len(rules),3)
        cap=line('cap','Table 1 A source measurement table',40,105,230)
        cells=[line('a','Condition',50,135,90,block=1),line('b','Value',170,135,80,block=1,index=1),
               line('c','Operating range',50,155,100,block=2),line('d','12',170,155,20,block=2,index=1)]
        self.assertEqual(len(s.horizontal_table_boxes([cap]+cells,rules,600,800)),1)

    def test_caption_without_number_space_and_table_reference_wrap_are_distinct(self):
        a=line('a','Figure1 A source fabrication process.',40,100,240)
        b=line('b','The observations are shown in Table',40,140,240,block=1)
        c=line('c','2. The measured response is recorded.',40,152,240,block=1,index=1)
        page={'width':600,'height':800,'lines':[a,b,c]}
        self.assertTrue(s.caption_anchor(a,page))
        self.assertFalse(s.list_marker(c,page))
        self.assertFalse(s.caption_start('Figure 3 shows the original observation.'))

    def test_short_centered_title_block_extends_profile_without_source_completion(self):
        a=line('a','An original long title line describing a measured system',50,100,500)
        b=line('b','Observed Responses',235,122,130,block=1)
        c=line('c','A source author',180,160,240,block=2)
        for r in [a,b]:r['size']=16;r['font']='Times-Bold';r['flags']=16
        body=[line('p'+str(i),'This original narrative paragraph supplies the observed body font size and spacing.',50,220+i*12,230,block=3,index=i) for i in range(4)]
        page={'page':1,'width':600,'height':800,'lines':[a,b,c]+body}
        profile=s.document_profile([page]);self.assertEqual(profile['title_band'],[100,132])

    def test_same_baseline_caption_tails_respect_independent_panel_anchors(self):
        a=line('a','Fig. 1. An original source caption.',40,100,140,index=0)
        b=line('b','Its continuation.',40,112,110,index=1)
        c=line('c','Fig. 2. Another independent source caption.',190,100,150,index=2)
        d=line('d','Its own separate continuation.',190,112,140,index=3)
        rows=s.physical_rows([a,b,c,d])
        self.assertEqual(len(rows),4)
        self.assertEqual({tuple(r['native_line_ids']) for r in rows},{('a',),('b',),('c',),('d',)})

    def test_separate_filled_header_bands_prevent_native_block_fusion(self):
        a=line('a','An independent panel heading',40,100,130)
        b=line('b','A distinct longer panel heading for another section',190,100,280,index=1)
        for r in [a,b]:r['flags']=16
        rows=s.physical_rows([a,b],heading_regions=[[35,96,180,116],[185,96,480,116]])
        self.assertEqual(len(rows),2)
        page={'page':3,'width':600,'height':800,'lines':rows,'heading_regions':[[35,96,180,116],[185,96,480,116]]}
        profile=s.document_profile([page]);profile['body_size']=10
        probs=[.001]*len(s.ROLES);probs[3]=.991
        for r in rows:self.assertEqual(s.role_decision(s.role_features(r,page,profile),probs)['assigned_role'],'heading')

    def test_plot_ticks_and_parameter_text_are_not_page_numbers_or_equations(self):
        rows=[line('n','120',60,720,20),line('v','V = 3.4',100,710,50,block=1),
              line('c','Fig. 4. An original measured response plot.',40,765,240,block=2)]
        for r in rows[:2]:r['size']=8
        page={'page':4,'width':600,'height':800,'lines':rows,'graphic_regions':[[40,670,270,755]]}
        profile=s.document_profile([page]);profile['body_size']=10
        probs=[.001]*len(s.ROLES);probs[3]=.991
        for r in rows[:2]:self.assertEqual(s.role_decision(s.role_features(r,page,profile),probs)['assigned_role'],'label')
        self.assertEqual(s.role_decision(s.role_features(rows[2],page,profile),probs)['assigned_role'],'caption')

    def test_centered_title_candidates_can_cross_native_blocks(self):
        a=line('a','An original wide title line',60,50,460)
        b=line('b','A short centered continuation',150,74,280,block=1)
        a['size']=b['size']=20
        pairs=s.candidate_pairs([a,b],600,800,roles={'a':'title','b':'title'})
        self.assertIn(('a','b'),[(x['id'],y['id']) for x,y in pairs])
        self.assertIsNone(s.join_gate(a,b,'title','title'))

    def test_small_caps_caption_same_baseline_keeps_both_native_fragments(self):
        a=line('a','TABLE I.',80,100,37)
        b=line('b','PARAMETERS AND RANGES',135,100,120,index=1)
        a['size']=8;b['size']=6.5
        rows=s.physical_rows([a,b])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['native_line_ids'],['a','b'])
        self.assertEqual(rows[0]['text'],'TABLE I. PARAMETERS AND RANGES')

    def test_citation_range_continuation_is_measured_without_completion(self):
        a=line('a','The original evidence appears in [1-',40,100,230)
        b=line('b','3].',40,112,15,index=1)
        page={'width':600,'height':800,'lines':[a,b]}
        features=dict(zip(s.JOIN_FEATURES,s.join_features(a,b,page,('body','body'))))
        self.assertEqual(features['bracket_continuation'],1.)
        b['text']='3. A new numbered item'
        features=dict(zip(s.JOIN_FEATURES,s.join_features(a,b,page,('body','body'))))
        self.assertEqual(features['bracket_continuation'],0.)

    def test_sparse_diagram_label_block_can_supply_local_graphic_evidence(self):
        rows=[line(str(i),text,40+(i%2)*80,100+(i//2)*20,65,index=i) for i,text in enumerate([
            '• Fetch','• Decode','• Write','• Jump','• Add','• Read'])]
        for row in rows:row['size']=8
        cap=line('cap','Figure 3. An original data path diagram.',40,300,240,block=1)
        page={'page':2,'width':600,'height':800,'lines':rows+[cap]}
        profile=s.document_profile([page]);profile['body_size']=10
        features=s.role_features(rows[0],page,profile)
        self.assertTrue(features[s.ROLE_FEATURES.index('source_figure_band')])

    def test_raised_source_footnote_marker_and_continuation_are_metadata(self):
        first=line('first','1An original explanatory note.',320,710,230)
        tail=line('tail','with a retained citation [2].',312,720,220,index=1)
        first['size']=tail['size']=8
        first['spans']=[{'text':'1','size':6,'bbox':[320,708,323,714],'origin':[320,712]},
                        {'text':'An original explanatory note.','size':8,'bbox':[324,710,550,718],'origin':[324,715]}]
        for sp in first['spans']:sp.update(font='Times-Roman',flags=0)
        page={'page':1,'width':600,'height':800,'lines':[first,tail]}
        profile=s.document_profile([page]);profile['body_size']=10
        self.assertTrue(s.raised_footnote_marker(first))
        probabilities=[.001]*len(s.ROLES);probabilities[0]=.991
        for row in [first,tail]:
            features=s.role_features(row,page,profile)
            self.assertTrue(features[s.ROLE_FEATURES.index('footnote_context')])
            self.assertEqual(s.role_decision(features,probabilities)['assigned_role'],'metadata')
        first['spans'][0]['size']=8
        self.assertFalse(s.raised_footnote_marker(first))

    def test_author_affiliation_boundary_matches_inference_and_loss(self):
        a=line('a','A. Vale and B. Park',100,100,260)
        b=line('b','Department of Science, Example University',90,112,280,index=1)
        page={'width':600,'height':800,'lines':[a,b]}
        self.assertEqual(s.join_gate(a,b,'metadata','metadata'),'author-to-affiliation-boundary')
        self.assertEqual(trainer.constraint_cost(s.join_features(a,b,page,('metadata','metadata')),'join')[1],1.)
        a['text']='Department of Science'
        self.assertIsNone(s.join_gate(a,b,'metadata','metadata'))

    def test_mixed_review_state_title_chain_preserves_review_after_join(self):
        a=line('a','An original document title with a wide first line',50,50,400)
        b=line('b','and its short continuation',150,72,200,index=1)
        for row in [a,b]: row['size']=20
        page={'page':1,'width':600,'height':800,'lines':[a,b],'raw_sha256':s.digest([a,b])}
        profile=s.document_profile([page]);profile.update(body_size=10,max_size=20,title_band=[50,82])
        probabilities=[.001]*len(s.ROLES);probabilities[1]=.991
        model={'id':'original-test-fixture','role_head':{},'join_head':{},'role_threshold':.8,'join_threshold':.94}
        with patch.object(s,'load_model',return_value=model),patch.object(s,'predict_many',side_effect=[[probabilities,probabilities],[[.001,.999]]]):
            result=s.reconstruct(page,profile)
        self.assertEqual(len(result['blocks']),1)
        self.assertEqual(result['blocks'][0]['line_ids'],['a','b'])
        self.assertTrue(result['blocks'][0]['review_required'])

    def test_caption_below_smaller_regular_prose_does_not_override_body(self):
        rows=[line('r'+str(i),text,320,140+i*12,235,index=i) for i,text in enumerate([
            'This source paragraph uses a smaller body font on its first page.',
            'Its original text remains continuous across physical source rows',
            'and the terminal sentence ends here. A figure follows further down.',
            'The caption must not turn this narrative into diagram labels.'])]
        for row in rows: row['size']=9
        cap=line('cap','Figure 1. An independent diagram below the paragraph.',320,580,235,block=2)
        page={'page':1,'width':600,'height':800,'lines':rows+[cap],
              'graphic_regions':[[320,510,555,565]]}
        profile=s.document_profile([page]);profile['body_size']=10
        features=s.role_features(rows[0],page,profile)
        self.assertFalse(features[s.ROLE_FEATURES.index('source_figure_band')])
        probs=[.001]*len(s.ROLES);probs[0]=.991
        self.assertEqual(s.role_decision(features,probs)['assigned_role'],'body')

    def test_figure_band_requires_local_graphic_evidence_for_nonmarker_text(self):
        label=line('label','Response (V)',40,150,90);label['size']=8
        cap=line('cap','Figure 2. A response plot.',40,270,230,block=1)
        page={'page':2,'width':600,'height':800,'lines':[label,cap]}
        profile=s.document_profile([page]);profile['body_size']=10
        self.assertFalse(s.role_features(label,page,profile)[s.ROLE_FEATURES.index('source_figure_band')])
        page['graphic_regions']=[[35,130,250,250]]
        self.assertTrue(s.role_features(label,page,profile)[s.ROLE_FEATURES.index('source_figure_band')])

    def test_repeated_footer_inside_lower_nine_percent_retains_metadata(self):
        footer=line('footer','An original recurring workshop imprint',150,746,300)
        page={'page':3,'width':600,'height':800,'lines':[footer]}
        profile=s.document_profile([page]);profile['repeated_furniture']=[s.furniture_key(footer,page)]
        features=s.role_features(footer,page,profile)
        probs=[.001]*len(s.ROLES);probs[0]=.991
        self.assertEqual(s.role_decision(features,probs)['assigned_role'],'metadata')

    def test_horizontal_only_table_is_bounded_by_caption_rules_and_actual_cell_bands(self):
        cap=line('cap','Table 1. Source measurements.',70,100,300)
        cells=[line('a','Field',70,130,80,block=1),line('b','Value',270,130,80,block=1,index=1),
               line('c','Pressure',70,150,80,block=2),line('d','12 kPa',270,150,80,block=2,index=1)]
        prose=line('p','This original prose paragraph begins after the table and must remain outside the proposed cells.',70,180,330,block=3)
        prose['size']=12
        rules=[(60,120,400),(60,142,400),(60,170,400),(60,240,400)]
        boxes=s.horizontal_table_boxes([cap]+cells+[prose],rules,600,800)
        self.assertEqual(boxes,[[60,120,400,170]])
        self.assertEqual(s.horizontal_table_boxes([cap,cells[0],prose],rules,600,800),[])

    def test_independently_numbered_headings_never_merge_as_one_heading(self):
        a=line('a','4. Performance evaluation',40,100,230)
        b=line('b','4.1. Device design',40,112,220,index=1)
        page={'width':600,'height':800,'lines':[a,b]}
        self.assertEqual(s.join_gate(a,b,'heading','heading'),'new-numbered-heading')
        features=s.join_features(a,b,page,('heading','heading'))
        self.assertEqual(trainer.constraint_cost(features,'join')[1],1.)
        b['text']='under source conditions'
        self.assertIsNone(s.join_gate(a,b,'heading','heading'))

    def test_numbered_heading_in_own_block_uses_next_prose_typeface(self):
        head=line('h','2. A source section title',40,100,230);head['font']='Source-Bold'
        prose=line('p','The next source paragraph supplies sufficient narrative evidence.',60,116,300,block=1)
        page={'page':3,'width':600,'height':800,'lines':[head,prose]}
        self.assertTrue(s.numbered_typographic_heading(head,page))
        self.assertFalse(s.list_marker(head,page))

    def test_color_online_caption_context_stops_list_propagation_into_narrative(self):
        caption=line('cap','Figure 1 (Color online) (a) A measured source response.',40,300,500)
        tail=line('tail','(d) The final source panel.',40,312,440,index=1)
        body=line('body','The next source paragraph is separate narrative.',40,330,230,block=1)
        page={'page':2,'width':600,'height':800,'lines':[caption,tail,body]}
        self.assertTrue(s.caption_anchor(caption,page))
        self.assertTrue(s.role_features(tail,page,s.document_profile([page]))[s.ROLE_FEATURES.index('explicit_caption_label')])
        self.assertFalse(s.role_features(body,page,s.document_profile([page]))[s.ROLE_FEATURES.index('list_continuation_context')])
        self.assertFalse(s.caption_start('Figure 1 illustrates the measured response.'))

    def test_first_page_title_uses_dominant_type_not_earlier_masthead(self):
        masthead=line('masthead','A SOURCE JOURNAL FEATURE',35,25,280)
        masthead['size']=12
        title=line('title','The original document title',70,160,350,block=1);title['size']=32
        continuation=line('continuation','A multiline title',70,200,280,block=1,index=1);continuation['size']=32
        title['bbox'][3]=192;continuation['bbox'][3]=232
        prose=[line('p'+str(i),text,70,430+i*14,350,block=3,index=i) for i,text in enumerate([
            'This original opening summary has sufficient source text to be narrative,',
            'with measured conditions and limitations retained in the same paragraph.',
            'Several lines supply typographic and physical evidence of a prose block,',
            'so the end of the title and author region can be identified conservatively.'])]
        page={'page':1,'width':600,'height':800,'lines':[masthead,title,continuation]+prose}
        profile=s.document_profile([page])
        self.assertEqual(profile['title_band'],[160,232])
        self.assertEqual(profile['front_matter_bottom'],430)

    def test_small_author_date_running_header_below_top_margin_is_metadata(self):
        rows=[line('author','Vale A, et al.',185,99,70),
              line('journal','Example Journal',260,99,70,index=1),
              line('date','June 2025 Vol. 6',340,99,90,index=2)]
        for row in rows:row['size']=7
        page={'page':2,'width':600,'height':840,'lines':rows}
        profile=s.document_profile([page]);profile['body_size']=8
        f=s.role_features(rows[1],page,profile)
        self.assertTrue(f[s.ROLE_FEATURES.index('running_header_context')])
        self.assertEqual(s.role_decision(f,[.99]+[.001]*9)['assigned_role'],'metadata')

    def test_parenthesized_number_continuation_is_not_a_list_marker(self):
        a=line('a','The mechanism is implemented by a circuit (delay',40,100,230)
        b=line('b','2) whose parameter can be varied.',40,112,200,index=1)
        page={'width':600,'height':800,'lines':[a,b]}
        self.assertFalse(s.list_marker(b,page))
        a['text']='The two stages are listed below:'
        self.assertTrue(s.list_marker(b,page))

    def test_hanging_list_continues_after_tall_bullet_and_complete_sentence(self):
        marker=line('m','›› A stated source item',40,100,210)
        marker['bbox'][3]=119
        a=line('a','contains a complete sentence.',49,117,200,index=1)
        b=line('b','Another sentence belongs to the same item.',49,129,200,index=2)
        page={'page':2,'width':600,'height':800,'lines':[marker,a,b]}
        features=s.role_features(b,page,s.document_profile([page]))
        self.assertTrue(features[s.ROLE_FEATURES.index('list_continuation_context')])
        b['bbox'][0]=59
        features=s.role_features(b,page,s.document_profile([page]))
        self.assertFalse(features[s.ROLE_FEATURES.index('list_continuation_context')])

    def test_short_caption_label_and_text_share_one_physical_row_without_lost_ids(self):
        label=line('label','Fig. 4.',40,100,25)
        text=line('text','The measured response',74,100,105,index=1)
        rows=s.physical_rows([label,text])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['native_line_ids'],['label','text'])
        self.assertEqual(rows[0]['text'],'Fig. 4. The measured response')
        text['text']='Fig. 5. Separate caption'
        self.assertEqual(len(s.physical_rows([label,text])),2)

    def test_cross_column_features_separate_seam_position_from_local_spacing(self):
        a=line('a','an original source clause continued',40,610,230)
        b=line('b','under the stated condition.',330,90,220,block=1)
        page={'width':600,'height':800,'lines':[a,b]}
        features=dict(zip(s.JOIN_FEATURES,s.join_features(a,b,page,('body','body'),True)))
        self.assertEqual(features['vertical_gap'],.2)
        self.assertEqual(features['baseline_step'],1.2)
        self.assertEqual(features['left_delta'],0.)
        self.assertEqual(features['transition_previous_bottom'],620/800)
        self.assertEqual(features['transition_next_top'],90/800)
        self.assertEqual(trainer.constraint_cost(list(features.values()),'join')[1],0.)

    def test_repeated_marginal_footer_precedes_reference_context(self):
        row=line('footer','A recurring publication footer.',40,780,250)
        page={'page':4,'width':600,'height':800,'lines':[row]}
        profile=s.document_profile([page]);profile['repeated_furniture']=[s.furniture_key(row,page)]
        features=s.role_features(row,page,profile)
        features[s.ROLE_FEATURES.index('reference_section_context')]=1.
        probabilities=[.001]*len(s.ROLES);probabilities[s.ROLES.index('reference')]=.991
        self.assertEqual(s.role_decision(features,probabilities)['assigned_role'],'metadata')

    def test_centered_caption_final_line_can_join_with_matching_loss_constraint(self):
        a=line('a','Figure 2: A measured response under controlled conditions.',40,100,240)
        b=line('b','at the stated bias.',120,112,80,index=1)
        page={'width':600,'height':800,'lines':[a,b]}
        self.assertIsNone(s.join_gate(a,b,'caption','caption'))
        f=s.join_features(a,b,page,('caption','caption'))
        self.assertEqual(trainer.constraint_cost(f,'join')[1],0.)
        b['native_block']=2
        self.assertIsNotNone(s.join_gate(a,b,'caption','caption'))

    def test_cross_column_candidate_keeps_late_body_line_and_excludes_footer(self):
        left=line('left','continued at the bottom of the left column',40,737,230)
        right=line('right','and resumed in the next source column.',330,55,230,block=1)
        footer=line('footer','Publication and licensing information',40,770,230,block=2)
        roles={'left':'body','right':'body','footer':'metadata'}
        pairs=s.column_transition_pairs([left,right,footer],600,800,roles)
        self.assertEqual([(a['id'],b['id']) for a,b in pairs],[('left','right')])

    def test_control_suffixed_subfigure_marker_is_labeled_without_changing_source(self):
        marker=line('m','(a)\x03',40,100,20);marker['size']=12
        cap=line('c','Figure 2: A vertically stacked group of panels.',40,620,230,block=1);cap['size']=8
        body=line('p','Source narrative below the figure and its caption.',40,655,230,block=2)
        page={'page':3,'width':600,'height':800,'lines':[marker,cap,body]}
        profile=s.document_profile([page]);profile['body_size']=10
        f=s.role_features(marker,page,profile)
        self.assertTrue(f[s.ROLE_FEATURES.index('source_figure_band')])
        self.assertEqual(marker['text'],'(a)\x03')

    def test_captioned_table_precedes_later_figure_band_without_relabeling_cells(self):
        tablecap=line('tc','Table 1. The measured responses.',50,50,320)
        cell=line('cell','1.675',80,350,35,block=1);cell['size']=9
        figcap=line('fc','Fig. 2. A separate plot beneath the table.',50,520,320,block=2)
        page={'page':7,'width':600,'height':800,'lines':[tablecap,cell,figcap],
              'structure_regions':[[75,72,350,320],[75,100,350,365]]}
        profile=s.document_profile([page]);profile['body_size']=10
        f=s.role_features(cell,page,profile)
        self.assertTrue(f[s.ROLE_FEATURES.index('captioned_table_context')])
        self.assertFalse(f[s.ROLE_FEATURES.index('source_figure_band')])
        probs=[.001]*len(s.ROLES);probs[s.ROLES.index('label')]=.991
        self.assertEqual(s.role_decision(f,probs)['assigned_role'],'table')

    def test_subfigure_text_below_plot_is_caption_but_in_plot_text_is_not(self):
        cap=line('sub','(a) Measured response at a fixed bias.',40,230,170)
        main=line('main','Figure 2: Two measured responses.',40,280,350,block=1)
        page={'page':3,'width':600,'height':800,'lines':[cap,main],
              'graphic_regions':[[40,70,210,210]]}
        self.assertTrue(s.subfigure_caption_context(cap,page))
        f=s.role_features(cap,page,s.document_profile([page]))
        probs=[.001]*len(s.ROLES);probs[s.ROLES.index('label')]=.991
        self.assertEqual(s.role_decision(f,probs)['assigned_role'],'caption')
        page['graphic_regions']=[[40,70,210,260]]
        self.assertFalse(s.subfigure_caption_context(cap,page))

    def test_short_subfigure_fragments_join_without_merging_two_panel_captions(self):
        a=line('a','(a) A measured response',40,100,110)
        b=line('b','with bias',152,100,45,index=1)
        rows=s.physical_rows([a,b]);self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['text'],'(a) A measured response with bias')
        b['text']='(b) A second response';b['spans'][0]['text']=b['text']
        self.assertEqual(len(s.physical_rows([a,b])),2)

    def test_composite_model_provenance_keeps_both_heads_fitting_sources(self):
        import train_structure_forest as forest
        with tempfile.TemporaryDirectory() as td:
            annotation=Path(td)/'annotations.json';annotation.write_text('{}')
            base=Path(td)/'base.json';base.write_text('{}')
            model={'training':{'real_train_source_sha256':['a'*64],
                               'real_validation_source_sha256':['b'*64]}}
            forest.record_head_provenance(model,[{'source_sha256':'c'*64,'source_parent_sha256':['e'*64]}],
                                          [{'source_sha256':'d'*64}],annotation,base,12,173)
        self.assertEqual(set(model['training']['real_train_source_sha256']),{'a'*64,'c'*64})
        self.assertEqual(set(model['training']['real_validation_source_sha256']),{'b'*64,'d'*64})
        self.assertEqual(model['training']['role_head_provenance']['real_train_source_sha256'],['c'*64])
        self.assertIn('e'*64,model['training']['real_train_source_family_sha256'])

    def test_unknown_font_numbered_section_does_not_turn_body_into_list(self):
        rows=[line('h','4. Measured device response',40,100,210),
              line('p','The channel response was measured under the stated conditions',40,114,220,index=1),
              line('p2','and the resulting curve is reported in the following figure.',40,126,220,index=2)]
        rows[0]['font']='EmbeddedF9'
        page={'page':2,'width':600,'height':800,'lines':rows}
        self.assertTrue(s.numbered_typographic_heading(rows[0],page))
        self.assertFalse(s.list_marker(rows[0],page))
        for row in rows[1:]:
            f=s.role_features(row,page,s.document_profile([page]))
            self.assertFalse(f[s.ROLE_FEATURES.index('list_continuation_context')])
        rows[0]['font']=rows[1]['font']
        self.assertTrue(s.list_marker(rows[0],page))

    def test_narrow_justified_prose_recovers_same_baseline_words_only(self):
        texts=['The channel response was','measured under carefully',
               'controlled conditions. This','response remained stable',
               'during repeated measurements,','and all values were recorded.']
        rows=[]
        for i,text in enumerate(texts):
            if i==3:
                rows.extend([line('w1','response',40,40+i*13,40,index=i),
                             line('w2','remained',86,40+i*13,40,index=i+1),
                             line('w3','stable',132,40+i*13,28,index=i+2)])
            else:rows.append(line('l'+str(i),text,40,40+i*13,120,index=i))
        self.assertTrue(s.fragmented_prose_block(rows))
        result=s.physical_rows(rows)
        self.assertEqual(len(result),6)
        joined=next(x for x in result if 'w1' in x['native_line_ids'])
        self.assertEqual(joined['text'],'response remained stable')
        self.assertEqual(set(lid for r in result for lid in r['native_line_ids']),{r['id'] for r in rows})
        cells={'cells':[[39,78,82,90],[83,78,128,90],[129,78,164,90]]}
        self.assertEqual(len(s.physical_rows(rows,[cells])),8)

    def test_small_diagram_label_grid_is_not_rejoined_as_prose(self):
        rows=[line(str(i),text,40+(i%3)*40,40+(i//3)*13,30,index=i)
              for i,text in enumerate(['Input','Gate','Output','High','Low','Low','Low','High','High','Start','Stop','Reset'])]
        self.assertFalse(s.fragmented_prose_block(rows))
        self.assertEqual(len(s.physical_rows(rows)),len(rows))

    def test_reference_column_context_stops_at_larger_biography_font(self):
        rows=[line('rh','References',40,50,100),
              line('r1','[1] A. Vale, A measured report.',40,70,220,block=1),
              line('r2','[2] B. Reed, Another report.',40,100,220,block=2),
              line('r3','[3] C. Stone, Controlled measurements.',40,130,220,block=3),
              line('tail','Journal of Measurements, pages 14–20, 2022.',40,142,220,block=4),
              line('bio','Alex Doe is a researcher in experimental measurement.',40,165,220,block=5)]
        for row in rows[1:5]:row['size']=8
        rows[-1]['size']=9.2
        page={'page':3,'width':600,'height':800,'lines':rows};profile=s.document_profile([page])
        f=s.role_features(rows[4],page,profile)
        self.assertTrue(f[s.ROLE_FEATURES.index('reference_section_context')])
        f=s.role_features(rows[-1],page,profile)
        self.assertFalse(f[s.ROLE_FEATURES.index('reference_section_context')])

    def test_geometry_corroborated_unknown_title_keeps_review_required(self):
        title=line('t','An ordinary typeface title with a modest size increase',90,40,420);title['size']=12
        body=line('p','Body text in the normal document typeface for comparison.',40,150,220,block=1)
        page={'page':1,'width':600,'height':800,'lines':[title,body]}
        f=s.role_features(title,page,s.document_profile([page]))
        dec=s.role_decision(f,[.3,.65]+[.00625]*8)
        self.assertEqual(dec['assigned_role'],'title')
        self.assertTrue(dec['review_required'])

    def test_provisional_rule_is_never_auto_accepted_in_training_evaluation(self):
        features=[0.]*len(s.ROLE_FEATURES)
        features[s.ROLE_FEATURES.index('inline_prose_math_context')]=1.
        with patch.object(s,'predict_many',return_value=[[.991]+[.001]*9]):
            result=trainer.evaluate({},[(features,s.ROLES.index('body'),'source')],.8)
        self.assertEqual(result['accuracy'],1.)
        self.assertEqual(result['accepted'],0)
        self.assertEqual(result['by_document']['source']['accepted'],0)

    def test_keywords_do_not_change_body_after_section_heading(self):
        rows=[line('keywords','Keywords: imaging, circuits',40,140,220,block=2,index=0),
              line('heading','Introduction',110,153,80,block=2,index=1),
              line('body','The device records the measured response.',40,166,220,block=2,index=2)]
        rows[1]['flags']=16
        page={'page':1,'width':600,'height':800,'lines':rows}
        f=s.role_features(rows[2],page,s.document_profile([page]))
        self.assertFalse(f[s.ROLE_FEATURES.index('explicit_metadata_label')])

    def test_funding_does_not_change_references_in_mixed_native_block(self):
        rows=[line('ack','This work was supported by a research grant.',310,650,230,block=2,index=0),
              line('heading','References',390,670,80,block=2,index=1),
              line('entry','[1] J. Doe, IEEE, 2024.',310,684,230,block=2,index=2)]
        rows[2]['size']=9
        page={'page':1,'width':600,'height':800,'lines':rows}
        p=s.document_profile([page]);p['body_size']=10
        f=s.role_features(rows[2],page,p)
        self.assertFalse(f[s.ROLE_FEATURES.index('footnote_context')])
        self.assertTrue(f[s.ROLE_FEATURES.index('reference_section_context')])

    def test_figure_grid_is_retained_as_detector_evidence_not_forced_table(self):
        rows=[line('c1','Fig.1 Diagram of a device.',40,180,130),
              line('c2','Fig.2 Fabrication process.',210,180,160,block=1)]
        grid={'bbox':[30,30,560,700],'rows':8,'columns':8,'cells':[[30,30,560,700]]}
        nested={'bbox':[40,280,170,340],'rows':2,'columns':2,'cells':[]}
        kept,rejected=s.filter_table_regions(rows,[grid,nested],600,800)
        self.assertEqual(kept,[])
        self.assertEqual(len(rejected),2)
        self.assertIn('figure',rejected[0]['reason'])
        real={'bbox':[40,400,450,510],'rows':3,'columns':4,'cells':[]}
        kept,rejected=s.filter_table_regions([line('tc','Table 1. Measurements',40,380)], [real],600,800)
        self.assertEqual(kept,[real])
        self.assertEqual(rejected,[])

    def test_local_data_table_survives_inside_multi_figure_frame(self):
        rows=[line('f1','Fig. 1. First diagram.',40,180,130),
              line('f2','Fig. 2. Second diagram.',210,180,150,block=1),
              line('caption','Table 1. Measured values.',320,400,200,block=2)]
        frame={'bbox':[30,30,570,700],'rows':3,'columns':3,'cells':[]}
        local={'bbox':[320,300,540,398],'rows':3,'columns':3,'cells':[]}
        kept,rejected=s.filter_table_regions(rows,[frame,local],600,800)
        self.assertEqual(kept,[local]);self.assertEqual(len(rejected),1)
        cells=[]
        for y in range(3):
            for x in range(3):
                cell=[320+x*60,500+y*20,380+x*60,520+y*20];cells.append(cell)
                rows.append(line(f'v{x}{y}',str(x+y*3),cell[0]+10,cell[1]+2,10,block=3+y))
        dense={'bbox':[320,500,500,560],'rows':3,'columns':3,'cells':cells}
        kept,rejected=s.filter_table_regions(rows,[frame,dense],600,800)
        self.assertEqual(kept,[dense])
        rows=[row for row in rows if not row['id'].startswith('v')]
        kept,rejected=s.filter_table_regions(rows,[frame,dense],600,800)
        self.assertEqual(kept,[])

    def test_local_table_and_caption_continuations_outrank_figure_band(self):
        probabilities=[.001]*len(s.ROLES);probabilities[s.ROLES.index('label')]=.991
        for key,expected in [('table_region','table'),('explicit_caption_label','caption')]:
            features=[0.]*len(s.ROLE_FEATURES)
            features[s.ROLE_FEATURES.index('source_figure_band')]=1
            features[s.ROLE_FEATURES.index('log_length')]=math.log1p(24)/6
            features[s.ROLE_FEATURES.index(key)]=1
            decision=s.role_decision(features,probabilities)
            self.assertEqual(decision['assigned_role'],expected)
        cap=line('cap','Table 1. Measured response.',300,402,200)
        page={'lines':[cap],'table_regions':[{'bbox':[300,300,520,400]}]}
        self.assertEqual(s.captioned_table_boxes(page),[[300,300,520,400]])

    def test_two_captions_on_same_baseline_remain_separate_without_table_cells(self):
        left=line('l','Figure 2: Source diagram with a full caption.',40,220,230,block=3,index=0)
        right=line('r','Figure 3: Another diagram in a different panel.',280,220,230,block=3,index=1)
        rows=s.physical_rows([left,right],[])
        self.assertEqual(len(rows),2)
        self.assertEqual([r['text'] for r in rows],[left['text'],right['text']])

    def test_caption_context_stops_before_numbered_unknown_font_heading(self):
        cap=line('cap','Figure 1: A device schematic.',330,220,210,block=1);cap['size']=6
        tail=line('tail','with a measured channel region.',330,230,210,block=2);tail['size']=6
        heading=line('h','2. OVERCOMING OBSTACLES',330,246,180,block=3);heading['size']=8;heading['font']='Embedded+F9'
        prose=line('p','While devices promise improved operation, obstacles remain.',330,260,220,block=3,index=1);prose['size']=8;prose['font']='Embedded+F3'
        page={'page':1,'width':600,'height':800,'lines':[cap,tail,heading,prose]};profile=s.document_profile([page])
        for row in [heading,prose]:
            f=s.role_features(row,page,profile)
            self.assertFalse(f[s.ROLE_FEATURES.index('native_caption_context')])
        f=s.role_features(heading,page,profile)
        self.assertTrue(f[s.ROLE_FEATURES.index('explicit_heading_label')])

    def test_reference_context_spans_native_blocks_and_next_column(self):
        rows=[line('rh','References',40,650,100),
              line('r1','[Vale 24] A. Vale, A measured report.',330,50,220,block=1),
              line('r2','[Reed 23] B. Reed, Another report.',330,95,220,block=2),
              line('r3','[Stone 22] C. Stone, Controlled measurements.',330,140,220,block=3),
              line('tail','Proceedings, volume 12, pages 14–20, 2022.',330,152,220,block=4)]
        page={'page':3,'width':600,'height':800,'lines':rows};profile=s.document_profile([page])
        f=s.role_features(rows[-1],page,profile)
        self.assertTrue(f[s.ROLE_FEATURES.index('reference_section_context')])
        self.assertTrue(s.REFERENCE.match(rows[1]['text']))

    def test_title_band_excludes_separate_affiliation_after_title(self):
        title=line('t','A compact article title with ordinary type size',90,45,420);title['size']=10.4
        affiliation=line('a','Department of Computing, Example University',90,90,420,block=1);affiliation['size']=10.4
        body=line('p','This body paragraph uses a slightly smaller type size.',40,150,220,block=2);body['size']=8.1
        body2=line('p2','Further observations use the same ordinary body type.',40,162,220,block=2,index=1);body2['size']=8.1
        page={'page':1,'width':600,'height':800,'lines':[title,affiliation,body,body2]};profile=s.document_profile([page])
        self.assertEqual(profile['title_band'],[45,55])


    def test_dropcap_joins_first_printed_row_without_losing_evidence(self):
        initial=line('initial','D',40,40,20);initial['size']=30;initial['bbox'][3]=70;initial['spans'][0]['size']=30
        first=line('first','URING the experiment, signals were measured.',62,41,230,index=1)
        second=line('second','and all the stated conditions are preserved.',62,53,230,index=2)
        rows=s.physical_rows([initial,first,second])
        self.assertEqual(rows[0]['text'],'DURING the experiment, signals were measured.')
        self.assertEqual(rows[0]['native_line_ids'],['initial','first'])
        self.assertEqual(rows[1]['text'],second['text'])

    def test_multilevel_figure_reference_in_prose_is_not_caption(self):
        self.assertFalse(s.CAPTION.search('Figure 31.3.2 shows the overall nanosystem.'))
        self.assertFalse(s.CAPTION.search('The result is shown in Fig. 2.'))

    def test_multilevel_figure_caption_with_delimiter_is_detected(self):
        self.assertTrue(s.CAPTION.search('Figure 31.3.2: Schematic of the system.'))
        self.assertTrue(s.CAPTION.search('Fig. 2. A measured response.'))
        self.assertTrue(s.CAPTION.search('TABLE VI'))
        self.assertTrue(s.CAPTION.search('1. Fabrication flow for the CNT computer. (338 KB)'))
        self.assertTrue(s.CAPTION.search('Flowchart showing the implementation of the SUBNEG instruction.'))

    def test_numbered_list_items_do_not_match_bibliography_entries(self):
        self.assertFalse(s.REFERENCE.search('1) development of a spintronic-based neuron;'))
        self.assertTrue(s.LIST_START.match('1) development of a spintronic-based neuron;'))
        self.assertTrue(s.REFERENCE.search('[12] Doe, J. & Roe, A. Ordered document structures.'))

    def test_explicit_caption_rule_overrides_model_without_mutating_model_score(self):
        row=line('caption','Figure 31.3.2: Schematic of the system.',20,30)
        page={'page':1,'width':600,'height':800,'lines':[row]}
        features=s.role_features(row,page,s.document_profile([page]))
        probs=[.55,.01,.01,.01,.02,.01,.35,.01,.02,.01]
        decision=s.role_decision(features,probs)
        self.assertEqual(decision['predicted_role'],'body')
        self.assertEqual(decision['assigned_role'],'caption')
        self.assertEqual(decision['rule'],'explicit-caption-prefix-or-block-label')
        self.assertEqual(decision['score'],.55)
        prose=line('prose','Figure 31.3.2 shows the overall system.',20,30)
        page={'page':1,'width':600,'height':800,'lines':[prose]}
        features=s.role_features(prose,page,s.document_profile([page]))
        self.assertEqual(s.role_decision(features,probs)['assigned_role'],'body')

    def test_local_caption_block_context_and_reference_section_context(self):
        title=line('title','1. Fabrication flow for the CNT computer. (338 KB)',40,40,210,block=4,index=0)
        desc=line('desc','Steps 1-4 prepare the final substrate for circuit fabrication.',40,52,210,block=4,index=1)
        ref_heading=line('rh','VII. REFERENCES',120,40,90,block=5)
        ref=line('ref','• G. Almasi, C. J. Archer, 2005, a publication title.',40,55,220,block=6)
        page={'page':1,'width':600,'height':800,'lines':[title,desc,ref_heading,ref]}
        profile=s.document_profile([page])
        self.assertEqual(s.role_features(title,page,profile)[s.ROLE_FEATURES.index('caption_start')],1.)
        self.assertEqual(s.role_features(desc,page,profile)[s.ROLE_FEATURES.index('native_caption_context')],1.)
        self.assertEqual(s.role_features(ref,page,profile)[s.ROLE_FEATURES.index('reference_section_context')],1.)

    def test_table_caption_label_propagates_only_within_its_native_block(self):
        label=line('table-label','TABLE VI',310,40,40,block=8,index=0)
        desc=line('table-desc','ERROR ANALYSIS OF 3 BY 3 MULTIPLIERS',300,52,180,block=8,index=1)
        page={'page':1,'width':600,'height':800,'lines':[label,desc]}
        profile=s.document_profile([page])
        probs=[.8,.02,.02,.02,.02,.02,.02,.02,.02,.02]
        for row in [label,desc]:
            features=s.role_features(row,page,profile)
            self.assertEqual(s.role_decision(features,probs)['assigned_role'],'caption')
        other=line('cell','A measured table value.',310,90,40,block=9)
        page['lines'].append(other)
        other_features=s.role_features(other,page,profile)
        self.assertFalse(other_features[s.ROLE_FEATURES.index('explicit_caption_label')])

    def test_front_matter_author_and_affiliation_blocks_are_metadata(self):
        authors=[line('a1','Alice Smith1,',40,60,100,block=4,index=0),
                 line('a2','Bob Jones2*,',150,60,100,block=4,index=1),
                 line('a3','Carol Doe3*',260,60,100,block=4,index=2)]
        affiliation=[line('i1','Department of Engineering',40,100,180,block=5,index=0),
                     line('i2','Example State University',40,112,180,block=5,index=1),
                     line('i3','contact@example.org',40,124,180,block=5,index=2)]
        page={'page':1,'width':600,'height':800,'lines':authors+affiliation}
        profile=s.document_profile([page]);probs=[.8,.02,.02,.02,.02,.02,.02,.02,.02,.02]
        af=s.role_features(authors[0],page,profile)
        inf=s.role_features(affiliation[0],page,profile)
        self.assertEqual(af[s.ROLE_FEATURES.index('author_line_context')],1.)
        self.assertEqual(inf[s.ROLE_FEATURES.index('affiliation_block_context')],1.)
        self.assertEqual(s.role_decision(af,probs)['assigned_role'],'metadata')
        self.assertEqual(s.role_decision(inf,probs)['assigned_role'],'metadata')

    def test_list_continuation_stops_after_completed_item(self):
        start=line('start','1) A numbered contribution begins here',40,40,220,block=4,index=0)
        continuation=line('continuation','and its wrapped continuation stays in this block.',55,52,200,block=4,index=1)
        prose=line('prose','A separate prose paragraph follows the numbered list.',40,68,220,block=5,index=0)
        page={'page':1,'width':600,'height':800,'lines':[start,continuation,prose]}
        profile=s.document_profile([page])
        start_f=s.role_features(start,page,profile)
        continuation_f=s.role_features(continuation,page,profile)
        prose_f=s.role_features(prose,page,profile)
        self.assertEqual(start_f[s.ROLE_FEATURES.index('list_start')],1.)
        self.assertEqual(continuation_f[s.ROLE_FEATURES.index('list_continuation_context')],1.)
        self.assertEqual(prose_f[s.ROLE_FEATURES.index('list_continuation_context')],0.)

    def test_list_continuation_can_cross_a_short_native_block_boundary(self):
        start=line('start','2) Making the XNOR/XOR resilient with MTJ and designing',40,40,220,block=4,index=0)
        continuation=line('continuation','an SEU-hardened PCSA using a C-element.',55,52,200,block=5,index=0)
        prose=line('prose','A separate prose paragraph follows the list item.',40,66,220,block=6,index=0)
        page={'page':1,'width':600,'height':800,'lines':[start,continuation,prose]}
        profile=s.document_profile([page])
        self.assertEqual(s.role_features(continuation,page,profile)[s.ROLE_FEATURES.index('list_continuation_context')],1.)
        self.assertEqual(s.role_features(prose,page,profile)[s.ROLE_FEATURES.index('list_continuation_context')],0.)

    def test_equation_evidence_does_not_spread_to_nearby_body_block(self):
        equation=line('equation','Q = I × R',220,40,80,block=1)
        equation['font']='CMEX10';equation['spans'][0]['font']='CMEX10'
        body=line('body','A full explanatory sentence remains ordinary body text.',40,58,250,block=2,index=0)
        page={'page':1,'width':600,'height':800,'lines':[equation,body]}
        profile=s.document_profile([page])
        equation_f=s.role_features(equation,page,profile)
        body_f=s.role_features(body,page,profile)
        self.assertEqual(equation_f[s.ROLE_FEATURES.index('display_equation_context')],1.)
        self.assertEqual(body_f[s.ROLE_FEATURES.index('display_equation_context')],0.)

    def test_vector_graphic_text_is_detected_as_label_context(self):
        label=line('pin','PIN04',120,70,24,block=1)
        page={'page':7,'width':600,'height':800,'lines':[label],
              'graphic_regions':[[100,60,300,100]]}
        features=s.role_features(label,page,s.document_profile([page]))
        probabilities=[.8,.02,.02,.02,.02,.02,.02,.02,.02,.02]
        self.assertEqual(features[s.ROLE_FEATURES.index('graphic_context')],1.)
        self.assertEqual(s.role_decision(features,probabilities)['assigned_role'],'label')
        sidebar=line('sidebar','A long explanatory sidebar sentence remains body text.',24,120,215)
        page['lines'].append(sidebar)
        page['graphic_regions']=[[0,80,270,700]]
        sidebar_features=s.role_features(sidebar,page,s.document_profile([page]))
        self.assertEqual(sidebar_features[s.ROLE_FEATURES.index('graphic_context')],0.)

    def test_title_band_captures_moderately_larger_first_page_title(self):
        title=line('title','A Useful Hardware Platform for Material Computation',80,70,300)
        title['size']=14;title['bbox'][3]=84
        title['spans'][0]['size']=14;title['spans'][0]['bbox'][3]=84
        body=line('body','The measured physical properties define the computation.',40,180,300,index=1)
        body['size']=10
        body['spans'][0]['size']=10
        page={'page':1,'width':600,'height':800,'lines':[title,body]}
        self.assertEqual(s.document_profile([page])['title_band'],[70,84])

    def test_running_furniture_uses_page_edges_not_lower_body_rows(self):
        body=line('body','A final paragraph line still belongs to the article text.',40,720,260)
        footer=line('footer','Journal of Examples 12 (2024)',40,782,180)
        page={'page':2,'width':600,'height':800,'lines':[body,footer]}
        profile=s.document_profile([page])
        body_features=s.role_features(body,page,profile)
        footer_features=s.role_features(footer,page,profile)
        self.assertEqual(body_features[s.ROLE_FEATURES.index('running_header_context')],0.)
        self.assertEqual(footer_features[s.ROLE_FEATURES.index('running_header_context')],1.)
        probs=[.8,.02,.02,.02,.02,.02,.02,.02,.02,.02]
        self.assertEqual(s.role_decision(body_features,probs)['assigned_role'],'body')
        self.assertEqual(s.role_decision(footer_features,probs)['assigned_role'],'metadata')

    def test_explicit_metadata_does_not_spread_to_title_in_same_native_block(self):
        title=line('title','A Structured Analysis of Document Layout',40,40,270,block=4,index=0)
        doi=line('doi','DOI: 10.0000/example.2024.12',40,54,220,block=4,index=1)
        page={'page':1,'width':600,'height':800,'lines':[title,doi]}
        profile=s.document_profile([page])
        title_features=s.role_features(title,page,profile)
        doi_features=s.role_features(doi,page,profile)
        self.assertFalse(title_features[s.ROLE_FEATURES.index('explicit_metadata_label')])
        self.assertTrue(doi_features[s.ROLE_FEATURES.index('explicit_metadata_label')])

    def test_section_labels_and_math_fonts_get_specific_roles(self):
        heading=line('heading','Introduction',40,40,100)
        formula=line('formula','Qinj',240,120,25,block=2)
        formula['font']='MTSY10';formula['spans'][0]['font']='MTSY10'
        page={'page':1,'width':600,'height':800,'lines':[heading,formula]}
        profile=s.document_profile([page]);probs=[.8,.02,.02,.02,.02,.02,.02,.02,.02,.02]
        heading_features=s.role_features(heading,page,profile)
        equation_features=s.role_features(formula,page,profile)
        self.assertEqual(s.role_decision(heading_features,probs)['assigned_role'],'heading')
        self.assertEqual(equation_features[s.ROLE_FEATURES.index('display_equation_context')],1.)
        self.assertEqual(s.role_decision(equation_features,probs)['assigned_role'],'equation')

    def test_unmarked_model_list_prediction_falls_back_to_body(self):
        row=line('body','The material was processed on the same device for every sample.',40,40,260)
        page={'page':1,'width':600,'height':800,'lines':[row]}
        features=s.role_features(row,page,s.document_profile([page]))
        probabilities=[.01,.01,.01,.01,.01,.01,.01,.01,.01,.92]
        decision=s.role_decision(features,probabilities)
        self.assertEqual(decision['predicted_role'],'list')
        self.assertEqual(decision['assigned_role'],'body')
        self.assertEqual(decision['rule'],'reject-list-without-marker-or-continuation')

    def test_detected_table_region_is_an_explicit_role_constraint(self):
        row=line('cell','A table cell value.',150,120,80)
        page={'page':1,'width':600,'height':800,'lines':[row],
              'structure_regions':[[100,100,400,300]]}
        features=s.role_features(row,page,s.document_profile([page]))
        self.assertEqual(features[s.ROLE_FEATURES.index('table_region')],1.)
        probabilities=[.01,.01,.01,.01,.01,.01,.01,.01,.9,.01]
        decision=s.role_decision(features,probabilities)
        self.assertEqual(decision['assigned_role'],'table')
        self.assertEqual(decision['rule'],'source-table-cell-region')

    def test_wrapped_figure_number_and_section_heading_do_not_start_lists(self):
        prior=line('prior','The schematic is shown in Fig.',40,100,220)
        wrapped=line('wrapped','6. A data word is applied to the circuit.',40,112,220,index=1)
        heading=line('heading','1. Introduction',40,170,200,block=1)
        body=line('body','The next paragraph remains ordinary prose.',40,190,220,block=2)
        page={'page':2,'width':600,'height':800,'lines':[prior,wrapped,heading,body]}
        profile=s.document_profile([page])
        self.assertFalse(s.list_marker(wrapped,page))
        self.assertEqual(s.role_features(body,page,profile)[s.ROLE_FEATURES.index('list_continuation_context')],0.)
        self.assertIsNone(s.join_gate(prior,wrapped,'body','body'))
        self.assertTrue(s.LIST_START.match('(a) a real list item'))
        self.assertFalse(s.LIST_START.match('(CNTFETs) are devices'))

    def test_native_adjacency_uses_physical_rows_not_span_indices(self):
        first=line('first','A source line contains a superscript.',40,100,220,index=0)
        next_row=line('next','Its continuation preserves the printed order.',40,112,220,index=5)
        blank=line('blank',' ',40,111,10,index=4)
        page={'page':2,'width':600,'height':800,'lines':[first,blank,next_row]}
        features=s.join_features(first,next_row,page,('body','body'))
        self.assertEqual(features[s.JOIN_FEATURES.index('native_adjacent')],1.)

    def test_terminal_citation_preserves_paragraph_boundary(self):
        first=line('first','The first paragraph ends here. [ 16–22 ]',40,100,220)
        next_row=line('next','Another paragraph starts.',50,112,210,index=1)
        self.assertTrue(s.terminal_sentence(first['text']))
        self.assertEqual(s.join_gate(first,next_row,'body','body'),'paragraph-indent-after-terminal')

    def test_caption_without_punctuation_and_split_native_blocks(self):
        start=line('caption','Figure 1 (a) A source device and its measured response',40,100,220)
        continuation=line('continued','under each of the reported conditions.',40,118,220,block=1)
        page={'page':2,'width':600,'height':800,'lines':[start,continuation]}
        features=s.role_features(continuation,page,s.document_profile([page]))
        self.assertTrue(s.caption_start('FIGURE 3 Photoelectric mechanism of the source device.'))
        self.assertFalse(s.caption_start('Figure 3 shows the source device.'))
        self.assertTrue(features[s.ROLE_FEATURES.index('native_caption_context')])

    def test_reviewed_group_order_overrides_pdf_serialization_order(self):
        from structure_annotation_contract import reviewed_group_lines
        right=line('right','continues in the next column.',330,80,220,block=0)
        left=line('left','The same source paragraph',40,700,220,block=1)
        for row in [right,left]:row['_group']='same';row['_role']='body'
        page={'lines':[right,left],'_order_regions':[['left'],['right']]}
        self.assertEqual([row['id'] for row in reviewed_group_lines(page)['same']],['left','right'])
        page['_order_regions']=[['left'],['left']]
        with self.assertRaisesRegex(ValueError,'Repeated'):reviewed_group_lines(page)

    def test_source_body_at_page_top_is_not_running_furniture(self):
        rows=[line(str(i),'The ordinary paragraph continues across source lines.',40,55+i*12,220,index=i) for i in range(8)]
        page={'page':2,'width':600,'height':800,'lines':rows}
        features=s.role_features(rows[0],page,s.document_profile([page]))
        self.assertFalse(features[s.ROLE_FEATURES.index('running_header_context')])

    def test_title_metadata_and_running_header_rules_use_page_structure(self):
        title=line('title','A General Document Analysis Study',160,120,260)
        title['size']=20;title['bbox'][3]=140
        title['spans'][0]['size']=20;title['spans'][0]['bbox'][3]=140
        keyword=line('keyword','Keywords: parsing, layout, evaluation',160,300,260,index=1)
        body=line('body','The department at Example University reviewed the samples.',160,400,300,index=2)
        page={'page':1,'width':600,'height':800,'lines':[title,keyword,body]}
        profile=s.document_profile([page]);profile['title_band']=[120,140]
        profile['front_matter_bottom']=None
        title_features=s.role_features(title,page,profile)
        keyword_features=s.role_features(keyword,page,profile)
        running=line('running','8 A. Author, B. Writer, et al.',135,50,190,index=2)
        running_page={'page':8,'width':600,'height':800,'lines':[running]}
        running_features=s.role_features(running,running_page,profile)
        body_features=s.role_features(body,page,profile)
        article_type=line('article-type','full paper',572,75,16,block=9)
        article_page={'page':1,'width':600,'height':800,'lines':[article_type]}
        article_features=s.role_features(article_type,article_page,s.document_profile([article_page]))
        body_probs=[.8,.02,.02,.02,.02,.02,.02,.02,.02,.02]
        title_probs=[.02,.8,.02,.02,.02,.02,.02,.02,.02,.02]
        self.assertEqual(s.role_decision(title_features,title_probs)['assigned_role'],'title')
        self.assertEqual(s.role_decision(title_features,title_probs)['rule'],None)
        self.assertEqual(title_features[s.ROLE_FEATURES.index('title_band')],1.)
        self.assertEqual(s.role_decision(keyword_features,body_probs)['assigned_role'],'metadata')
        self.assertEqual(s.role_decision(article_features,body_probs)['assigned_role'],'metadata')
        self.assertEqual(s.role_decision(running_features,body_probs)['assigned_role'],'body')
        self.assertEqual(s.role_decision(body_features,body_probs)['assigned_role'],'body')
        self.assertEqual(s.role_decision(body_features,body_probs)['rule'],None)
        profile['repeated_furniture']=[s.furniture_key(running,running_page)]
        repeated_features=s.role_features(running,running_page,profile)
        self.assertEqual(repeated_features[s.ROLE_FEATURES.index('repeated_furniture')],1.)
        self.assertEqual(s.role_decision(repeated_features,body_probs)['assigned_role'],'metadata')
        self.assertEqual(s.role_decision(repeated_features,body_probs)['rule'],'repeated-marginal-running-furniture')

    def test_broad_table_boundary_is_recovered_from_nested_vector_grid(self):
        import fitz
        doc=fitz.open();page=doc.new_page(width=600,height=800)
        page.draw_line((100,200),(500,200));page.draw_line((100,400),(500,400))
        for x in (400,450,500):page.draw_line((x,200),(x,400))
        raw=s.raw_page(page)
        self.assertTrue(any(r[0]<=100.5 and r[2]>=499.5 and r[1]<=200.5 and r[3]>=399.5 for r in raw['structure_regions']))
        doc.close()

    def test_model_validation_rejects_corrupt_network_and_tree(self):
        head={'mean':[0.,0.],'scale':[1.,1.],'weights':[[.1],[.2]],'bias':[0.],
              'output':[[.3,.4]],'output_bias':[0.,0.]}
        s.validate_head(head,2,2)
        for key,value in [('scale',[0.,1.]),('weights',[[.1]]),('output_bias',[math.nan,0.])]:
            bad=copy.deepcopy(head);bad[key]=value
            with self.assertRaises(ValueError):s.validate_head(bad,2,2)
        tree={'left':[1,-1,-1],'right':[2,-1,-1],'feature':[0,-2,-2],
              'threshold':[.5,-2,-2],'value':[[.5,.5],[1.,0.],[0.,1.]]}
        forest={'kind':'extra-trees','feature_count':2,'classes':2,'trees':[tree]}
        s.validate_head(forest,2,2)
        self.assertEqual(s.predict_many(forest,[[0,0],[1,0]]),[[1.,0.],[0.,1.]])
        cyclic=copy.deepcopy(forest);cyclic['trees'][0]['left'][0]=0
        with self.assertRaisesRegex(ValueError,'Cyclic'):s.validate_head(cyclic,2,2)

    def test_split_leakage_and_invalid_training_inputs_are_rejected(self):
        a={'id':'a','split':'train','source_sha256':'a'*64,'pages':[{'raw_sha256':'page-a'}]}
        b={'id':'b','split':'test','source_sha256':'a'*64,'pages':[{'raw_sha256':'page-b'}]}
        with self.assertRaisesRegex(ValueError,'Repeated source'):trainer.validate_document_splits([a,b])
        b['source_sha256']='b'*64;b['pages'][0]['raw_sha256']='page-a'
        with self.assertRaisesRegex(ValueError,'Repeated native'):trainer.validate_document_splits([a,b])
        for rows in [[],[([math.nan]*len(s.ROLE_FEATURES),0,'owned-synthetic-a')]]:
            with self.assertRaises(ValueError):trainer.train_head(rows,10,173,1,'role')

    def test_wider_role_head_has_requested_parameter_shape(self):
        samples=[]
        for i in range(len(s.ROLES)):
            features=[0.0]*len(s.ROLE_FEATURES);features[i]=float(i+1)
            samples.append((features,i,'owned-synthetic-test'))
        head=trainer.train_head(samples,len(s.ROLES),173,1,'role',hidden=72)
        self.assertEqual(head['architecture'],[len(s.ROLE_FEATURES),72,len(s.ROLES)])
        self.assertEqual(len(head['weights'][0]),72)
        with self.assertRaisesRegex(ValueError,'Hidden units'):
            trainer.train_head(samples,len(s.ROLES),173,1,'role',hidden=513)

    def test_repaired_source_cannot_reenter_as_independent_test(self):
        a={'id':'original','split':'train','source_sha256':'a'*64,'pages':[]}
        b={'id':'repaired','split':'test','source_sha256':'b'*64,'source_parent_sha256':['a'*64],'pages':[]}
        with self.assertRaisesRegex(ValueError,'source family'):trainer.validate_document_splits([a,b])
        with tempfile.TemporaryDirectory() as tmp:
            labels=Path(tmp)/'labels.json';labels.write_text(json.dumps({'documents':[b]}))
            model=Path(tmp)/'model.json'
            provenance={'training':{'real_train_source_sha256':['a'*64],'real_validation_source_sha256':[]}}
            with patch.object(s,'load_model',return_value=provenance):
                with self.assertRaisesRegex(ValueError,'participated in fitting'):
                    corpus.evaluate(labels,model,Path(tmp)/'result.json')
            provenance['training']={'real_train_source_sha256':['b'*64],'real_train_source_family_sha256':['a'*64]}
            b.update(source_sha256='c'*64,source_parent_sha256=['a'*64]);labels.write_text(json.dumps({'documents':[b]}))
            with patch.object(s,'load_model',return_value=provenance):
                with self.assertRaisesRegex(ValueError,'participated in fitting'):
                    corpus.evaluate(labels,model,Path(tmp)/'result.json')

    def test_empty_eligible_edge_set_reports_unmeasured_not_perfect(self):
        row=line('only','Unresolved source row.',40,40)
        row.update(_role='body',_group='one',_assembly_unresolved=True,_pair_excluded=True)
        page={'page':1,'lines':[row],'_order_regions':[['only']]}
        doc={'id':'unresolved','split':'test','source_sha256':'a'*64,'source_page_count':1,'pages':[page],'profile':{}}
        result={'line_roles':[{'line_id':'only','assigned_role':'body'}],
                'blocks':[{'role':'body','line_ids':['only']}],'coverage':{'pass':True}}
        with tempfile.TemporaryDirectory() as tmp:
            labels=Path(tmp)/'labels.json';labels.write_text(json.dumps({'documents':[doc]}))
            model=Path(tmp)/'model.json';model.write_text('{}');out=Path(tmp)/'results.json'
            with patch.object(s,'load_model',return_value={}),patch.object(s,'reconstruct',return_value=result):
                corpus.evaluate(labels,model,out)
            evaluation=json.loads(out.read_text());metrics=evaluation['documents'][0]
            for key in ['join_precision','join_recall','join_f1']:self.assertIsNone(metrics[key])
            self.assertIn('unmeasured',metrics['join_metric_status'])
            self.assertEqual(metrics['exact_prose_groups'],0)
            self.assertFalse(evaluation['all_documents_99_percent'])

    def test_equation_fragments_use_unordered_region_membership_not_prose_edges(self):
        prose=[line('p1','The original measured result is described',40,40),
               line('p2','under the stated source conditions.',40,52)]
        equation=[line('q1','A(x) =',40,100),line('q2','B(x).',210,100)]
        rows=prose+equation
        for row in prose:row.update(_role='body',_group='prose')
        for row in equation:row.update(_role='equation',_group='display')
        page={'page':1,'width':600,'height':800,'lines':rows,
              '_order_regions':[['p1','p2'],['q1','q2']]}
        doc={'id':'spatial-equation','split':'test','source_sha256':'c'*64,
             'source_page_count':1,'pages':[page],'profile':{}}
        result={'line_roles':[{'line_id':row['id'],'assigned_role':row['_role']} for row in rows],
                'blocks':[{'role':'body','line_ids':['p1','p2']},
                          {'role':'equation','line_ids':['q1','q2']}],
                'relations':[],'coverage':{'pass':True}}
        with tempfile.TemporaryDirectory() as tmp:
            labels=Path(tmp)/'labels.json';labels.write_text(json.dumps({'documents':[doc]}))
            model=Path(tmp)/'model.json';model.write_text('{}');out=Path(tmp)/'results.json'
            with patch.object(s,'load_model',return_value={}),patch.object(s,'reconstruct',return_value=result):
                corpus.evaluate(labels,model,out)
            metrics=json.loads(out.read_text())['documents'][0]
        self.assertEqual(metrics['join_true_positive'],1)
        self.assertEqual(metrics['join_false_negative'],0)
        self.assertEqual(metrics['equation_region_membership']['exact_recall'],1)
        self.assertEqual(metrics['equation_region_membership']['exact_precision'],1)
        self.assertIn('symbol transcription',metrics['equation_region_membership']['scope'])

    def test_unresolved_concurrent_layers_do_not_score_an_invented_reading_order(self):
        rows=[line('a','First competing source layer.',40,40),line('b','Second competing source layer.',40,40)]
        for row in rows:row.update(_role='body',_group=row['id'],_assembly_unresolved=True,
                                   _unresolved_reason='Overlapping native layers.',_pair_excluded=True)
        page={'page':1,'lines':rows,'_order_regions':[['a'],['b']], '_order_unresolved':True}
        doc={'id':'concurrent-layers','split':'test','source_sha256':'b'*64,
             'source_page_count':1,'pages':[page],'profile':{}}
        result={'line_roles':[{'line_id':'a','assigned_role':'body'},
                              {'line_id':'b','assigned_role':'body'}],
                'blocks':[{'role':'body','line_ids':['a']},{'role':'body','line_ids':['b']}],
                'relations':[],'coverage':{'pass':True}}
        with tempfile.TemporaryDirectory() as tmp:
            labels=Path(tmp)/'labels.json';labels.write_text(json.dumps({'documents':[doc]}))
            model=Path(tmp)/'model.json';model.write_text('{}');out=Path(tmp)/'results.json'
            with patch.object(s,'load_model',return_value={}),patch.object(s,'reconstruct',return_value=result):
                corpus.evaluate(labels,model,out)
            metrics=json.loads(out.read_text())['documents'][0]
        self.assertIsNone(metrics['reading_order_accuracy'])
        self.assertEqual(metrics['reading_order_truth_coverage'],0)
        self.assertIn('partial-reading-order-truth',metrics['certification_blockers'])

    def test_damaged_source_glyph_cannot_be_promoted_to_equation(self):
        row=line('damaged','\x17a = \x03 b + \x1c',40,40)
        page={'page':1,'width':600,'height':800,'lines':[row]}
        features=s.role_features(row,page,s.document_profile([page]))
        self.assertEqual(features[s.ROLE_FEATURES.index('bad_char')],0)
        features[s.ROLE_FEATURES.index('display_equation_context')]=1
        probabilities=[.001]*len(s.ROLES)
        probabilities[s.ROLES.index('equation')]=.99
        result=s.role_decision(features,probabilities,source_text=row['text'])
        self.assertEqual(result['assigned_role'],'body')
        self.assertTrue(result['review_required'])
        self.assertEqual(result['rule'],'damaged-native-glyph-not-equation')

    def test_damaged_source_glyph_cannot_be_confidently_promoted_to_title(self):
        row=line('damaged','\x07\x13\x1a garbled title',40,40)
        page={'page':1,'width':600,'height':800,'lines':[row]}
        features=s.role_features(row,page,s.document_profile([page]))
        features[s.ROLE_FEATURES.index('title_band')]=1
        probabilities=[.001]*len(s.ROLES)
        probabilities[s.ROLES.index('title')]=.99
        result=s.role_decision(features,probabilities,source_text=row['text'])
        self.assertEqual(result['assigned_role'],'body')
        self.assertTrue(result['review_required'])
        self.assertEqual(result['rule'],'damaged-native-glyph-review')

    def test_native_text_damage_lowers_role_truth_coverage_without_becoming_a_guess(self):
        clean=line('clean','A source paragraph.',40,40);clean.update(_role='body',_group='clean')
        damaged=line('damaged','A source \x03 paragraph.',40,60);damaged.update(_role='body',_group='damaged')
        page={'page':1,'lines':[clean,damaged],'_order_regions':[['clean','damaged']]}
        doc={'id':'damaged-native-text','split':'test','source_sha256':'a'*64,
             'source_page_count':1,'pages':[page],'profile':{}}
        result={'line_roles':[{'line_id':'clean','assigned_role':'body'},
                              {'line_id':'damaged','assigned_role':'body'}],
                'blocks':[{'role':'body','line_ids':['clean']},{'role':'body','line_ids':['damaged']}],
                'relations':[],'coverage':{'pass':True}}
        with tempfile.TemporaryDirectory() as tmp:
            labels=Path(tmp)/'labels.json';labels.write_text(json.dumps({'documents':[doc]}))
            model=Path(tmp)/'model.json';model.write_text('{}');out=Path(tmp)/'results.json'
            with patch.object(s,'load_model',return_value={}),patch.object(s,'reconstruct',return_value=result):
                corpus.evaluate(labels,model,out)
            metrics=json.loads(out.read_text())['documents'][0]
        self.assertEqual(metrics['role_examples'],1)
        self.assertEqual(metrics['role_accuracy'],1)
        self.assertEqual(metrics['role_truth_coverage'],.5)
        self.assertEqual(metrics['unresolved_source_text_rows'],1)
        self.assertEqual(metrics['source_text_integrity_status'],'source-review-required')
        self.assertTrue(
            {'missing-role-truth','role_truth_coverage-below-99-or-unmeasured'}
            & set(metrics['certification_blockers'])
        )
        self.assertFalse(metrics['document_99_percent'])

    def test_unresolved_composite_role_is_excluded_from_accuracy_but_blocks_coverage(self):
        resolved=line('a','A paragraph line.',40,40);resolved.update(_role='body',_group='g')
        composite=line('b','Acknowledgements: supported by a grant.',40,60);composite.update(
            _role='metadata',_role_unresolved=True,_assembly_unresolved=True,
            _pair_excluded=True,_group='mixed')
        page={'page':1,'lines':[resolved,composite],'_order_regions':[['a','b']]}
        doc={'id':'composite-role','split':'test','source_sha256':'a'*64,
             'source_page_count':1,'pages':[page],'profile':{}}
        result={'line_roles':[{'line_id':'a','assigned_role':'body'},
                              {'line_id':'b','assigned_role':'body'}],
                'blocks':[{'role':'body','line_ids':['a']},
                          {'role':'body','line_ids':['b']}],
                'relations':[],'coverage':{'pass':True}}
        with tempfile.TemporaryDirectory() as tmp:
            labels=Path(tmp)/'labels.json';labels.write_text(json.dumps({'documents':[doc]}))
            model=Path(tmp)/'model.json';model.write_text('{}');out=Path(tmp)/'results.json'
            with patch.object(s,'load_model',return_value={}),patch.object(s,'reconstruct',return_value=result):
                corpus.evaluate(labels,model,out)
            metrics=json.loads(out.read_text())['documents'][0]
        self.assertEqual(metrics['role_examples'],1)
        self.assertEqual(metrics['role_accuracy'],1)
        self.assertEqual(metrics['role_truth_coverage'],.5)
        self.assertEqual(metrics['unresolved_role_rows'],1)
        self.assertIn('missing-role-truth',metrics['certification_blockers'])
        self.assertFalse(metrics['document_99_percent'])

    def test_certification_requires_all_corpus_truth(self):
        row={'document':'original','source_sha256':'source-a','full_document_truth':True,
             'role_truth_coverage':1,'assembly_truth_coverage':1,'reading_order_truth_coverage':1,
             'native_accounting_pass':True,'role_accuracy':1,'join_precision':1,'join_recall':1,
             'reading_order_accuracy':1,'exact_prose_group_accuracy':1,'content_structure_metrics':{k:{'source_review_complete':True,'accuracy':1}
                for k in ['table_structure','equation_structure','figure_ownership','source_text_integrity','cross_page_assembly']}}
        self.assertTrue(corpus.certification_gate([copy.deepcopy(row)],['source-a'])['pass'])
        for key,value in [('full_document_truth',False),('role_truth_coverage',.999),
                          ('reading_order_accuracy',None),('exact_prose_group_accuracy',.98),('ambiguous_group_rows_excluded',1),('content_structure_metrics',{})]:
            bad=copy.deepcopy(row);bad[key]=value
            self.assertFalse(corpus.certification_gate([bad],['source-a'])['pass'])
        self.assertFalse(corpus.certification_gate([row],['source-a','missing-source'])['pass'])

    def test_assembly_evaluation_masks_overlapping_uncertainty_once(self):
        rows=[line('known','A source paragraph.',40,40),line('unknown','A source fragment.',40,60)]
        rows[0].update(_role='body',_group='known')
        rows[1].update(_role='body',_assembly_unresolved=True,_role_unresolved=True)
        page={'page':1,'lines':rows}
        doc={'id':'partial-labels','split':'validation','pages':[page],'profile':{}}
        result={'line_roles':[{'line_id':r['id'],'assigned_role':'body'} for r in rows],
                'blocks':[{'role':'body','line_ids':[r['id']]} for r in rows],
                'coverage':{'pass':True}}
        with tempfile.TemporaryDirectory() as tmp:
            labels=Path(tmp)/'labels.json';labels.write_text(json.dumps({'documents':[doc]}))
            model=Path(tmp)/'model.json';model.write_text('{}');out=Path(tmp)/'results.json'
            with patch.object(s,'load_model',return_value={}),patch.object(s,'reconstruct',return_value=result):
                corpus.evaluate(labels,model,out)
            metrics=json.loads(out.read_text())['documents'][0]
        self.assertEqual(metrics['assembly_truth_coverage'],.5)
        self.assertEqual(metrics['eligible_prose_groups'],1)
        self.assertEqual(metrics['unscorable_prose_groups'],1)
        self.assertEqual(metrics['eligible_exact_prose_group_accuracy'],1)
        self.assertEqual(metrics['exact_prose_group_accuracy'],.5)
        self.assertFalse(metrics['document_99_percent'])

    def test_reference_ingest_retains_entry_and_encoding_warning(self):
        row=line('a','[1] Example A. Title. Journal 12. 2024. \ufffd',40,40)
        page={'page':1,'lines':[row],'native_lines':[row],'raw_sha256':'original'}
        result={'blocks':[{'role':'reference','type':'paragraph','text':row['text'],'bbox':row['bbox'],
            'line_ids':['a'],'native_line_ids':['a'],'level':2,'typography':{},'review_required':True,'operations':[]}], 'issues':[]}
        prepared={'pages':{1:page},'profile':{},'model_path':'model','model_sha256':'model-sha','pipeline_sha256':'pipeline-sha'}
        with tempfile.TemporaryDirectory() as tmp,patch.object(s,'reconstruct',return_value=result):
            content={'sources':[{'id':'D001','next_block_index':1}],'blocks':[],'issues':[]}
            _,warnings=adapter.append_page(Path(tmp),content,'D001',1,prepared,'auto',t.add_block,t.split_text)
            self.assertEqual(len(content['blocks'][0]['units']),1)
            self.assertEqual(content['blocks'][0]['units'][0]['source'],row['text'])
            self.assertTrue(any(w['code']=='text-encoding-review' for w in warnings))

    def test_only_adjacent_group_rows_are_positive_training_edges(self):
        rows=[line(str(i),'A sufficiently long narrative row.',40,40+i*12,index=i) for i in range(3)]
        for row in rows:row.update(_role='body',_group='same-paragraph')
        page={'page':1,'width':600,'height':800,'lines':rows}
        doc={'id':'original-fixture','pages':[page],'profile':s.document_profile([page])}
        _,pairs=trainer.examples([doc]);self.assertEqual(sum(p[1] for p in pairs),2)
        self.assertTrue(any(p[1]==0 and p[0][s.JOIN_FEATURES.index('baseline_step')]>2 for p in pairs))

    def test_training_examples_skip_whitespace_and_include_multicolumn_positive_edges(self):
        blank=line('blank',' ',20,100);body=line('body','Visible source text.',20,120,index=1)
        for row in (blank,body):row.update(_role='body',_group='body')
        roles,_=trainer.examples([{'id':'blank-fixture','pages':[{'page':1,'width':600,'height':800,'lines':[blank,body]}],'profile':s.document_profile([{'page':1,'width':600,'height':800,'lines':[blank,body]}])}])
        self.assertEqual(len(roles),1)
        docs=trainer.synthetic(36,173);positive_columns=set();positive_edges=0
        for doc in docs:
            for page in doc['pages']:
                lines=[x for x in page['lines'] if x['text'].strip()]
                transitions=s.column_transition_pairs(lines,page['width'],page['height'])
                groups={}
                for line0 in lines:groups.setdefault(line0.get('_group',line0['id']),[]).append(line0)
                adjacent={(a['id'],b['id']) for group in groups.values() for a,b in zip(group,group[1:])}
                for a,b in transitions:
                    if (a['id'],b['id']) in adjacent:
                        positive_edges+=1;positive_columns.add(doc['family'])
        self.assertGreater(positive_edges,0)
        self.assertIn('columns-2',positive_columns)
        self.assertIn('columns-3',positive_columns)

    def test_join_training_never_bridges_an_excluded_middle_row(self):
        rows=[line(str(i),'A sufficiently long source narrative row.',40,40+i*12,index=i) for i in range(3)]
        for row in rows:row.update(_role='body',_group='paragraph')
        rows[1]['_pair_excluded']=True
        page={'page':1,'width':600,'height':800,'lines':rows}
        roles,pairs=trainer.examples([{'id':'masked-middle','pages':[page],'profile':s.document_profile([page])}])
        self.assertEqual(len(roles),3)  # Pair uncertainty does not erase a known role.
        self.assertTrue(pairs)
        self.assertEqual(sum(p[1] for p in pairs),0)

    def test_training_masks_unknown_roles_and_assembly_independently(self):
        for flag in ('_role_unresolved','_assembly_unresolved','missing-group'):
            with self.subTest(flag=flag):
                rows=[line(str(i),'A sufficiently long source narrative row.',40,40+i*12,index=i) for i in range(2)]
                for row in rows:row.update(_role='body',_group='paragraph')
                if flag=='missing-group':rows[1].pop('_group')
                else:rows[1][flag]=True
                page={'page':1,'width':600,'height':800,'lines':rows}
                roles,pairs=trainer.examples([{'id':'uncertain-labels','pages':[page],'profile':s.document_profile([page])}])
                self.assertEqual(len(roles),1 if flag=='_role_unresolved' else 2)
                self.assertEqual(pairs,[])

    def test_training_report_accepts_legacy_annotation_without_label_source(self):
        row=line('a','A reviewed source paragraph.',40,40);row.update(_role='body',_group='g')
        page={'page':1,'width':600,'height':800,'lines':[row]}
        doc={'id':'legacy-reviewed','split':'train','pages':[page],'profile':s.document_profile([page])}
        with tempfile.TemporaryDirectory() as tmp:
            model=Path(tmp)/'model.json';evidence=Path(tmp)/'evidence.json'
            argv=['train_source_structure.py','--documents','0','--epochs','1','--output',str(model),'--evidence',str(evidence)]
            with patch.object(sys,'argv',argv),patch.object(trainer,'synthetic',return_value=[doc]),patch.object(trainer,'train_head',return_value={}),patch.object(trainer,'evaluate',return_value={'accuracy':None}),contextlib.redirect_stdout(io.StringIO()):
                trainer.main()
            self.assertEqual(json.loads(evidence.read_text())['splits'][0]['label_source'],'not-recorded')

    def test_table_cell_boundaries_override_same_baseline_recovery(self):
        a=line('a','A long cell entry that needs enough source characters',20,30,90)
        b=line('b','A separate cell',115,30,80,index=1)
        cells=[{'cells':[[10,20,110,50],[110,20,210,50]]}]
        rows=s.physical_rows([a,b],cells)
        self.assertEqual(len(rows),2);self.assertEqual([r['native_line_ids'] for r in rows],[['a'],['b']])

    def test_section_number_and_title_recover_one_baseline(self):
        a=line('a','2',20,30,6);a['flags']=16
        b=line('b','Methods',30,30,70,index=1)
        row=s.physical_rows([a,b])[0]
        self.assertEqual(row['text'],'2 Methods');self.assertEqual(row['native_line_ids'],['a','b'])

    def test_roman_small_caps_section_preserves_native_font_runs(self):
        a=line('a','III.',100,80,15)
        b=line('b','EXPERIMENTAL RESULTS',127,80,130,index=1)
        b['size']=8;b['spans'][0]['size']=8
        rows=s.physical_rows([a,b])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['text'],'III. EXPERIMENTAL RESULTS')
        self.assertEqual(rows[0]['native_line_ids'],['a','b'])
        self.assertEqual([span['size'] for span in rows[0]['spans']],[10,8])

    def test_inline_subscript_serialized_before_its_parent_uses_glyph_order(self):
        text='The measured N has a defined numerical value.'
        main=line('main',text,40,80,len(text)*4,index=1)
        main['spans'][0]['chars']=[{'c':c,'bbox':[40+i*4,80,44+i*4,90],
                                  'origin':[40+i*4,88]} for i,c in enumerate(text)]
        x=40+(text.index('N')+1)*4
        sub=line('sub','m',x,85,3,index=0);sub['size']=5
        sub['spans'][0].update(size=5,origin=[x,88],chars=[{'c':'m','bbox':[x,85,x+3,90],'origin':[x,88]}])
        rows=s.physical_rows([sub,main])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['text'],'The measured Nm has a defined numerical value.')
        self.assertEqual(set(rows[0]['native_line_ids']),{'main','sub'})
        self.assertTrue(rows[0]['inline_glyph_runs'])

    def test_repeated_ligature_encoding_is_retained_without_text_expansion(self):
        row=line('radical','ﬃﬃﬃﬃﬃ',40,80,30)
        text,operations=s.compose([row],set())
        self.assertEqual(text,'ﬃﬃﬃﬃﬃ')
        self.assertTrue(s.suspect_native_encoding(text))
        word=line('word','an ofﬁce',40,100,70)
        self.assertEqual(s.compose([word],set())[0],'an office')

    def test_trained_source_cannot_be_presented_as_blind_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            annotations=Path(tmp)/'truth.json'
            annotations.write_text(json.dumps({'documents':[{'id':'renamed-test',
                'source_sha256':'a'*64,'split':'test','pages':[]}]}))
            with patch.object(s,'load_model',return_value={'training':{
                'real_train_source_sha256':['a'*64]}}):
                with self.assertRaisesRegex(ValueError,'participated in fitting'):
                    corpus.evaluate(annotations,Path(tmp)/'model',Path(tmp)/'report')

    def test_wrapped_figure_reference_stays_in_prose_but_standalone_caption_remains(self):
        prose=line('p','The results are shown in the following comparison in',40,200,220)
        reference=line('r','Fig. 2. (a). A change is visible in the recorded data.',40,212,220,index=1)
        caption=line('c','Fig. 3. (a) The measured response.',40,400,200,block=2)
        page={'page':1,'width':600,'height':800,'lines':[prose,reference,caption]}
        self.assertFalse(s.caption_anchor(reference,page))
        self.assertTrue(s.caption_anchor(caption,page))
        f=s.role_features(reference,page,s.document_profile([page]))
        self.assertFalse(f[s.ROLE_FEATURES.index('caption_start')])
        self.assertFalse(f[s.ROLE_FEATURES.index('native_caption_context')])
        self.assertIsNone(s.join_gate(prose,reference,'body','body'))

    def test_table_header_does_not_inherit_caption_from_same_native_block(self):
        cap=line('cap','Table 1: Recorded values',300,200,200)
        cell=line('cell','Number',300,215,30,index=1)
        page={'page':1,'width':600,'height':800,'lines':[cap,cell],
              'table_regions':[{'bbox':[295,212,550,250]}]}
        f=s.role_features(cell,page,s.document_profile([page]))
        self.assertFalse(f[s.ROLE_FEATURES.index('native_caption_context')])
        self.assertFalse(f[s.ROLE_FEATURES.index('explicit_caption_label')])
        self.assertEqual(s.role_decision(f,[.8]+[.02]*9)['assigned_role'],'table')

    def test_mixed_native_block_retains_italic_subheading_and_table_caption(self):
        head=line('head','A. Device layout',40,200,100);head['flags']=2
        body=line('body','The device layout uses the measured source parameters.',40,215,230,index=1)
        cap=line('cap','TABLE 1. RECORDED VALUES FOR',40,300,200,block=2);cap['size']=8
        continuation=line('cont','VARIOUS TECHNOLOGIES',75,310,120,block=2,index=1);continuation['size']=8
        page={'page':2,'width':600,'height':800,'lines':[head,body,cap,continuation]}
        profile=s.document_profile([page])
        for row,role in [(head,'heading'),(continuation,'caption')]:
            features=s.role_features(row,page,profile)
            self.assertEqual(s.role_decision(features,[.8]+[.02]*9)['assigned_role'],role)

    def test_bibliography_full_names_and_quoted_title_start(self):
        for text in ['[6] Jean-Pierre Colinge, Recent advances in devices.',
                     '[7] A Gangadhar, A controlled measurement.',
                     '[10] G Estrin, A memory system.',
                     '[11] Daniel J Sorin, Low power memory.']:
            self.assertTrue(s.REFERENCE.search(text),text)
        self.assertFalse(s.REFERENCE.search('[11] have implemented the device in this study.'))

    def test_figure_band_does_not_cross_gutter_into_bibliography(self):
        caption=line('cap','Fig. 5. A source measurement.',40,300,230,block=0)
        ref=line('ref','pp. 436–441, March 2008.',315,150,160,block=1)
        ref['size']=7.8
        page={'page':4,'width':600,'height':800,'lines':[caption,ref]}
        profile=s.document_profile([page]);profile['body_size']=10
        f=s.role_features(ref,page,profile)
        self.assertFalse(f[s.ROLE_FEATURES.index('source_figure_band')])

    def test_illustrative_figure_reference_does_not_force_caption_role(self):
        row=line('prose','Fig. 1 (a) illustrates the proposed neuron model.',40,200,220)
        page={'page':2,'width':600,'height':800,'lines':[row]}
        self.assertFalse(s.caption_anchor(row,page))

    def test_scalar_vector_parity_and_rejection(self):
        head={'mean':[0.,0.],'scale':[1.,2.],'weights':[[.2,-.1],[.3,.4]],'bias':[0.,.1],
              'output':[[.4,-.2],[-.3,.1]],'output_bias':[.2,-.1]}
        rows=[[0.,1.],[3.,-2.]]
        a=s.predict_python(head,rows);b=s.predict_many(head,rows)
        for x,y in zip(a,b):
            for xx,yy in zip(x,y):self.assertAlmostEqual(xx,yy,places=12)
        for method in [s.predict_python,s.predict_many]:
            for invalid in [[[0]],[[math.nan,0]],[[0,math.inf]]]:
                with self.assertRaises(ValueError):method(head,invalid)

    def test_incompatible_model_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'model.json';p.write_text(json.dumps({'role_features':['wrong']}))
            with self.assertRaisesRegex(ValueError,'contract mismatch'):s.load_model(str(p))

    def test_narrow_two_and_three_column_order(self):
        rows=[]
        for col,x in enumerate([20,125,230]):
            rows.extend([line(f'{col}-a','Column prose',x,40,97,block=col),line(f'{col}-b','Continued prose',x,75,97,block=col,index=1)])
        self.assertEqual([r['id'] for r in s.order_regions(rows,340)],['0-a','0-b','1-a','1-b','2-a','2-b'])

    def test_same_right_edge_is_candidate_not_override(self):
        a=line('a','Text beside a floating object',80,30,140)
        b=line('b','Continuation beneath the object',30,42,190,index=1)
        self.assertIsNone(s.join_gate(a,b,'body','body'))
        self.assertEqual(s.join_gate(a,b,'body','caption'),'role-boundary')
        self.assertEqual(s.join_gate(a,b,'table','table'),'protected-structure')

    def test_column_end_to_next_column_start_is_a_learned_join_candidate(self):
        a=line('left-end','...memory logic bandwidth',40,700,220,block=0,index=10)
        b=line('right-start','wall [4] closes the same printed sentence.',330,70,220,block=1,index=0)
        page={'width':600,'height':800}
        self.assertEqual(s.column_transition_pairs([a,b],600,800),[(a,b)])
        self.assertIn((a,b),s.candidate_pairs([a,b],600,800))
        features=s.join_features(a,b,page,('body','body'),True)
        self.assertEqual(features[s.JOIN_FEATURES.index('column_transition')],1.)
        self.assertIsNone(s.join_gate(a,b,'body','body',True))
        self.assertEqual(s.join_gate(a,b,'caption','body',True),'role-boundary')

    def test_column_transition_ignores_centered_header_and_bottom_caption(self):
        rows=[]
        for i,y in enumerate([80,130,180,700]):rows.append(line('left-'+str(i),'Left column paragraph text.',40,y,210,block=0,index=i))
        for i,y in enumerate([80,130,180,220]):rows.append(line('right-'+str(i),'Right column continuation.',330,y,210,block=1,index=i))
        rows.append(line('center','Centered author metadata.',250,50,100,block=2))
        rows.append(line('caption','Last caption words.',40,750,200,block=3))
        pairs=s.column_transition_pairs(rows,600,800)
        self.assertEqual([(a['id'],b['id']) for a,b in pairs],[('left-3','right-0')])

    def test_column_transition_constraint_does_not_apply_local_baseline_penalty(self):
        a=line('left','a sentence fragment at the end of the left column',40,700,210,block=0,index=3)
        b=line('right','continues at the top of the next column',330,80,210,block=1,index=0)
        features=s.join_features(a,b,{'width':600,'height':800},('body','body'),True)
        self.assertEqual(trainer.constraint_cost(features,'join'),[0.,0.])

    def test_compose_never_completes_fragment(self):
        a=line('a','an unfinished source frag-',20,30)
        b=line('b','ment',20,42,index=1)
        text,ops=s.compose([a,b],set())
        self.assertEqual(text,'an unfinished source frag-ment')
        self.assertTrue(any(x['operation']=='retain-ambiguous-print-hyphen' for x in ops))
        self.assertEqual(a['text'],'an unfinished source frag-')

    def test_auto_native_table_and_explicit_native_routes(self):
        import fitz
        self.assertEqual(t.parser().parse_args(['ingest','p','a.pdf']).structure,'auto')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.pdf';doc=fitz.open();page=doc.new_page()
            page.insert_text((40,50),'Source heading',fontsize=19)
            page.insert_text((40,90),'A visible source paragraph.');doc.save(source);doc.close()
            for route,tables in [('auto',False),('auto',True),('native',False)]:
                dest=root/(route+str(tables))
                with contextlib.redirect_stdout(io.StringIO()):
                    t.init(argparse.Namespace(project=str(dest),title='Fixture',languages='zh-Hans',style='editorial',page_size='A4',columns=1))
                    t.ingest(argparse.Namespace(project=str(dest),files=[str(source)],pages=None,password=None,order='auto',tables=tables,structure=route,structure_model=None))
                _,_,content=t.project(dest)
                self.assertEqual(content['sources'][0]['structure']['route'],'ml' if route=='auto' and not tables else 'native')
                from refinement import validate_blocks
                self.assertEqual(validate_blocks(content),[])
            with self.assertRaisesRegex(ValueError,'Do not combine'):
                t.ingest(argparse.Namespace(project=str(dest),files=[str(source)],pages=None,password=None,order='auto',tables=True,structure='ml',structure_model=None))

    def test_default_model_and_real_ingest_preserve_evidence_without_translation(self):
        import fitz
        model=s.load_model();self.assertIsNotNone(model)
        self.assertEqual(model['role_head']['architecture'][0],len(s.ROLE_FEATURES))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.pdf';doc=fitz.open();p=doc.new_page()
            p.insert_text((40,50),'A source paragraph remains incomplete')
            p.insert_text((40,64),'and the visible continuation preserves 12.5 V.')
            doc.save(source);doc.close();project=root/'project'
            args=argparse.Namespace(project=str(project),title='Original fixture',languages='zh-Hans',style='editorial',page_size='A4',columns=1)
            with contextlib.redirect_stdout(io.StringIO()):
                t.init(args)
                t.ingest(argparse.Namespace(project=str(project),files=[str(source)],pages=None,password=None,order='auto',tables=False,structure='auto',structure_model=None))
            _,_,content=t.project(project);text=' '.join(u['source'] for _,u in t.units(content))
            self.assertIn('12.5 V.',text);self.assertIn('incomplete',text)
            route=content['sources'][0]['structure']
            self.assertEqual(route['route'],'ml');self.assertEqual(route['requested_route'],'auto')
            self.assertEqual(route['model_id'],'source-structure-1.0.2-r58-h192-region-h96')
            self.assertEqual(route['model_sha256'],__import__('hashlib').sha256(s.MODEL_PATH.read_bytes()).hexdigest())
            self.assertTrue(all(not u['translations'] for _,u in t.units(content)))
            from refinement import validate_blocks
            self.assertEqual(validate_blocks(content),[])
            ids=[lid for b in content['blocks'] for lid in b['source'].get('native_line_ids',[])]
            self.assertEqual(len(ids),2);self.assertEqual(len(ids),len(set(ids)))
            self.assertTrue(list((project/'reports/source-structure').glob('*.json.gz')))
            self.assertTrue(any(i['code']=='structure-source-review' and i['status']=='open' for i in content['issues']))


if __name__=='__main__':unittest.main()
