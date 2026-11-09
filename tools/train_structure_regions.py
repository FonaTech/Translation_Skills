#!/usr/bin/env python3
"""Train an optional contextual structure head; stdlib-only exported inference.

Training requires NumPy. Original generated examples supplement source-reviewed
labels; never mix source families across splits or call selected-page scores
whole-document accuracy. Copyright 2026 Yufeng Zhan. MIT.
"""
from pathlib import Path
import argparse,copy,hashlib,json,random,sys,textwrap
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'skills/document-translation/scripts'),str(ROOT/'tools')]
import source_structure as s
import structure_regions as r
from train_source_structure import make_line, validate_document_splits
from structure_annotation_contract import source_identities


def synthetic(count,seed):
    docs=[]
    for di in range(count):
        rng=random.Random(seed+971*di);base=rng.uniform(8,14)
        font=rng.choice(['Times-Roman','CMR10','NotoSerif','Arial']);width=rng.choice([500,612,720]);height=842
        page={'page':3,'width':width,'height':height,'lines':[],'graphic_regions':[],'table_regions':[]}
        serial=0
        def add(text,x,y,size=None,ft=None,kind='retain',gid=None,bid=None,flags=0):
            nonlocal serial
            serial+=1
            row=make_line(text,x,y,size or base,ft or font,flags,serial if bid is None else bid,serial,page,'body',gid or str(serial),rng)
            row.update(_specialist=kind)
            page['lines'].append(row);return row
        cols=rng.choice([1,2,3]);cw=(width-80-(cols-1)*20)/cols
        for col in range(cols):
            x=40+col*(cw+20);y=55
            title=add(rng.choice(['3.2 Original observations','Method and operation','Recorded results']),x,y,base*rng.choice([1.,1.1,1.2,1.4]),font+'-Bold','heading',flags=16);y+=base*2
            text='The original observation remains valid under the stated conditions and its measured uncertainty is retained for the next experiment.'
            bid=serial+200
            parts=textwrap.wrap(text,max(18,int(cw/(base*.5))))
            for part in parts:
                row=add(part,x,y,kind='prose',gid='paragraph'+str(col),bid=bid);y+=base*1.25
            # Short algebraic tails are prose; ordinary display formulas below are not.
            add('at q = 0.',x,y,kind='prose',gid='paragraph'+str(col),bid=bid);y+=base*2.5
            commands=rng.choice([
                ['module demo (a, b, y);','input [3:0] a, b;','always @(a or b)','begin : named y = a & ~b;','end','endmodule'],
                ['def record(values):','for value in values:','if value > 0:','return value','return None'],
                ['const values = [1, 2];','function record(value) {','let result = value * 2;','return result;','}'],
                ['tool> read_hdl example.v','tool> create_clock -period 10 clk','tool> report_timing']])
            codefont=rng.choice(['CourierNew','Consolas','LiberationMono','Menlo']);size=base*rng.uniform(.8,1)
            for n,part in enumerate(commands):
                add(part,x+(size*2 if n and n<len(commands)-1 else 0),y,size,codefont,'code','code'+str(col));y+=size*1.5
            y+=base*2
            add('The next original paragraph describes a different observation.',x,y,kind='prose');y+=base*2
            # Real fraction layout: numerator, denominator, expression and number.
            eqid='equation'+str(col);ex=x+cw*.15
            add('−ℏ²',ex,y,base,'Symbol','math',eqid)
            add('2 m',ex,y+base*1.35,base*.85,font,'math',eqid)
            add('d² ψ = E ψ',ex+base*4,y+base*.7,base,'CambriaMath','math',eqid)
            add('(2.1)',min(width-55,x+cw-base*2.5),y+base*.7,base,font,'math',eqid);y+=base*4
            # Figure labels, caption, table and monospaced table negative examples.
            for n,label in enumerate(['Temperature T','Critical point','12.5']):
                rr=add(label,x+(n%2)*cw*.45,y+(n//2)*base*2,base*.8,font,'label')
                rr['bbox'][2]=min(x+cw,rr['bbox'][2])
            page['graphic_regions'].append([x-2,y-3,x+cw,y+base*4]);y+=base*4.5
            caption='Figure 2. An original source diagram. The measured quantities retain their units and the original conditions of observation, with every source qualification preserved.'
            cbid=serial+400
            for part in textwrap.wrap(caption,max(18,int(cw/(base*.8*.5)))):
                add(part,x,y,base*.8,font,'retain',gid='caption'+str(col),bid=cbid);y+=base
            y+=base
            add('Value    Range    Error',x,y,base*.8,codefont,'retain');y+=base*2
            lbid=serial+500
            for n,part in enumerate(textwrap.wrap('(2) Preserve every stated condition in the original observation. A wrapped explanation is still part of this numbered item and retains its original limits.',max(20,int(cw/(base*.5))))):
                add(part,x+(base*1.5 if n else 0),y,base,font,'retain',gid='list'+str(col),bid=lbid);y+=base*1.3
            y+=base
            # A superscript anchor is genuine; note may be a side note or bottom note.
            anchor=add('The original note is cited here.10',x,y,base,font,'prose')
            last=anchor['spans'][0];marker={**last,'text':'10','size':base*.7,'bbox':[last['bbox'][2]-5,y-3,last['bbox'][2],y+3],'origin':[last['bbox'][2]-5,y+base*.4]}
            anchor['spans']=[{**last,'text':'The original note is cited here.'},marker]
            y+=base*2.5;ns=base*rng.uniform(.75,.84);nx=x
            noteid='note'+str(col)
            first=add('10An original note preserves the source condition.',nx,y,ns,font,'footnote',noteid)
            span=first['spans'][0];ms=ns*rng.uniform(.72,.91)
            first['spans']=[{**span,'text':'10','size':ms,'bbox':[nx,y-3,nx+ms,y+ms-3],'origin':[nx,y+ns*.8-3]},
                            {**span,'text':'An original note preserves the source condition.','bbox':[nx+ms,y,span['bbox'][2],y+ns],'origin':[nx+ms,y+ns*.8]}]
            for li in range(rng.randint(1,6)):
                part=rng.choice(['Its continuation keeps the original qualification.','The source remains unchanged.','in the stated conditions, with a measured error,','independent observations, conditional assumptions,','and limits.'])
                add(part,nx,y+ns*(1.45+li*1.25),ns,font,'footnote',noteid,bid=serial+600)
            # Same-size bold subsection immediately before code or a list.
            hy=y+ns*10
            add('Procedure for the original measured system',x,hy,base,font+'-Bold','heading',flags=16)
            add('• Record the original value and its uncertainty.',x,hy+base*2,base,font,'retain')
        # Native running furniture remains retained even when short and bold.
        add('Example Technical Handbook',40,18,base*.8,font+'-Bold','retain',flags=16)
        add(str(20+di),width-55,height-22,base*.8,font,'retain')
        profile=s.document_profile([page]);profile.update(body_size=base*rng.uniform(.90,1.08),body_fonts=[font.casefold()])
        docs.append({'id':f'original-context-{di}','split':'train','profile':profile,'pages':[page]})
        # Index/contents typographic entries are distinct from free prose.
        for kind,title in [('index','Index'),('contents','Contents')]:
            p={'page':1,'width':width,'height':height,'lines':[],'graphic_regions':[],'table_regions':[]}
            old=page;page=p
            add(title,40,45,base*1.5,font+'-Bold','retain',flags=16)
            for n in range(8):
                text=(f'Original entry {n}, {12+n}, {41+n}' if kind=='index' else f'{n+1}. Original section ........ {12+n}')
                add(text,40+(base if n%3==1 else 0),85+n*base*1.4,base*.9,font,kind)
            docs.append({'id':f'original-{kind}-{di}','split':'train','profile':profile,'pages':[p]});page=old
    return docs


def examples(documents):
    samples=[]
    for doc in documents:
        for page in doc['pages']:
            ctx=r.context(page,doc['profile']);groups={}
            for row in page['lines']:
                if (row['id'] not in ctx or s.native_text_damaged(row['text']) or
                        row.get('_specialist') not in r.CLASSES or
                        row.get('_specialist_unresolved') or row.get('_role_unresolved')):continue
                info=ctx[row['id']];kind=row['_specialist']
                cost=[0.]*len(r.CLASSES)
                valid={'code':bool(info['code_group']),'footnote':bool(info['note_group']),
                       'math':bool(info['math_group']),'index':info['page_index'],'contents':info['page_contents']}
                for name,allowed in valid.items():cost[r.CLASSES.index(name)]=float(not allowed)
                # Annotation is authoritative. Record unsupported source relations
                # rather than teaching a contradictory geometry loss.
                conflict=bool(cost[r.CLASSES.index(kind)])
                if conflict:cost=[0.]*len(r.CLASSES)
                samples.append({'x':r.features(row,page,doc['profile'],ctx),'y':r.CLASSES.index(kind),
                                'cost':cost,'importance':8. if doc.get('source_sha256') else 1.,
                                'group':doc['id']+':'+str(page['page'])+':'+str(row['_group']),
                                'id':row['id'],'source':doc['id'],'conflict':conflict})
    return samples


def fit(samples,seed,epochs,hidden=96):
    if not 8<=hidden<=512:raise ValueError('Hidden units must be between 8 and 512.')
    import numpy as np
    def mm(a,b):return np.einsum('ni,ij->nj',a,b,optimize=False)
    rng=np.random.default_rng(seed);x=np.asarray([a['x'] for a in samples]);y=np.asarray([a['y'] for a in samples]);n=len(y);k=len(r.CLASSES)
    mean=x.mean(0);scale=x.std(0);scale[scale<.08]=1.;x=np.clip((x-mean)/scale,-12,12)
    importance=np.asarray([a['importance'] for a in samples]);cost=np.asarray([a['cost'] for a in samples])
    counts=np.bincount(y,minlength=k);cw=np.sqrt(n/np.maximum(counts,1)/k);cw=np.minimum(cw,4.)
    weights=importance*cw[y];weights/=weights.mean()
    pars=[rng.normal(0,.12,(x.shape[1],hidden)),np.zeros(hidden),rng.normal(0,.12,(hidden,k)),np.zeros(k)]
    moments=[np.zeros_like(p) for p in pars];vel=[np.zeros_like(p) for p in pars];step=0;logs=[]
    # Same verified literal/spatial region should retain a consistent role even
    # when its denominator/end/continuation has a different lexical signature.
    groups={}
    for i,a in enumerate(samples):
        if r.CLASSES[a['y']] in {'code','footnote','math'}:groups.setdefault(a['group'],[]).append(i)
    partners=np.arange(n)
    for ids in groups.values():
        for ia,ib in zip(ids,ids[1:]+ids[:1]):partners[ia]=ib
    for epoch in range(epochs):
        total=physical=consistency=0.
        for idx in np.array_split(rng.permutation(n),max(1,(n+255)//256)):
            xx=x[idx];yy=y[idx];q=x[partners[idx]];w=weights[idx];c=cost[idx];batch=len(idx)
            W,b,O,ob=pars
            h=np.tanh(mm(xx,W)+b);hq=np.tanh(mm(q,W)+b)
            z=mm(h,O)+ob;z-=z.max(1,keepdims=True);p=np.exp(z);p/=p.sum(1,keepdims=True)
            zq=mm(hq,O)+ob;zq-=zq.max(1,keepdims=True);pq=np.exp(zq);pq/=pq.sum(1,keepdims=True)
            ce=-np.log(np.maximum(1e-12,p[np.arange(batch),yy]));total+=float((ce*w).sum())
            geometry=(p*c).sum(1,keepdims=True);physical+=float(geometry.sum())
            delta=p-pq;consistency+=float((delta*delta).sum()/2)
            grad=p.copy();grad[np.arange(batch),yy]-=1;grad*=w[:,None]/batch
            grad+=.18*p*(c-geometry)/batch
            gp=.12*delta/batch;gq=-gp
            grad+=p*(gp-(gp*p).sum(1,keepdims=True))
            dq=pq*(gq-(gq*pq).sum(1,keepdims=True))
            dh=(mm(grad,O.T))*(1-h*h);dhq=(mm(dq,O.T))*(1-hq*hq)
            grads=[mm(xx.T,dh)+mm(q.T,dhq)+1e-5*W,(dh+dhq).sum(0),mm(h.T,grad)+mm(hq.T,dq)+1e-5*O,(grad+dq).sum(0)]
            step+=1;lr=.004*(.2+.8*(1-epoch/epochs))
            for j,g in enumerate(grads):
                moments[j]=.9*moments[j]+.1*g;vel[j]=.999*vel[j]+.001*g*g
                pars[j]-=lr*(moments[j]/(1-.9**step))/(np.sqrt(vel[j]/(1-.999**step))+1e-8)
        if epoch==0 or (epoch+1)%50==0 or epoch==epochs-1:
            log={'epoch':epoch+1,'cross_entropy':total/n,'geometry_loss':physical/n,'region_consistency_loss':consistency/n};logs.append(log);print(json.dumps(log),flush=True)
    W,b,O,ob=pars
    return {'mean':mean.tolist(),'scale':scale.tolist(),'weights':W.tolist(),'bias':b.tolist(),'output':O.tolist(),'output_bias':ob.tolist()},logs


def scores(head,samples):
    if not samples:return None
    probs=s.predict_many(head,[a['x'] for a in samples]);correct=sum(max(range(len(p)),key=p.__getitem__)==a['y'] for a,p in zip(samples,probs))
    by={}
    for a,p in zip(samples,probs):
        entry=by.setdefault(a['source'],{'correct':0,'rows':0,'conflicts':0});entry['rows']+=1;entry['correct']+=int(max(range(len(p)),key=p.__getitem__)==a['y']);entry['conflicts']+=int(a['conflict'])
    return {'accuracy':correct/len(samples),'correct':correct,'rows':len(samples),'by_source':by,
            'meaning':'raw specialist classification on selected annotated rows, before source gates; not final reconstruction or whole-document accuracy'}


def partition_documents(documents, base_model):
    """Keep test sources separate, including lineage already seen by base heads."""
    validate_document_splits(documents)
    partitions={name:[d for d in documents if d['split']==name]
                for name in ('train','validation','holdout','test')}
    seen=set()
    for provenance in (base_model.get('training',{}),
                       base_model.get('region_head',{}).get('training',{})):
        for name in ('real_train_source_sha256','real_validation_source_sha256',
                     'real_train_source_family_sha256','real_validation_source_family_sha256'):
            seen.update(provenance.get(name,[]))
    if any(source_identities(d)&seen for d in partitions['test']):
        raise ValueError('Test source participated in base model fitting or validation.')
    return partitions


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base-model',type=Path,required=True);ap.add_argument('--annotations',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--evidence',type=Path,required=True);ap.add_argument('--documents',type=int,default=100);ap.add_argument('--epochs',type=int,default=250);ap.add_argument('--hidden',type=int,default=96,help='Hidden units in the specialist region head (8-512).');ap.add_argument('--seed',type=int,default=173);a=ap.parse_args()
    if not 8<=a.hidden<=512:ap.error('--hidden must be between 8 and 512')
    data=json.loads(a.annotations.read_text());docs=data['documents'];model=json.loads(a.base_model.read_text())
    partitions=partition_documents(docs,model)
    train={d['source_sha256'] for d in partitions['train']};other={d['source_sha256'] for d in partitions['validation']}
    if train&other:raise ValueError('Source leakage across specialist splits.')
    # Explicitly reject source-family leakage when caller supplied family IDs.
    families={}
    for d in docs:
        family=d.get('source_family',d['source_sha256']);families.setdefault(family,set()).add(d['split'])
    if any(len(v)>1 for v in families.values()):raise ValueError('Source-family leakage.')
    training=examples(synthetic(a.documents,a.seed)+[d for d in docs if d['split']=='train'])
    validation=examples(partitions['validation'])
    holdout=examples(partitions['holdout']);test=examples(partitions['test'])
    head,curve=fit(training,a.seed,a.epochs,a.hidden)
    model.update(id=f'source-structure-v1.0.2-region-context-h{a.hidden}',region_head={'revision':r.REVISION,'features':r.FEATURES,'classes':r.CLASSES,'threshold':.9,'network':head})
    evidence={'version':'1.0.2','seed':a.seed,'base_model_sha256':hashlib.sha256(a.base_model.read_bytes()).hexdigest(),
              'annotation_sha256':hashlib.sha256(a.annotations.read_bytes()).hexdigest(),'source_module_sha256':hashlib.sha256(Path(s.__file__).read_bytes()).hexdigest(),
              'region_module_sha256':hashlib.sha256(Path(r.__file__).read_bytes()).hexdigest(),
              'architecture':[len(r.FEATURES),a.hidden,len(r.CLASSES)],'loss':{'supervised':'class-balanced cross entropy, inspected-source weight 8','geometry_weight':.18,'region_consistency_weight':.12,'curve':curve},
              'training_source_sha256':sorted(train),'validation_source_sha256':sorted(other),
              'training':scores(head,training),'validation':scores(head,validation),
              'holdout':scores(head,holdout),'test':scores(head,test),
              'test_source_sha256':sorted(d['source_sha256'] for d in partitions['test']),
              'whole_document_acceptance_evaluable':False,
              'scope':data.get('protocol'),'threshold_policy':'fixed .9 and .4 margin before validation; source-evidence gates remain mandatory'}
    # Keep private identities/evidence out of the redistributable checkpoint.
    model['region_head']['training']={'seed':a.seed,'architecture':evidence['architecture'],'original_synthetic_documents':a.documents,'source_training_documents':len(train),'selected_page_diagnostics':True,'whole_document_accuracy_certified':False,'real_train_source_sha256':sorted(train),'real_validation_source_sha256':sorted(other),'loss_weights':{'geometry':.18,'region_consistency':.12}}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(model,separators=(',',':'))+'\n');evidence['model_sha256']=hashlib.sha256(a.output.read_bytes()).hexdigest();a.evidence.write_text(json.dumps(evidence,indent=2)+'\n');s.load_model.cache_clear();s.load_model(str(a.output))
    print(json.dumps({'training_accuracy':evidence['training']['accuracy'],'training_rows':evidence['training']['rows'],'validation':evidence['validation'],'model':str(a.output)},indent=2))
if __name__=='__main__':main()
