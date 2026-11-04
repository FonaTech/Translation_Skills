#!/usr/bin/env python3
"""Collect actual DOM outcomes and train a small offline pairwise MLP ranker.

Training labels are disclosed engineering preferences, not human aesthetic ratings.
No private source text is included in this synthetic dataset.
"""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import math
import random
import os
import base64
import io

ROOT=Path(__file__).resolve().parent.parent
ASSETS=ROOT/'skills/document-translation/assets'
FEATURES=['invalid','overflow','errors','empty','sparse','mean_fill','fill_variation','tail_fill','imbalance','font_delta','leading_delta','spacing_delta','small_type','narrow_measure','page_expansion','figure_fraction','table_fraction','page_count','title_delta','caption_delta','table_type_delta','cell_padding_delta','column_gap_delta','interior_sparse']


def fixture(index,rng):
    language=['zh','en','mixed','ar'][index%4]
    prose={'zh':'这是一段用于测量文档版式的合成文字。参数变化应改变可见排版，同时完整保留原有内容、数字 12.5 和单位 V。',
           'en':'This synthetic paragraph measures typography, spacing and pagination. Preserve every character, the number 12.5 and the unit V while adjusting the layout.',
           'mixed':'Mixed-language layout: 中文与 English 保持原始内容。A figure, table or heading must remain traceable. 数值 −12.5 μm。',
           'ar':'هذه فقرة اصطناعية لقياس تخطيط المستند. يجب الحفاظ على النص والأرقام 12.5 والوحدات مع ضبط حجم الخط والمسافات.'}[language]
    d={'w':rng.choice([148,210,216,297]),'h':297,'mx':rng.choice([14,18,24]),'my':rng.choice([14,20,26]),'cols':rng.choice([1,2,3]),'gap':rng.choice([5,7,10]),'size':rng.choice([9.5,10.5,12,14]),'leading':rng.choice([1.4,1.65,1.9]),'para':rng.choice([1.2,3,7]),'head':rng.choice([2,5,10]),'tableSize':rng.choice([7.5,9,11]),'cellPad':rng.choice([.6,1.5,3]),'titleSize':22,'captionSize':8,'accent':'#304659'}
    if d['w']==148:d.update(h=210,cols=rng.choice([1,2]),mx=14)
    elif d['w']==297:d.update(h=210,cols=rng.choice([2,3]))
    html='<h1 data-title="true">Layout fixture '+str(index+1)+'</h1>'
    for i in range(rng.choice([2,5,9,14,22,35])):
        if i%5==0:html+='<h3>Section '+str(i+1)+'</h3>'
        html+='<p data-uid="f'+str(index)+'-'+str(i)+'">'+prose*rng.randint(1,4)+'</p>'
        if i==3 and index%3==0:
            # A real embedded raster exercises image accounting, loading and
            # figure features. A colored DIV is not counted as an image.
            from PIL import Image, ImageDraw
            canvas=Image.new('RGB',(360,180),'#f0f5f8');draw=ImageDraw.Draw(canvas)
            draw.line([(25,15),(25,155),(340,155)],fill='#526778',width=2)
            for k in range(6):
                h=25+(k*23+index*11)%115
                draw.rectangle((45+k*46,155-h,74+k*46,154),fill=['#18766f','#446b96','#b48543'][k%3])
            buffer=io.BytesIO();canvas.save(buffer,format='PNG')
            image='data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()
            html+='<figure data-span="'+('all' if index%2 else 'column')+'"><img src="'+image+'" alt="Original synthetic bar chart" style="width:100%;height:'+str(rng.choice([35,60,95]))+'mm;object-fit:contain"><figcaption>Figure 1. Original synthetic layout fixture.</figcaption></figure>'
        if i==5 and index%3==1:
            html+='<table><thead><tr><th>Item</th><th>Value</th><th>Unit</th></tr></thead><tbody>'+''.join('<tr><td>Measurement '+str(j)+'</td><td>'+str(j*12.5)+'</td><td>μm</td></tr>' for j in range(rng.randint(4,14)))+'</tbody></table>'
    return {'title':'Synthetic '+str(index+1),'html':html,'design':d,'overrides':{k:True for k in d},'familyClass':'family-source','route':'source','dir':'rtl' if language=='ar' else 'ltr'}


def collect(path,count,browser,seed):
    from playwright.sync_api import sync_playwright
    rng=random.Random(seed);records=[]
    with sync_playwright() as pw:
        br=pw.chromium.launch(headless=True,**({'executable_path':browser} if browser else {}))
        page=br.new_page(viewport={'width':1400,'height':1100})
        page.goto((ASSETS/'document-layout-editor.html').as_uri());page.wait_for_function('()=>window.studioReady')
        for index in range(count):
            source=fixture(index,rng)
            data=page.evaluate('''async source=>{
             const original=[source],candidates=LayoutAssist.candidates(original),out=[];let baseline=1;
             for(const candidate of candidates){await Studio.loadState({title:source.title,sourceCSS:'',sections:candidate.sections});const report=await Studio.preview();if(candidate.id==='source')baseline=report.pages.length;
              const x=LayoutAssist.features(report,candidate.sections,original,baseline);out.push({candidate:candidate.id,features:x,report:{pass:report.pass,textPreserved:report.textPreserved,pages:report.pages.length,errors:report.errors},design:candidate.sections[0].design});}
             return out;
            }''',source)
            records.append({'document':'synthetic-'+str(index+1).zfill(3),'fixture':source,'candidates':data})
            print(json.dumps({'collected':index+1,'documents':count,'candidates':len(data)}),flush=True)
        br.close()
    dataset={'version':'1.0.1','seed':seed,'features':FEATURES,'provenance':'Original synthetic fixtures rendered using the shared DOM pagination engine. No private documents. Labels are engineering preferences, not human aesthetic judgement.','documents':records}
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(dataset,ensure_ascii=False,indent=2));return dataset


def utility(x):
    # Explicit teacher: prioritize valid content, readable typography and moderate density.
    # The model learns a nonlinear approximation; this is not a human-labelled corpus.
    return (-30*x[0]-12*x[1]-8*x[2]-20*x[3]-3*x[4]
            -2.5*(x[5]-.78)**2-1.1*x[6]-.6*(max(0,.35-x[7]))
            -.65*x[8]-2.8*x[9]-1.8*x[10]-.8*x[11]-2*x[12]
            -1.5*x[13]-.55*max(0,x[14])-.5*x[18]-.7*x[19]-.8*x[20]-.25*x[21]-.3*x[22]-2*x[23])


def train(dataset,epochs=1800):
    import numpy as np
    seed=dataset['seed'];rng=np.random.default_rng(seed)
    docs=dataset['documents'];order=list(range(len(docs)));random.Random(seed).shuffle(order)
    holdout=set(order[:max(4,len(docs)//4)])
    def samples(indices):
        return [(i,c) for i in indices for c in docs[i]['candidates']]
    training=samples(i for i in range(len(docs)) if i not in holdout)
    matrix=np.array([c['features'] for _,c in training],dtype=float)
    mean=matrix.mean(axis=0);scale=np.maximum(matrix.std(axis=0),.05)
    # Differences generated only within the same document; document-level holdout prevents leakage.
    pairs=[]
    for i,d in enumerate(docs):
        if i in holdout:continue
        for a,b in itertools.combinations(d['candidates'],2):
            diff=utility(a['features'])-utility(b['features'])
            if abs(diff)>.005:
                pairs.append((a['features'],b['features'],1.0 if diff>0 else 0.0,min(2,abs(diff)*3+.2)))
    xa=(np.array([p[0] for p in pairs])-mean)/scale;xb=(np.array([p[1] for p in pairs])-mean)/scale
    target=np.array([p[2] for p in pairs]);pw=np.array([p[3] for p in pairs])
    hidden=12;W=rng.normal(0,.16,(len(FEATURES),hidden));bias=np.zeros(hidden);v=rng.normal(0,.15,hidden)
    params=[W,bias,v];m=[np.zeros_like(p) for p in params];vv=[np.zeros_like(p) for p in params]
    for step in range(1,epochs+1):
        ha=np.tanh(xa@W+bias);hb=np.tanh(xb@W+bias);delta=(ha-hb)@v
        prob=1/(1+np.exp(-np.clip(delta,-40,40)));g=(prob-target)*pw/len(pairs)
        ga=g[:,None]*v*(1-ha*ha);gb=-g[:,None]*v*(1-hb*hb)
        grads=[xa.T@ga+xb.T@gb+.0002*W,(ga+gb).sum(axis=0),((ha-hb)*g[:,None]).sum(axis=0)+.0002*v]
        for j,(p,gradient) in enumerate(zip(params,grads)):
            m[j]=.9*m[j]+.1*gradient;vv[j]=.999*vv[j]+.001*gradient*gradient
            p-=.012*(m[j]/(1-.9**step))/(np.sqrt(vv[j]/(1-.999**step))+1e-8)
    def score(c):return float(np.tanh(((np.array(c['features'])-mean)/scale)@W+bias)@v)
    evaluation=[];correct=total=0
    for i in sorted(holdout):
        candidates=docs[i]['candidates'];best=max(candidates,key=lambda c:utility(c['features']));chosen=max(candidates,key=score)
        local_correct=local_total=0
        for a,b in itertools.combinations(candidates,2):
            diff=utility(a['features'])-utility(b['features'])
            if abs(diff)>.005:local_total+=1;local_correct+=int((score(a)-score(b))*diff>0)
        correct+=local_correct;total+=local_total
        evaluation.append({'document':docs[i]['document'],'selected':chosen['candidate'],'teacher_best':best['candidate'],'regret':round(utility(best['features'])-utility(chosen['features']),6),'pairwise_correct':local_correct,'pairwise_total':local_total})
    def rounded(a):return np.round(a,9).tolist()
    model={'id':'dom-ranker-1.0.1','version':'1.0.1','architecture':[len(FEATURES),hidden,1],'activation':'tanh','features':FEATURES,'mean':rounded(mean),'scale':rounded(scale),'feature_min':rounded(matrix.min(axis=0)),'feature_max':rounded(matrix.max(axis=0)),'weights':rounded(W),'bias':rounded(bias),'output':rounded(v),'seed':seed,'training_documents':len(docs)-len(holdout),'holdout_documents':len(holdout),'training_pairs':len(pairs),'epochs':epochs,'label_source':'Disclosed engineering utility of real DOM measurements; synthetic training only. Not a semantic or calibrated aesthetic model.'}
    report={'model':model['id'],'document_split':True,'training_documents':len(docs)-len(holdout),'holdout_documents':len(holdout),'training_pairs':len(pairs),'holdout_pairwise_accuracy':correct/max(1,total),'holdout_mean_regret':sum(e['regret'] for e in evaluation)/len(evaluation),'holdout':evaluation,'limits':model['label_source']}
    return model,report


def export(model,dataset_path,report):
    model['dataset_sha256']=hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    folder=ASSETS/'models';folder.mkdir(exist_ok=True)
    (folder/'dom-ranker.json').write_text(json.dumps(model,ensure_ascii=False,indent=2))
    (folder/'evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    js='/* Original offline MLP weights and inference. MIT, Yufeng Zhan. */\nconst LayoutModel=(()=>{const model='+json.dumps(model,separators=(',',':'))+';\n'
    js+='''function predict(features){
 if(!Array.isArray(features)||features.length!==model.features.length||features.some(x=>!Number.isFinite(x)))return {model:model.id,score:null,reason:'invalid-features',confidence:null};
 const outside=features.flatMap((v,i)=>{let pad=Math.max(.1,(model.feature_max[i]-model.feature_min[i])*.35);return v<model.feature_min[i]-pad||v>model.feature_max[i]+pad?[model.features[i]]:[];});
 if(outside.length)return {model:model.id,score:null,reason:'outside-training-envelope',outside,confidence:null};
 const x=features.map((v,i)=>(v-model.mean[i])/model.scale[i]);
 const hidden=model.bias.map((b,j)=>Math.tanh(b+x.reduce((s,v,i)=>s+v*model.weights[i][j],0)));
 const score=hidden.reduce((s,v,j)=>s+v*model.output[j],0);return {model:model.id,score,confidence:null};
}return {predict,info:{id:model.id,architecture:model.architecture,training_documents:model.training_documents,holdout_documents:model.holdout_documents,label_source:model.label_source,dataset_sha256:model.dataset_sha256}};})();
'''
    (ASSETS/'layout-model.js').write_text(js)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--dataset',type=Path,required=True);ap.add_argument('--documents',type=int,default=40);ap.add_argument('--seed',type=int,default=173);ap.add_argument('--epochs',type=int,default=1800);ap.add_argument('--collect',action='store_true');ap.add_argument('--browser',default=os.environ.get('TRANSLATION_BROWSER'));a=ap.parse_args()
    dataset=collect(a.dataset,a.documents,a.browser,a.seed) if a.collect else json.loads(a.dataset.read_text())
    model,report=train(dataset,a.epochs);export(model,a.dataset,report);print(json.dumps(report,ensure_ascii=False,indent=2))
