#!/usr/bin/env python3
"""Train a small, portable native table-cell adjacency classifier.

Original generated geometry has known cell membership. Optional reviewed native
annotations stay outside the public bundle. Splits are by complete document.
Copyright 2026 Yufeng Zhan. MIT.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import source_structure as structure
import table_learning as links


def synthetic(documents=600,seed=20261110):
    samples=[]
    for di in range(documents):
        rng=random.Random(seed+di*977);size=rng.uniform(6,14)
        family=di%6;document='original-table-'+str(di)
        font=rng.choice(['Times-Roman','Arial','CMR10','NotoSerif'])
        width=rng.uniform(80,150);x=rng.uniform(20,65);y=60
        rows=[];rules=[]
        for logical in range(rng.randint(4,10)):
            wrapped=family in {1,2,4} and rng.random()<.7
            prose=family in {2,3,5};parts=2 if wrapped else 1
            for part in range(parts):
                if prose:text=rng.choice(['Recorded response','Measurement uncertainty','Power per observation','Original conditions'])
                else:text=str(rng.randint(0,300)) if part==0 else '(Q = L, Qb = H)'
                if wrapped and part==1 and prose:text=rng.choice(['under stated conditions','per MAC (W)','Precision','of original samples'])
                w=min(width*.85,max(size*.8,len(text)*size*.43))
                xx=x+(width-w)/2+rng.uniform(-size*.12,size*.12)
                yy=y+part*size*rng.uniform(1.08,1.35)
                sz=size*rng.uniform(.94,1.04)
                row={'id':f'{document}-{logical}-{part}','text':text,'bbox':[xx,yy,xx+w,yy+sz],
                     'size':sz,'font':font,'flags':16 if family==4 else 0,
                     'native_block':logical if di%2 else 1,'spans':[{'text':text,'font':font,'size':sz,'origin':[xx,yy+sz*.8]}],
                     '_cell':logical}
                rows.append(row)
            y+=size*(rng.uniform(2.65,3.25) if wrapped else rng.uniform(1.05,2.0))
            if family==3 or rng.random()<.18:rules.append([x,y-size*.25,x+width])
        page={'fraction_rules':rules}
        for a,b in zip(rows,rows[1:]):
            samples.append({'x':links.features(a,b,page),'y':int(a['_cell']==b['_cell']),
                            'document':document,'family':family,'origin':'original-generator-ground-truth'})
        # Matching y/font is not evidence for joining neighbouring columns.
        for a in rows[:3]:
            b={**a,'id':a['id']+'other','native_block':a['native_block']+500,
               'bbox':[v+(width+20 if i%2==0 else 0) for i,v in enumerate(a['bbox'])]}
            samples.append({'x':links.features(a,b,page,False),'y':0,'document':document,
                            'family':family,'origin':'original-generator-ground-truth'})
    return samples


def fit(samples,seed=173,epochs=100):
    import numpy as np
    rng=np.random.default_rng(seed);raw=np.array([s['x'] for s in samples]);target=np.array([s['y'] for s in samples])
    mean=raw.mean(0);scale=np.maximum(raw.std(0),.1);x=np.clip((raw-mean)/scale,-12,12)
    w=rng.normal(0,.12,(len(links.FEATURES),32));b=np.zeros(32);v=rng.normal(0,.12,(32,2));vb=np.zeros(2)
    params=[w,b,v,vb];mom=[np.zeros_like(p) for p in params];var=[np.zeros_like(p) for p in params];step=0
    importance=np.array([4 if s['origin']=='source-inspected-development' else 1 for s in samples])
    freq=np.bincount(target,minlength=2);balance=len(target)/np.maximum(freq,1)/2
    curves=[]
    for epoch in range(epochs):
        loss=0
        for start in range(0,len(target),256):
            if start==0:order=rng.permutation(len(target))
            idx=order[start:start+256];xx=x[idx];yy=target[idx];n=len(idx)
            h=np.tanh(np.einsum('ij,jk->ik',xx,w,optimize=False)+b)
            z=np.einsum('ij,jk->ik',h,v,optimize=False)+vb
            e=np.exp(z-z.max(1,keepdims=True));p=e/e.sum(1,keepdims=True)
            loss+=float(-np.log(np.maximum(p[np.arange(n),yy],1e-12)).sum())
            dz=p.copy();dz[np.arange(n),yy]-=1;dz*=balance[yy,None]*importance[idx,None]/n
            # Measured separators and disjoint columns penalize false joins.
            incompatible=np.maximum(raw[idx,links.FEATURES.index('intervening_rule')],1-raw[idx,-1])
            penalty=.25*incompatible*(yy==0)
            dz[:,1]+=penalty*p[:,1]*(1-p[:,1])/n;dz[:,0]-=penalty*p[:,1]*p[:,0]/n
            dh=np.einsum('ij,kj->ik',dz,v,optimize=False)*(1-h*h)
            grads=[np.einsum('ij,ik->jk',xx,dh,optimize=False)+.0001*w,
                   dh.sum(0),np.einsum('ij,ik->jk',h,dz,optimize=False)+.0001*v,dz.sum(0)];step+=1
            for j,(param,grad) in enumerate(zip(params,grads)):
                mom[j]=.9*mom[j]+.1*grad;var[j]=.999*var[j]+.001*grad*grad
                param-=.004*(.2+.8*(1-epoch/epochs))*(mom[j]/(1-.9**step))/(np.sqrt(var[j]/(1-.999**step))+1e-8)
                if not np.isfinite(param).all():
                    raise ValueError('Non-finite table model parameters; training stopped.')
        if epoch%20==0 or epoch==epochs-1:curves.append({'epoch':epoch+1,'cross_entropy':loss/len(target)})
    cv=lambda a:np.round(a,9).tolist()
    network={'architecture':[len(links.FEATURES),32,2],'activation':'tanh','mean':cv(mean),'scale':cv(scale),
             'weights':cv(w),'bias':cv(b),'output':cv(v),'output_bias':cv(vb)}
    return network,curves


def evaluate(network,samples,threshold):
    probs=structure.predict_many(network,[x['x'] for x in samples]);tp=fp=fn=tn=0
    for row,p in zip(samples,probs):
        positive=p[1]>=threshold;truth=bool(row['y'])
        tp+=positive and truth;fp+=positive and not truth;fn+=not positive and truth;tn+=not positive and not truth
    return {'pairs':len(samples),'documents':len({s['document'] for s in samples}),
            'true_positive':tp,'false_positive':fp,'false_negative':fn,'true_negative':tn,
            'precision':tp/max(1,tp+fp),'recall':tp/max(1,tp+fn),'f1':2*tp/max(1,2*tp+fp+fn),
            'accuracy':(tp+tn)/max(1,len(samples)),'threshold':threshold,'calibrated_probability':False}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--evidence',type=Path,required=True)
    ap.add_argument('--annotations',type=Path);ap.add_argument('--documents',type=int,default=600)
    ap.add_argument('--epochs',type=int,default=120);ap.add_argument('--seed',type=int,default=20261110);args=ap.parse_args()
    generated=synthetic(args.documents,args.seed)
    # Entire documents stay in one split; sampled rows cannot cross splits.
    train=[s for s in generated if int(s['document'].rsplit('-',1)[1])%5 not in {0,1}]
    validation=[s for s in generated if int(s['document'].rsplit('-',1)[1])%5==1]
    holdout=[s for s in generated if int(s['document'].rsplit('-',1)[1])%5==0]
    actual=[];annotation_hash=None
    if args.annotations:
        annotation_hash=hashlib.sha256(args.annotations.read_bytes()).hexdigest()
        records=json.loads(args.annotations.read_text(encoding='utf-8'))
        for doc in records['documents']:
            if doc['split']!='train' or doc['label_provenance']!='source-inspected-development':raise ValueError('Require inspected training annotations.')
            for page in doc['pages']:
                lookup={r['id']:r for r in page['lines']}
                for pair in page['pairs']:
                    actual.append({'x':links.features(lookup[pair['from']],lookup[pair['to']],page),
                        'y':pair['same_cell'],'document':doc['source_sha256'],'origin':'source-inspected-development'})
        train.extend(actual)
    model,curve=fit(train,args.seed,args.epochs);threshold=.94
    report={'kind':'table-cell-link-development','seed':args.seed,'split':'whole-original-document',
        'train':evaluate(model,train,threshold),'synthetic_validation':evaluate(model,validation,threshold),
        'synthetic_holdout':evaluate(model,holdout,threshold),'real_development':evaluate(model,actual,threshold),
        'annotations_sha256':annotation_hash,'curve':curve,'semantic_accuracy_claimed':False,
        'limits':['Generated holdout measures generated geometry only.','Real source labels are development data, not an independent real-world holdout.',
                  'Cell links do not certify full grid, header hierarchy, text extraction, or translations.']}
    package={'id':'native-table-cell-links-1.0.3','version':'1.0.3','features':links.FEATURES,
             'classes':['different-cell','same-cell'],'threshold':threshold,'network':model,
             'training':{'seed':args.seed,'documents':args.documents,'annotation_sha256':annotation_hash,
                         'loss':'Class-balanced cross entropy plus source-separator false-join penalty',
                         'synthetic_holdout':report['synthetic_holdout'],'independent_real_accuracy':None},
             'author':'Yufeng Zhan','license':'MIT'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.evidence.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(package,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    report['model_sha256']=hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.evidence.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('model_sha256','train','synthetic_validation','synthetic_holdout','real_development')},indent=2))

if __name__=='__main__':main()
