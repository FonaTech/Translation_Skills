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
    def test_archived_preceding_prose_still_bounds_a_hidden_inline_math_tail(self):
        prior=styled('archived','The measured pressure and source conditions remain specified over the',40,180,block=7)
        tail=styled('tail','interval of [1, 2], here Pr = 2.',40,192,block=7,index=1)
        formula=styled('formula','F = 2 - P',105,209,font='CambriaMath',block=8)
        number=styled('number','(2)',510,209,block=9)
        p=page([tail,formula,number]);p['native_lines']=[prior,tail,formula,number]
        before=copy.deepcopy(p);ctx=r.context(p,profile(p))
        self.assertTrue(ctx['tail']['short_prose_tail'])
        self.assertIsNone(ctx['tail']['math_group'])
        self.assertIsNotNone(ctx['formula']['math_group'])
        self.assertEqual(ctx['formula']['math_group'],ctx['number']['math_group'])
        self.assertEqual(p,before)

    def test_coincident_source_and_ocr_numbers_keep_complete_fraction_together(self):
        padded=styled('source-number',' '*30+'(3)',300,200)
        chars=[]
        for i,char in enumerate(padded['text']):
            x=300+i*7 if i<30 else 510+(i-30)*4
            chars.append({'c':char,'bbox':[x,200,x+4,210],'origin':[x,208]})
        padded['spans'][0]['chars']=chars
        padded['bbox'][2]=522;padded['spans'][0]['bbox'][2]=522
        ocr=styled('ocr-number','(3)',510,199,size=9.5)
        ocr['bbox'][2]=522;ocr['spans'][0]['bbox'][2]=522
        rows=[styled('lhs','P =',120,200,font='CambriaMath'),
              styled('numerator','a + b',150,193,font='CambriaMath'),
              styled('denominator','n',155,209,font='CambriaMath'),padded,ocr]
        p=page(rows);before=copy.deepcopy(p);ctx=r.context(p,profile(p))
        owner=ctx['ocr-number']['math_group']
        self.assertIsNotNone(owner)
        for row in rows:self.assertEqual(ctx[row['id']]['math_group'],owner)
        self.assertEqual(p,before)

    def test_embedded_expression_number_and_ocr_share_one_region(self):
        embedded=styled('expression','x = y     (5)',100,200,font='CambriaMath')
        chars=[]
        for i,char in enumerate(embedded['text']):
            x=100+i*5 if i<10 else 510+(i-10)*4
            chars.append({'c':char,'bbox':[x,200,x+4,210],'origin':[x,208]})
        embedded['spans'][0]['chars']=chars
        embedded['bbox'][2]=522;embedded['spans'][0]['bbox'][2]=522
        ocr=styled('number','(5)',510,199,size=9.5)
        ocr['bbox'][2]=522;ocr['spans'][0]['bbox'][2]=522
        rows=[embedded,ocr,styled('ocr-expression','x = y',100,199,font='CambriaMath')]
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertIsNotNone(ctx['number']['math_group'])
        self.assertEqual({ctx[x['id']]['math_group'] for x in rows},{ctx['number']['math_group']})

    def test_repeated_or_differing_numbers_are_not_coincident_anchors(self):
        first=styled('first','(3)',510,200)
        repeated=styled('repeated','(3)',510,240)
        other=styled('other','(4)',510,200)
        shifted=styled('shifted','(3)',510,205)
        self.assertEqual(len(r.equation_anchor_groups([first,repeated,other,shifted],10)),4)
        rows=[]
        for number in [first,repeated]:
            rows.extend([styled(number['id']+'-formula','x = y',100,number['bbox'][1],font='CambriaMath'),number])
        p=page(rows);ctx=r.context(p,profile(p))
        for number in [first,repeated]:
            self.assertEqual(ctx[number['id']]['math_group'],ctx[number['id']+'-formula']['math_group'])
            self.assertIsNotNone(ctx[number['id']]['math_group'])
        self.assertNotEqual(ctx['first']['math_group'],ctx['repeated']['math_group'])

    def test_final_piecewise_branch_requires_connected_brace_and_native_alignment(self):
        rows=[styled('lhs','f =',100,208,font='CambriaMath'),
              styled('brace-top','⎧',135,190,font='CambriaMath'),
              styled('brace-middle','⎨',135,202,font='CambriaMath'),
              styled('brace-bottom','⎩',135,219,font='CambriaMath'),
              styled('first','1, q > 0',150,200,block=7),
              styled('last','0, Otherwise',150,220,block=7),
              styled('number','(4)',510,208),
              styled('outside','0, Outside the equation',150,245,block=7)]
        p=page(rows);ctx=r.context(p,profile(p));owner=ctx['number']['math_group']
        self.assertIsNotNone(owner)
        self.assertEqual(ctx['last']['math_group'],owner)
        self.assertNotEqual(ctx['outside']['math_group'],owner)
        # Neither similar wording nor unrelated native objects establish a
        # branch when the geometric source evidence is absent.
        rows[5]['native_block']=8
        self.assertNotEqual(r.context(p,profile(p))['last']['math_group'],owner)
        rows[5]['native_block']=7
        p['lines']=[row for row in rows if not row['id'].startswith('brace-')]
        self.assertNotEqual(r.context(p,profile(p))['last']['math_group'],owner)

    def test_numbered_fraction_inside_small_drawing_keeps_variable_and_multiply_dot(self):
        numerator=styled('top','I',150,193,font='Times-Italic')
        numerator['spans'][0]['flags']=2
        rows=[styled('lhs','Q =',100,200,font='CambriaMath'),
              styled('dot','·',135,200),numerator,
              styled('bottom','n',150,208,font='CambriaMath'),styled('number','(5)',510,200)]
        p=page(rows);p['graphic_regions']=[[147,190,164,204]];p['fraction_rules']=[(147,205,164)]
        pr=profile(p);ctx=r.context(p,pr)
        self.assertIsNotNone(ctx['number']['math_group'])
        self.assertEqual(ctx['top']['math_group'],ctx['number']['math_group'])
        self.assertEqual(ctx['dot']['math_group'],ctx['number']['math_group'])
        # A large figure remains a barrier, even with a small rule inside it.
        p['graphic_regions']=[[90,150,280,290]]
        self.assertIsNone(r.context(p,pr)['top']['math_group'])

    def test_extended_delimiters_use_actual_ink_for_adjacent_formula_ownership(self):
        import copy
        rows=[]
        for i,y in enumerate([200,230]):
            delimiter=styled('delimiter'+str(i),chr(4),140,y-20,font='CMEX10')
            delimiter['spans'][0]['chars']=[{'c':chr(4),'bbox':delimiter['bbox'][:],
                'origin':[140,y-12],'native_glyph':{'ink_bbox':[140,y-14,146,y+9],
                                                  'sha256':'source-outline'}}]
            rows.extend([styled('lhs'+str(i),'F =',100,y,font='CambriaMath'),delimiter,
                         styled('rhs'+str(i),'x + y',148,y,font='CambriaMath'),
                         styled('number'+str(i),'('+str(i+1)+')',510,y)])
        p=page(rows);before=copy.deepcopy(p);ctx=r.context(p,profile(p))
        for i in range(2):
            self.assertEqual(ctx['delimiter'+str(i)]['math_group'],ctx['number'+str(i)]['math_group'])
            self.assertNotEqual(ctx['delimiter'+str(i)]['math_group'],ctx['number'+str(1-i)]['math_group'])
        self.assertEqual(p,before)

    def test_roman_parenthetical_scripts_and_fraction_denominator_belong_to_display(self):
        lhs=styled('variable','V(c)',100,200,size=10,font='Times-Italic')
        lhs['spans']=[{'text':'V','size':10,'font':'Times-Italic','flags':2,'bbox':[100,200,106,210],'origin':[100,208]},
                      {'text':'(c)','size':6,'font':'Times-Roman','flags':0,'bbox':[106,196,114,202],'origin':[106,201]}]
        denominator=styled('denominator','d(logIDS)',150,211,size=10)
        denominator['spans']=[{'text':'d(logI','size':10,'font':'Times-Roman','flags':0,'bbox':[150,211,180,221],'origin':[150,219]},
                              {'text':'DS)','size':6,'font':'Times-Roman','flags':0,'bbox':[180,216,190,222],'origin':[180,221]}]
        denominator['bbox']=[150,211,190,222]
        rows=[lhs,styled('relation','=',120,200,font='CambriaMath'),
              styled('numerator','dV',155,196,font='CambriaMath'),denominator,
              styled('number','(7)',510,200)]
        p=page(rows);p['fraction_rules']=[(149,209,191)]
        ctx=r.context(p,profile(p));group=ctx['number']['math_group']
        self.assertIsNotNone(group)
        self.assertEqual(ctx['variable']['math_group'],group)
        self.assertEqual(ctx['denominator']['math_group'],group)
        p['fraction_rules']=[]
        self.assertIsNone(r.context(p,profile(p))['denominator']['math_group'])

    def test_centred_operator_limit_stays_with_previous_equation(self):
        rows=[styled('lhs','F(t) =',100,200,font='CambriaMath'),
              styled('operator','∑',140,192,font='CambriaMath'),
              styled('upper','m',143,189,size=6,font='CambriaMath'),
              styled('lower','i = 1',140,211,size=6,font='CambriaMath'),
              styled('rhs','w x',155,200,font='CambriaMath'),
              styled('first','(3)',510,200),
              styled('next-lhs','E =',100,230,font='CambriaMath'),
              styled('numerator','a + b + c',151,218,font='CambriaMath'),
              styled('denominator','n',172,235,font='CambriaMath'),
              styled('second','(4)',510,230)]
        # The limit is directly under its operator; the following numerator's
        # font box is closer vertically but does not enclose the limit's x-band.
        rows[1]['bbox'][2]=154;rows[1]['spans'][0]['bbox'][2]=154
        rows[3]['bbox'][2]=152;rows[3]['spans'][0]['bbox'][2]=152
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertIsNotNone(ctx['first']['math_group'])
        self.assertEqual(ctx['lower']['math_group'],ctx['first']['math_group'])
        self.assertNotEqual(ctx['lower']['math_group'],ctx['second']['math_group'])

    def test_numbered_display_keeps_upright_alternative_identifiers(self):
        rows=[styled('lhs','ABC or DEF',100,200),styled('relation','=',149,200,font='CambriaMath'),
              styled('rhs','x',165,200,font='CambriaMath'),styled('number','(6)',510,200)]
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertIsNotNone(ctx['number']['math_group'])
        self.assertEqual(ctx['lhs']['math_group'],ctx['number']['math_group'])

    def test_numbered_display_keeps_split_italic_function_fragments(self):
        fragment=styled('fragment','C ex',100,200,font='Times-Italic')
        fragment['spans'][0]['flags']=2
        rows=[fragment,styled('relation','p = x',118,200,font='CambriaMath'),styled('number','(6)',510,200)]
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertIsNotNone(ctx['number']['math_group'])
        self.assertEqual(ctx['fragment']['math_group'],ctx['number']['math_group'])

    def test_numbered_display_keeps_separate_descriptive_subscript(self):
        rows=[styled('lhs','I',100,200,font='Times-Italic'),styled('sub','peak',106,204,size=6),
              styled('relation','= x',125,200,font='CambriaMath'),styled('number','(6)',510,200)]
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertIsNotNone(ctx['number']['math_group'])
        self.assertEqual(ctx['sub']['math_group'],ctx['number']['math_group'])
        # A nearby regular word has no measured subscript parent.
        rows.insert(2,styled('word','comment',165,220,size=6))
        ctx=r.context(page(rows),profile(page(rows)))
        self.assertIsNone(ctx['word']['math_group'])

    def test_numbered_product_keeps_full_word_italic_variables(self):
        formula=styled('product','Delaymax × Powercell × Areacell',100,211,font='Times-Italic')
        formula['spans']=[]
        x=100
        for text,small in [('Delay',False),('max',True),('×',False),('Power',False),
                           ('cell',True),('×',False),('Area',False),('cell',True)]:
            formula['spans'].append({'text':text,'size':7 if small else 10,
                'font':'Times-Italic','flags':2,'bbox':[x,214 if small else 211,x+len(text)*3,221],
                'origin':[x,221 if small else 219]})
            x+=len(text)*3
        rows=[styled('lhs','Q = x',60,200,font='CambriaMath'),formula,styled('number','(7)',510,200)]
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertIsNotNone(ctx['number']['math_group'])
        self.assertEqual(ctx['product']['math_group'],ctx['number']['math_group'])

    def test_numbered_damaged_artwork_is_reviewed_without_claiming_neural_seed(self):
        rows=[styled('lhs','w = x',100,200,font='CambriaMath'),
              styled('anchor','y\x03 (4)',150,200,font='CambriaMath')]
        p=page(rows);d=decisions(rows)
        r.refine(rows,p,profile(p),d,{'network':{}},lambda h,x:probabilities(['prose']*len(x)))
        self.assertEqual(d['anchor']['assigned_role'],'equation')
        self.assertTrue(d['anchor']['review_required'])
        self.assertFalse(d['anchor']['region_prediction']['applied'])
        self.assertFalse(d['anchor']['provisional_region_prediction']['accepted'])
        self.assertEqual(d['anchor']['provisional_region_prediction']['class'],'prose')
        self.assertEqual(d['anchor']['region_evidence']['seed_line_ids'],[])

    def test_full_width_footer_does_not_open_numbered_region_to_other_column(self):
        rows=[]
        for i,y in enumerate([490,520,550,650]):
            rows.append(styled('right'+str(i),'A narrative paragraph that provides measured column boundaries.',320,y,block=i))
        rows.extend([styled('left','An unrelated paragraph in the other column at this vertical position.',40,599,block=20),
                     styled('formula','x = y',350,600,font='CambriaMath'),
                     styled('number','(7)',510,600)])
        footer=styled('footer','A full width copyright notice that reaches both columns at the page bottom.',30,740,block=21)
        footer['bbox'][2]=550;footer['spans'][0]['bbox'][2]=550;rows.append(footer)
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertIsNotNone(ctx['number']['math_group'])
        self.assertEqual(ctx['formula']['math_group'],ctx['number']['math_group'])
        self.assertIsNone(ctx['left']['math_group'])

    def test_numbered_display_keeps_upright_identifier_beside_relation(self):
        rows=[styled('lhs','ABC',100,200),styled('relation','=',115,200,font='CambriaMath'),
              styled('rhs','x',130,200,font='CambriaMath'),styled('number','(6)',510,200)]
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertIsNotNone(ctx['number']['math_group'])
        self.assertEqual(ctx['lhs']['math_group'],ctx['number']['math_group'])

    def test_numbered_fraction_keeps_roman_subscript_identifiers(self):
        rows=[styled('lhs','Q =',60,200,font='CambriaMath')]
        for lid,text,y in [('numerator','Vbias',194),('denominator','Rmem',210)]:
            row=styled(lid,text,86,y)
            row['spans']=[{'text':text[:1],'size':10,'font':'Times-Italic','flags':2,
                           'bbox':[86,y,92,y+10],'origin':[86,y+8]},
                          {'text':text[1:],'size':7,'font':'Times-Roman','flags':0,
                           'bbox':[92,y+3,112,y+10],'origin':[92,y+10]}]
            rows.append(row)
        rows.append(styled('number','(7)',510,200))
        p=page(rows);ctx=r.context(p,profile(p))
        for lid in ['numerator','denominator']:
            self.assertEqual(ctx[lid]['math_group'],ctx['number']['math_group'])
            self.assertIsNotNone(ctx[lid]['math_group'])

    def test_descriptive_subscripts_do_not_turn_display_into_prose(self):
        formula=styled('formula','Pstatic, SRAM = Ileakage × Vdd',100,200)
        formula['spans']=[]
        for text,x,small in [('P',100,False),('static, SRAM',106,True),('=',150,False),
                             ('I',162,False),('leakage',168,True),('×',200,False),
                             ('V',212,False),('dd',218,True)]:
            formula['spans'].append({'text':text,'size':7 if small else 10,
                'font':'Times-Roman','flags':0,'bbox':[x,203 if small else 200,x+len(text)*4,210],
                'origin':[x,210 if small else 208]})
        rows=[formula,styled('number','(8)',510,200)]
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertIsNotNone(ctx['formula']['math_group'])
        self.assertEqual(ctx['formula']['math_group'],ctx['number']['math_group'])

    def test_numbered_prose_relation_is_not_a_scripted_formula(self):
        prose=styled('prose','The current = voltage divided by resistance',100,200)
        prose['spans'].append({'text':'2','size':7,'font':'Times-Roman','flags':0,
                              'bbox':[310,196,314,203],'origin':[310,202]})
        rows=[prose,styled('number','(8)',510,200)]
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertIsNone(ctx['prose']['math_group'])

    def test_formula_boundary_exclusion_preserves_owned_glyphs_and_native_source(self):
        import fitz
        from vector_assets import source_crop_page
        with fitz.open() as doc:
            pg=doc.new_page(width=240,height=160)
            pg.insert_text((40,57),'Adjacent prose above',fontsize=10)
            pg.insert_text((40,68),'x + y = 2',fontsize=10)
            pg.insert_text((40,79),'Adjacent prose below',fontsize=10)
            pg.draw_line((40,70),(85,70))
            raw=s.raw_page(pg)
            native=raw['native_lines'];owned=next(r for r in native if r['text']=='x + y = 2')
            region={'bbox':owned['bbox'],'native_line_ids':[owned['id']]}
            decisions={'line_roles':[{'line_id':r['id'],'assigned_role':'equation' if owned['id'] in r.get('native_line_ids',[r['id']]) else 'body',
                                      'predicted_role':'equation' if owned['id'] in r.get('native_line_ids',[r['id']]) else 'body'} for r in raw['lines']]}
            crop=(fitz.Rect(region['bbox'])+(-2,-2,2,2)) & pg.rect
            exclusions=ingest.formula_crop_exclusions(raw,region,decisions,crop)
            self.assertTrue(exclusions)
            before=pg.get_pixmap().samples
            with source_crop_page(pg,exclusions) as isolated:
                self.assertIn('x + y = 2',isolated.get_text())
                self.assertNotIn('Adjacent prose',isolated.get_text())
                self.assertEqual(len(pg.get_drawings()),len(isolated.get_drawings()))
            self.assertEqual(before,pg.get_pixmap().samples)
            self.assertIn('Adjacent prose above',pg.get_text())
            self.assertTrue(all(raw['raw_sha256'] in e['evidence'] for e in exclusions))

    def test_formula_boundary_ambiguous_owned_boxes_are_never_redacted(self):
        import fitz
        owned={'id':'math','bbox':[40,40,70,60],'text':'x','spans':[{'font':'CambriaMath','chars':[{'c':'x','bbox':[40,40,70,60]}]}]}
        prose={'id':'prose','bbox':[30,39,80,42],'text':'a','spans':[{'font':'Times','chars':[{'c':'a','bbox':[45,40,50,42]}]}]}
        pg={'raw_sha256':'ledger','native_lines':[owned,prose],'lines':[owned,prose]}
        reg={'bbox':[40,40,70,60],'native_line_ids':['math']}
        result={'line_roles':[{'line_id':'prose','assigned_role':'body','predicted_role':'body'}]}
        self.assertEqual(ingest.formula_crop_exclusions(pg,reg,result,[38,38,72,62]),[])
        owned['spans'][0]['chars'][0]['c']='\x0b'
        self.assertEqual(ingest.formula_crop_exclusions(pg,reg,result,[38,38,72,62]),[])
        prose['spans'][0]['chars'][0]['bbox']=[30,39,35,42]
        result['line_roles'][0]['predicted_role']='equation'
        self.assertEqual(ingest.formula_crop_exclusions(pg,reg,result,[28,38,72,62]),[])
        pg.pop('native_lines')
        self.assertEqual(ingest.formula_crop_exclusions(pg,reg,result,[28,38,72,62]),[])

    def test_separately_owned_equation_is_removed_from_crop_padding_only(self):
        import fitz
        from vector_assets import source_crop_page
        with fitz.open() as doc:
            pg=doc.new_page(width=300,height=180)
            pg.insert_text((40,68),'x + y = 2',fontsize=10)
            pg.insert_text((40,80),'z + t = 4',fontsize=10)
            raw=s.raw_page(pg);first,second=raw['native_lines']
            def block(row):
                return {'semantic_role':'equation','representation':'source-spatial-region',
                        'native_line_ids':[row['id']]}
            result={'blocks':[block(first),block(second)]}
            region={'bbox':first['bbox'],'native_line_ids':[first['id']]}
            crop=fitz.Rect(first['bbox'])+(-2,-2,2,4)
            before=pg.get_pixmap().samples
            exclusions=ingest.formula_crop_exclusions(raw,region,result,crop)
            self.assertTrue(exclusions)
            self.assertTrue(all('separately owned equation' in e['reason'] for e in exclusions))
            with source_crop_page(pg,exclusions) as isolated:
                self.assertIn('x + y = 2',isolated.get_text())
                self.assertNotIn('z + t = 4',isolated.get_text())
            self.assertEqual(before,pg.get_pixmap().samples)
            # A role prediction by itself cannot authorize removing formula ink.
            result['blocks']=[]
            self.assertEqual(ingest.formula_crop_exclusions(raw,region,result,crop),[])

    def test_formula_evidence_separates_rejected_predictions_from_used_seeds(self):
        rows=[{'line_id':'raw','predicted_role':'equation','assigned_role':'equation',
               'region_prediction':{'class':'math','applied':False},
               'region_evidence':{'seed_line_ids':['used']}},
              {'line_id':'used','predicted_role':'body','assigned_role':'equation',
               'region_prediction':{'class':'math','applied':True}}]
        evidence=ingest.formula_provenance(rows,'model','sha')
        self.assertEqual(evidence['raw_role_prediction_line_ids'],['raw'])
        self.assertEqual(evidence['raw_region_prediction_line_ids'],['raw','used'])
        self.assertEqual(evidence['neural_seed_line_ids'],['used'])
        self.assertFalse(evidence['semantic_transcription'])

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

    def test_boolean_command_output_remains_literal_and_is_not_math(self):
        rows=[styled('total','Total: 2 items',40,100,font='CourierNew',block=2),
              styled('label','All attributes:',60,112,font='CourierNew',block=2,index=1),
              styled('assignment','async_clear = false',80,124,font='CourierNew',block=2,index=2)]
        p=page(rows);ds=decisions(rows)
        for d in ds.values():d.update(assigned_role='equation',predicted_role='body')
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},
                       lambda *args:probabilities(['retain','retain','code']))
        self.assertTrue(all(ds[x['id']].get('semantic_role')=='code' for x in rows))
        self.assertFalse(any(g['kind']=='equation' for g in r.structured_groups(rows,ds,ctx)))

    def test_unsupported_display_proposal_does_not_capture_a_prose_tail(self):
        rows=[styled('prose','The total energy is given by the equipartition',40,100,block=4),
              styled('tail','theorem',40,112,block=4,index=1)]
        p=page(rows);ds=decisions(rows)
        ds['tail'].update(assigned_role='equation',predicted_role='equation')
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},
                       lambda *args:probabilities(['prose','prose']))
        self.assertTrue(ctx['tail']['short_prose_tail'])
        self.assertEqual(ds['tail']['assigned_role'],'body')
        self.assertTrue(ds['tail']['review_required'])
        self.assertEqual(ds['tail']['predicted_role'],'equation')

    def test_roman_function_joins_numbered_cases_instead_of_extra_display(self):
        rows=[styled('function','exp',260,220,font='Times-Roman'),
              styled('rhs','−β(Ea − Eb)',280,220,font='CambriaMath'),
              styled('number','(6.88)',480,220)]
        p=page(rows);ds=decisions(rows)
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},
                       lambda *args:probabilities(['math','math','retain']))
        groups=r.structured_groups(rows,ds,ctx)
        self.assertEqual(len(groups),1)
        self.assertEqual({x['id'] for x in groups[0]['members']},{'function','rhs','number'})

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

    def test_damaged_inline_symbol_retains_clean_seed_note_ownership(self):
        rows=[note(),styled('mathnote','unless '+chr(29)+' = 0, with the qualification.',40,612,8),
              styled('tail','and the final source condition.',40,624,8)]
        p=page(rows);ds=decisions(rows)
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},
                       lambda *args:probabilities(['footnote','retain','retain']))
        self.assertEqual(ds['mathnote']['semantic_role'],'footnote')
        self.assertTrue(ds['mathnote']['review_required'])
        groups=r.structured_groups(rows,ds,ctx)
        self.assertEqual([x['id'] for x in groups[0]['members']],['note','mathnote','tail'])

    def test_nested_shell_path_seeds_literal_code_region(self):
        rows=[styled('prompt','tool:/libraries/slow/cells/ABC1> ls -l -a Y',40,100,font='CourierNew'),
              styled('result','async_clear = false',40,114,font='CourierNew')]
        p=page(rows);ds=decisions(rows)
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},
                       lambda *args:probabilities(['code','retain']))
        self.assertTrue(all(ds[x['id']].get('semantic_role')=='code' for x in rows))
        self.assertFalse(r.CODE.search('x > y'))

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

    def test_numbered_math_keeps_roman_scripts_and_operator_fragments(self):
        lhs=styled('lhs','Q =',100,200,font='CambriaMath')
        numerator=styled('n','A',145,194,font='CambriaMath')
        denominator=styled('d','Latencyoriginal',145,210,7,font='Times-Italic')
        denominator['spans']=[
            {'text':'Latency','font':'Times-Italic','flags':2,'size':10,
             'bbox':[145,210,174,220],'origin':[145,218]},
            {'text':'original','font':'Times-Italic','flags':2,'size':7,
             'bbox':[174,212,194,219],'origin':[174,220]}]
        fragment=styled('operator','+ TMR',202,202,font='Times-Italic')
        fragment['spans'][0]['flags']=2
        rows=[lhs,numerator,denominator,fragment,styled('number','(7)',500,200)]
        p=page(rows);ds=decisions(rows)
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},
                       lambda *args:probabilities(['math','retain','retain','retain','math']))
        group=next(g for g in r.structured_groups(rows,ds,ctx) if g['kind']=='equation')
        self.assertEqual({x['id'] for x in group['members']},{x['id'] for x in rows})

    def test_rotated_watermark_cannot_clip_numbered_equation(self):
        watermark=styled('watermark','Downloaded source with original terms and conditions retained.',575,10)
        watermark.update(direction=[0,1],bbox=[575,10,582,780])
        rows=[styled('before','The source paragraph introduces the following measured quantity.',40,165),
              styled('math','Q = x + y',100,200,font='CambriaMath'),
              styled('number','(8)',510,200),watermark,
              styled('after','The following paragraph states the source conditions explicitly.',40,245)]
        ctx=r.context(page(rows),profile(page(rows)))
        self.assertEqual(ctx['number']['math_group'],ctx['math']['math_group'])
        self.assertIsNotNone(ctx['math']['math_group'])
        self.assertIsNone(ctx['watermark']['math_group'])

    def test_numbered_broken_font_artwork_is_retained_without_mapping_guess(self):
        native=styled('native','Rate ¼ A',100,200,font='OpaqueText')
        native['spans']=[
            {'text':'Rate','font':'OpaqueText','flags':0,'size':10,
             'bbox':[100,200,120,210],'origin':[100,208]},
            {'text':' ¼','font':'OpaqueGlyphs','flags':0,'size':10,
             'bbox':[121,200,129,210],'origin':[121,208]},
            {'text':' A','font':'OpaqueItalic','flags':1,'size':10,
             'bbox':[130,195,140,205],'origin':[130,202]}]
        rows=[native,styled('fraction','f γ',135,212,font='CambriaMath'),
              styled('number','(3a)',510,200)]
        p=page(rows);ds=decisions(rows)
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},
                       lambda *args:probabilities(['retain','math','math']))
        self.assertEqual(ds['native']['assigned_role'],'equation')
        self.assertEqual(native['text'],'Rate ¼ A')
        self.assertEqual(ctx['native']['math_group'],ctx['number']['math_group'])

    def test_numbered_equation_does_not_capture_later_circuit_supply_labels(self):
        rows=[styled('math','Q = x + y',100,200,font='CambriaMath'),
              styled('number','(8)',510,200),
              styled('supply','+VDD/2',250,244,7),
              styled('caption','Figure 1. Original circuit diagram.',100,300)]
        p=page(rows);p['graphic_regions']=[[245,250,275,280]]
        ctx=r.context(p,profile(p))
        self.assertIsNotNone(ctx['number']['math_group'])
        self.assertNotEqual(ctx['supply']['math_group'],ctx['number']['math_group'])

    def test_figure_chain_cannot_override_numbered_math_seed(self):
        rows=[styled('math','Q = x + y',100,200,font='CambriaMath'),
              styled('script','R',130,211,7,font='Times-Italic'),
              styled('number','(8)',510,200),
              styled('label','Pin',150,245,7),
              styled('caption','Figure 1. Original circuit diagram.',90,290)]
        rows[1]['spans'][0]['flags']=2
        p=page(rows);p['graphic_regions']=[[100,235,220,270]];ds=decisions(rows)
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},
                       lambda *args:probabilities(['math','retain','math','label','retain']))
        self.assertEqual(ds['script']['semantic_role'],'equation')
        self.assertEqual(ds['script']['region_evidence']['group'],ctx['number']['math_group'])

    def test_marginal_numbered_math_keeps_rejected_neural_score_provisional(self):
        row=styled('formula','Q = Afast + Bslow (7)',100,60,7,font='CambriaMath')
        rows=[row];p=page(rows);ds=decisions(rows)
        ds['formula'].update(assigned_role='metadata',rule='page-margin-running-furniture')
        probs=[.16/(len(r.CLASSES)-1)]*len(r.CLASSES);probs[r.CLASSES.index('math')]=.84
        ctx,proposals=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},lambda *args:[probs])
        self.assertFalse(proposals['formula']['applied'])
        self.assertEqual(ds['formula']['semantic_role'],'equation')
        self.assertTrue(ds['formula']['review_required'])
        self.assertEqual(ds['formula']['region_evidence']['seed_line_ids'],[])
        evidence=ingest.formula_provenance([ds['formula']],'model','sha')
        self.assertEqual(evidence['neural_seed_line_ids'],[])
        self.assertTrue(evidence['role_fallback_pending_review'])

    def test_prose_referencing_parenthesized_number_is_not_embedded_display(self):
        row=styled('body','The original conditions follow Equation (7)',40,200)
        ctx=r.context(page([row]),profile(page([row])))
        self.assertIsNone(ctx['body']['math_group'])

    def test_numbered_equation_keeps_terminal_italic_script_product(self):
        product=styled('product','aNb.',155,200,font='Times-Italic')
        product['spans']=[
            {'text':'aN','font':'Times-Italic','flags':2,'size':10,
             'bbox':[155,200,168,210],'origin':[155,208]},
            {'text':'b','font':'Times-Italic','flags':2,'size':7,
             'bbox':[168,203,173,210],'origin':[168,210]},
            {'text':'.','font':'CambriaMath','flags':2,'size':10,
             'bbox':[173,200,176,210],'origin':[173,208]}]
        rows=[styled('lhs','Q = x',100,200,font='CambriaMath'),product,
              styled('number','(9)',510,200)]
        p=page(rows);ctx=r.context(p,profile(p))
        self.assertIsNotNone(ctx['product']['math_group'])
        self.assertEqual(ctx['product']['math_group'],ctx['number']['math_group'])

    def test_numbered_integral_keeps_roman_limit_and_same_baseline_explanation(self):
        integral=styled('integral','∫',121,190,font='CambriaMath')
        limit=styled('limit','path',126,214,7)
        left=styled('left','W =',105,202,font='CambriaMath')
        right=styled('right','P dV = enclosed area.',145,202,font='Times-Roman')
        rows=[left,integral,limit,right,styled('number','(5.8)',510,220)]
        p=page(rows);ds=decisions(rows)
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},
                       lambda *args:probabilities(['math','math','retain','prose','math']))
        self.assertEqual(ds['limit']['semantic_role'],'equation')
        self.assertEqual(ds['right']['semantic_role'],'equation')
        self.assertEqual(ctx['limit']['math_group'],ctx['right']['math_group'])

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

    def test_visible_integral_encoded_as_whitespace_stays_inside_display(self):
        integral=styled('integral','\r',110,190,font='CMEX10')
        integral['spans'][0]['chars']=[{'c':'\r','bbox':integral['bbox'][:],
                                       'origin':[110,198]}]
        rows=[integral,styled('rhs','W = F dx',125,200,font='CambriaMath'),
              styled('number','(2.3)',480,200)]
        p=page(rows);result=s.reconstruct(p,profile(p))
        group=next(b for b in result['blocks'] if b.get('semantic_role')=='equation')
        self.assertIn('integral',group['line_ids'])
        self.assertLessEqual(group['bbox'][1],190)
        self.assertNotIn('integral',result['coverage']['excluded'])
        self.assertTrue(result['coverage']['pass'])
        normal=styled('space','\r',40,100,font='Times-Roman')
        normal['spans'][0]['chars']=[{'c':'\r','bbox':normal['bbox'][:]}]
        self.assertFalse(s.source_text_present(normal))

    def test_piecewise_condition_inside_math_envelope_is_not_duplicate_prose(self):
        first=styled('left','x =',160,210,font='CambriaMath')
        top=styled('top','1',230,200,font='CambriaMath')
        bottom=styled('bottom','exp −βE',230,220,font='CambriaMath')
        condition=styled('condition','for E > 0',330,220,font='CambriaMath')
        num=styled('number','(3.2)',480,210)
        outside=styled('prose','For an independent measurement use the next equation.',40,250)
        rows=[first,top,bottom,condition,num,outside];p=page(rows);ds=decisions(rows)
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},
                       lambda *args:probabilities(['math','retain','math','retain','retain','prose']))
        group=next(g for g in r.structured_groups(rows,ds,ctx) if g['kind']=='equation')
        self.assertIn('condition',{x['id'] for x in group['members']})
        self.assertNotIn('prose',{x['id'] for x in group['members']})

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

    def test_fragmented_prose_baseline_does_not_create_inline_display(self):
        first=styled('first','For example, when the stored da',310,640,block=1)
        tail=styled('tail','ata S=1 and SB=0, if we',first['bbox'][2]-4,640,block=8)
        rows=[first,tail];p=page(rows);ds=decisions(rows)
        ds['tail'].update(assigned_role='equation',predicted_role='equation')
        ctx,_=r.refine(rows,p,profile(p),ds,{'network':{},'threshold':.9},
                       lambda *args:probabilities(['prose','math']))
        self.assertTrue(ctx['tail']['same_baseline_prose'])
        self.assertIsNone(ctx['tail']['math_group'])
        self.assertEqual(ds['tail']['assigned_role'],'body')
        self.assertEqual(tail['text'],'ata S=1 and SB=0, if we')

    def test_split_column_prose_bounds_a_numbered_stacked_fraction(self):
        left=styled('left','The source value is specified as x',40,50,block=1)
        tail=styled('left-tail','= 75 kΩ at room',left['bbox'][2]-3,50,block=7)
        right=styled('right','The right column source prose continues',310,100,block=8)
        right_tail=styled('right-tail','with its original qualification.',right['bbox'][2]-3,100,block=9)
        lhs=styled('lhs','PR =',325,55,font='CambriaMath',block=4)
        numerator=styled('numerator','W / L',355,49,7,font='CambriaMath',block=4)
        denominator=styled('denominator','W / L',355,63,7,font='CambriaMath',block=4)
        number=styled('number','(5)',550,55,block=10)
        rows=[left,tail,right,right_tail,lhs,numerator,denominator,number]
        p=page(rows);ctx=r.context(p,profile(p))
        gid=ctx['number']['math_group'];self.assertIsNotNone(gid)
        self.assertEqual({x['id'] for x in rows if ctx[x['id']]['math_group']==gid},
                         {'lhs','numerator','denominator','number'})
        self.assertIsNone(ctx['left-tail']['math_group'])

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
            self.assertIn('<path',(root/block['asset']).read_text( encoding='utf-8'))

if __name__=='__main__':unittest.main()
