#!/usr/bin/env python3
"""Train original compact structure heads; inference needs no ML framework.

Original synthetic examples and optional source-inspected annotations are distinct.
Document-level splits prevent line leakage. Never call scores semantic accuracy.
Copyright 2026 Yufeng Zhan. MIT.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import random
import sys
import textwrap

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import source_structure as s
from structure_annotation_contract import reviewed_group_lines,source_identities

TEXT={
 'body':'The recorded signal remains stable under the stated conditions. Each measured value belongs to its corresponding observation, and uncertainty is retained. The next experiment may use a different material with the same procedure.',
 'title':'A structured view of information across complex documents',
 'heading':'Methods and observations',
 'metadata':'Received 12 March 2024 | Accepted 15 June 2024 | Published 20 June 2024',
 'caption':'Figure 2. Original schematic of the measurement system. The colored regions denote separate observations. Labels and units are retained.',
 'reference':'[12] Doe, J. & Roe, A. Ordered document structures. Example Journal 4, 12–18 (2024).',
 'equation':'E = m c² + α × β = 12.5',
 'label':'Voltage (V)',
 'table':'Observation     Value     Uncertainty',
 'list':'• Preserve every source statement and its condition.'}


def make_line(text,x,y,size,font,flags,bid,li,page,role,gid,rng):
    width=min(page['width']-x-20,max(size*1.2,len(text)*size*rng.uniform(.43,.53)))
    spans=[{'text':text,'size':size,'font':font,'flags':flags,'bbox':[x,y,x+width,y+size],'origin':[x,y+size*.8]}]
    if role=='metadata' and rng.random()<.2:
        cut=max(1,len(text)//3);spans=[{**spans[0],'text':text[:cut]}, {**spans[0],'text':text[cut:],'font':rng.choice(['Times-Roman','Arial','AdvOTf23'])}]
    return {'id':f'p{page["page"]:04d}-b{bid:04d}-l{li:04d}','native_block':bid,'native_line':li,'text':text,'bbox':[x,y,x+width,y+size],
            'direction':[1,0],'wmode':0,'spans':spans,'size':size,'font':font,'flags':flags,'_role':role,'_group':gid}


def synthetic(count,seed):
    docs=[]
    for di in range(count):
        rng=random.Random(seed+di*971);base=rng.uniform(8,12);width=rng.choice([500,595,612,720]);height=rng.choice([750,792,842,1000]);pages=[];gid=0
        font=rng.choice(['Times-Roman','Arial','AdvOTea1a7398','NotoSerif','CMR10','LiberationSans']);cols=rng.choice([1,2,3]);margin=rng.uniform(30,65);cw=(width-2*margin-(cols-1)*20)/cols
        for pn in range(1,4):
            page={'page':pn,'width':width,'height':height,'lines':[],'table_regions':[]};bid=0
            for col in range(cols):
                y=40; x=margin+col*(cw+20)
                sequence=['metadata','title','metadata','heading','body','body','caption','label','equation','body','reference','reference','table','list'] if pn==1 and col==0 else ['heading','body','body','caption','body','equation','body','reference','reference','label','table','list']
                for role in sequence:
                    gid+=1
                    if role=='title':size=base*rng.uniform(1.7,2.8);flags=16 if rng.random()<.7 else 0
                    elif role=='heading':size=base*rng.uniform(.9,1.45);flags=16
                    elif role in {'caption','metadata','reference','label','table'}:
                        size=base*rng.uniform(.72,.98);flags=0
                        if role=='metadata' and rng.random()<.3:size=base*rng.uniform(1.2,1.65);flags=2
                    else:size=base*rng.uniform(.96,1.04);flags=0
                    ft=font
                    if role=='heading' and rng.random()<.6:ft=rng.choice(['Arial-Bold','NotoSans-Bold','LiberationSans-Bold'])
                    if role=='equation':ft=rng.choice(['Symbol','CambriaMath','CMR10']);flags=2
                    elif role=='table':ft=rng.choice([font,'Courier']);flags=8 if ft=='Courier' else 0
                    elif rng.random()<.18:flags|=2
                    # Typography alone does not determine semantic role. Abstracts,
                    # notices and emphasized prose can be entirely bold or sans.
                    if role=='body' and rng.random()<.25:
                        flags|=16;ft=rng.choice([font+'-Bold','NotoSans-Bold','Arial-Bold'])
                    if role=='metadata' and rng.random()<.35:flags|=16
                    text=TEXT[role]
                    if role=='heading':text=rng.choice(['2. Results','Conclusions','Observations','A. Procedure','Background','4.1 Measurements','II. EXPERIMENTAL METHODS','IV. RESULTS AND DISCUSSION','3. COMPUTATIONAL FRAMEWORK'])
                    if role=='caption':text=rng.choice([TEXT[role],'Table 3: Comparison of measured values.','1. Fabrication flow for the device. (338 KB)','Flowchart showing the implementation of the process.'])
                    if role=='metadata':text=rng.choice([text,'J. Doe¹, A. Roe² & M. Lin³','Department of Science, Example University, City 12345','DOI: 10.0000/example.2024.12','OPEN','ARTICLE','© 2024 The Authors. All rights reserved.','www.example-journal.org','Example Journal 12, 2024, 1234','full paper','Ping Huang, Wei Lin, Maria Silva and Zheng Chen*','School of Applied Science and Technology, City 10000','E-mail: researcher@example.org','Collaborative Innovation Center of Advanced Materials. Example Academy of Sciences. City 10000, Country.'])
                    if role=='body':
                        text=rng.choice([text,'Figure 2d shows the recorded observations. Received signals may depend on temperature. The samples were prepared at a university laboratory, but this sentence is narrative prose.','The current is 12.5 μA and the formula V = I R applies under the stated condition. The result can be measured independently.','At the same time, the device has received considerable interest. The institute fabricated a prototype. This paragraph reports what happened, with all conditions retained.','JANE DOE is a professor of electrical engineering at Example University. Her research concerns novel devices and experimental computing systems. Contact her at jane@example.org.'])
                        text*=rng.randint(1,3)
                    if role=='list':text=rng.choice(['• Preserve every source statement and its condition. The line continuation belongs to this same item, including a wrapped final phrase.','›› New architectures and system runtimes process abundant data with all stated constraints preserved.','– The evolved controller operates under the specified environment, with its assumptions and limitations retained.'])
                    if role=='table':text=rng.choice([text,'High computation density for a given footprint','Nonvolatile storage','0.007','NA','Memory access','Energy-efficient digital systems'])
                    wrap=max(12,int(cw/(size*.5)));parts=textwrap.wrap(text,wrap) or [text]
                    # Diverse valid continuations include very short final rows.
                    # The final row can be digits, a single word or an author.
                    if role in {'body','reference','metadata'} and len(parts)>1 and rng.random()<.4:
                        words=parts[-1].split()
                        if len(words)>2:
                            cut=rng.randint(1,len(words)-1);parts[-1:] = [' '.join(words[:-cut]),' '.join(words[-cut:])]
                    if role in {'label','equation'}:parts=[text]
                    if role=='body' and di%4==0:
                        parts[-1]=parts[-1].rstrip()+ ' [1-'
                        parts.append('3].')
                    if role=='table':
                        page['table_regions'].append({'bbox':[x-1,y-1,x+cw,y+size*1.5*len(parts)+1],'rows':2,'columns':2})
                    group_x=x+(rng.uniform(0,10) if role in {'body','reference'} else 0)
                    for li,part in enumerate(parts):
                        if y+size>height-35:break
                        # Fragment some paragraphs into one-line native blocks; mix
                        # adjacent metadata/title in one native block on other pages.
                        native_bid=bid+li if role=='body' and di%3==0 else bid
                        native_li=0 if native_bid!=bid else li
                        line_x=group_x+(size if role=='list' and li else 0)
                        line=make_line(part,line_x,y,size,ft,flags,native_bid,native_li,page,role,gid if role!='table' else f'{gid}-cell-{li}',rng)
                        if role in {'body','reference','metadata'} and li and rng.random()<.12:
                            # A right-aligned continuation around a float. Preserve
                            # its measured width and move it within this column.
                            shift=max(0,x+cw-line['bbox'][2]);line['bbox'][0]+=shift;line['bbox'][2]+=shift
                            line['spans'][0]['bbox']=line['bbox'][:];line['spans'][0]['origin'][0]+=shift
                        page['lines'].append(line);y+=size*rng.uniform(1.17,1.5)
                    bid+=len(parts)+1;y+=rng.uniform(4,15)
            # Ground truth can retain side-by-side short labels; no guessed join.
            for n in range(4):
                gid+=1;page['lines'].append(make_line(str(n*2)+' V',margin+n*50,height-24,base*.65,font,0,bid+n,0,page,'label',gid,rng))
            for n,txt in enumerate(['www.example-journal.org','Example Journal 12, 2024, 1234','www.another-publisher.com']):
                gid+=1;page['lines'].append(make_line(txt,margin+(width/2 if n else 0),height-12 if n<2 else 14,base*.7,font,0,bid+10+n,0,page,'metadata',gid,rng))
            gid+=1
            side=make_line('full paper',width-20,70,base*1.3,font,16,bid+20,0,page,'metadata',gid,rng);side['direction']=[0,rng.choice([-1,1])];side['bbox']=[width-20,70,width-8,160];page['lines'].append(side)
            gid+=1
            watermark=make_line('Downloaded from https://example.org by Example University. Terms and conditions apply to this document.',width-10,10,base*.55,font,0,bid+21,0,page,'metadata',gid,rng);watermark['direction']=[0,-1];watermark['bbox']=[width-10,10,width-4,height-10];page['lines'].append(watermark)
            page['raw_sha256']=s.digest(page['lines']);pages.append(page)
        if cols>1:
            # Vary verified seam geometry independently of its source truth.
            # One fixed .76 -> .14 page jump encouraged position memorization.
            for seam in range(4):
                page={'page':5+seam,'width':width,'height':height,'lines':[],'table_regions':[]}
                col=seam%(cols-1);gid+=1
                left_x=margin+col*(cw+20);right_x=margin+(col+1)*(cw+20)
                y_left=height*rng.uniform(.56,.89);y_right=height*rng.uniform(.075,.47)
                prior=rng.choice(['the recorded response remains stable','the measured device operates','the procedure continues'])
                following=rng.choice(['under the stated conditions.','within the reported interval.','with the original assumptions retained.'])
                preceding=make_line('The original procedure records each observation and',left_x,y_left-base*1.3,base,font,0,900,0,page,'body',gid,rng)
                last=make_line(prior,left_x,y_left,base,font,0,900,1,page,'body',gid,rng)
                first=make_line(following,right_x,y_right,base,font,0,910,0,page,'body',gid,rng)
                tail=make_line('The next measurement retains its stated uncertainty.',right_x,y_right+base*1.3,base,font,0,910,1,page,'body',gid,rng)
                if seam%3==2:
                    last['text']+='.';last['spans'][0]['text']=last['text']
                    gid+=1
                    for row in [first,tail]:row['_group']=gid
                    first['text']='A new source paragraph describes a separate observation.';first['spans'][0]['text']=first['text']
                page['lines']=[preceding,last,first,tail]
                page['raw_sha256']=s.digest(page['lines']);pages.append(page)
        # A bibliography often occupies one tall native block per column. The
        # first row may continue a previous-page entry, so first-row cues alone
        # cannot determine the remaining row roles. These are original examples.
        page={'page':4,'width':width,'height':height,'lines':[],'table_regions':[]}
        number=1
        for col in range(cols):
            x=margin+col*(cw+20);y=45;li=0;size=base*rng.uniform(.60,.83)
            gid+=1
            page['lines'].append(make_line('References',x,30,size*1.15,font,16,800+col,0,page,'heading',gid,rng))
            for entry in range(12):
                gid+=1
                content=rng.choice([
                    'A. Vale and B. Park, Measurement uncertainty under controlled operating conditions. Journal of Original Examples, volume 12, pages 34–56, 2023.',
                    'C. Stone, Adaptive algorithms and experimental observations in complex systems. Proceedings of the Example Conference, 2022, pages 100–108.',
                    'D. Reed and E. Lin, Reproducible device studies with explicit limitations. Example Transactions, volume 8, issue 3, pages 210–219, 2024.',
                    'Open Example Specification. Accessed 12 May 2024. Available online: https://example.org/specification/part-three'])
                text=(f'[{number}] ' if not (entry==0 and col==0 and di%2==0) else '')+content
                parts=textwrap.wrap(text,max(20,int((cw-size*2)/(size*.5))))
                if y+len(parts)*size*1.35>height-35:break
                native_bid=col
                for j,part in enumerate(parts):
                    # PDF blocks often split inside one bibliography entry.
                    # Preserve its known group while changing the container.
                    if j and rng.random()<.35:native_bid=1000+col*100+entry*10+j
                    xx=x+(0 if j==0 else size*1.8)
                    page['lines'].append(make_line(part,xx,y,size,font,0,native_bid,li,page,'reference',gid,rng));li+=1;y+=size*1.3
                y+=size*.15;number+=1
        page['raw_sha256']=s.digest(page['lines']);pages.append(page)
        # Original figure-plate fixtures distinguish panel headings and plotted
        # tick/parameter labels from page furniture and display mathematics.
        page={'page':10,'width':width,'height':height,'lines':[],'table_regions':[],
              'heading_regions':[],'graphic_regions':[]}
        for col in range(2):
            x=margin+col*(width-2*margin)/2;pw=(width-2*margin)/2-12
            y=height*rng.uniform(.60,.67);size=base*rng.uniform(.65,.8)
            region=[x,y,x+pw,y+base*2.4];page['heading_regions'].append(region)
            gid+=1
            page['lines'].append(make_line('Response measurements' if col==0 else 'Operating conditions',x+4,y+base*.4,base*1.1,font+'-Bold',16,1200+col,0,page,'heading',gid,rng))
            top=y+base*3;bottom=height*.92
            page['graphic_regions'].append([x,top,x+pw,bottom])
            for n,text in enumerate(['0','20','60','120','V = 3.4','f = 2.1 MHz','(b)','Response (V)']):
                gid+=1;xx=x+(n%2)*pw*.44;yy=top+(bottom-top)*(n//2)/3.2
                page['lines'].append(make_line(text,xx,yy,size,font,0,1250+col*20+n,0,page,'label',gid,rng))
            gid+=1
            page['lines'].append(make_line(f'Fig. {col+1}. Measured response under original conditions.',x,bottom+base*.8,size,font,0,1300+col,0,page,'caption',gid,rng))
        gid+=1
        page['lines'].append(make_line('101',width-margin-20,height-12,base*.7,font,0,1400,0,page,'metadata',gid,rng))
        page['raw_sha256']=s.digest(page['lines']);pages.append(page)
        profile=s.document_profile(pages)
        docs.append({'id':f'owned-synthetic-{di:04d}','family':f'columns-{cols}','pages':pages,'profile':profile,'label_source':'original-generator-ground-truth','split':'holdout' if di%5==0 else 'train'})
    return docs


def examples(documents):
    roles=[];pairs=[]
    for doc in documents:
        profile=doc['profile']
        for page in doc['pages']:
            lines=page['lines']
            for line in lines:
                if (line.get('_role') in s.ROLES and line['text'].strip() and
                        not line.get('_role_unresolved') and not s.native_text_damaged(line['text'])):
                    roles.append((s.role_features(line,page,profile),s.ROLES.index(line['_role']),doc['id']))
            # Ordered candidate pairs and actual adjacent group lines both matter.
            seen=set()
            text_lines=[line for line in lines if line['text'].strip()]
            truth_roles={line['id']:line.get('_role') for line in text_lines}
            candidates=s.candidate_pairs(text_lines,page['width'],page['height'],roles=truth_roles)+list(zip(s.order_regions(text_lines,page['width']),s.order_regions(text_lines,page['width'])[1:]))
            # Establish adjacency before masking uncertain endpoints. Removing an
            # intervening excluded row would invent an unreviewed positive edge.
            groups=reviewed_group_lines(page)
            for group in groups.values():candidates.extend(zip(group,group[1:]))
            adjacent={(a['id'],b['id']) for group in groups.values() for a,b in zip(group,group[1:])}
            transitions={(x['id'],y['id']) for x,y in s.column_transition_pairs(text_lines,page['width'],page['height'],roles=truth_roles)}
            for a,b in candidates:
                key=(a['id'],b['id'])
                if key in seen:continue
                seen.add(key)
                if any(row.get('_role') not in s.ROLES or row.get('_pair_excluded') or
                       row.get('_assembly_unresolved') or row.get('_role_unresolved') or
                       '_group' not in row or s.native_text_damaged(row['text']) for row in (a,b)):continue
                # Same paragraph is not sufficient: skipping an intervening line
                # creates a false target and contradicts the path-cover decoder.
                ra,rb=a['_role'],b['_role'];positive=key in adjacent and ra==rb and ra not in {'equation','label','table'}
                transition=key in transitions
                pairs.append((s.join_features(a,b,page,(ra,rb),transition),int(positive),doc['id']))
    return roles,pairs


def constraint_cost(row,kind):
    """Geometry/font penalties, distinct from source-inspected labels.

    These are document-layout constraints, not PDE physical laws. A contradictory
    source label disables that sample's soft penalty and is counted in evidence.
    """
    if kind=='join':
        f=dict(zip(s.JOIN_FEATURES,row))
        centered=(any(f['role_'+r] for r in ['title','heading','metadata']) or f['role_caption'] and f['same_native_block']) and abs(f['left_delta']+f['right_delta'])/2<2
        right_aligned=any(f['role_'+r] for r in ['body','metadata','caption','reference','list']) and f['same_native_block'] and abs(f['right_delta'])<.5
        semantic_boundary=(not f['same_direction'] or not f['same_role'] or
                           any(f['role_'+r] for r in ['equation','label','table']) or f['next_caption_start'] or
                           (f['role_reference'] and f['next_reference_start']) or f['next_list_start'] or
                           (f['role_heading'] and f['next_heading_start']) or f['next_affiliation_boundary'])
        if f['column_transition']:
            unsafe=semantic_boundary or not any(f['role_'+r] for r in ['body','reference'])
        else:
            unsafe=(f['baseline_step']<.35 or f['vertical_gap']>1.35 or abs(f['size_log_ratio'])>.18 or f['horizontal_overlap']<.6 or
                    (abs(f['left_delta'])>2.8 and not centered and not right_aligned) or semantic_boundary)
        return [0,float(unsafe)]
    f=dict(zip(s.ROLE_FEATURES,row));cost=[0.]*len(s.ROLES)
    cost[s.ROLES.index('title')]=float(f['size_ratio']<math.log(1.3) or f['log_length']>math.log1p(180)/6)
    cost[s.ROLES.index('label')]=float(f['log_length']>math.log1p(85)/6 and abs(f['direction_y'])<.05)
    cost[s.ROLES.index('equation')]=float(f['letter_fraction']>.8 and f['log_length']>math.log1p(65)/6 and not f['symbol_font'] and f['math_fraction']<.1)
    return cost


def train_head(samples,classes,seed,epochs,kind,constraint_weight=.35,consistency_weight=.12,hidden=40):
    import numpy as np
    if not samples or classes<2 or epochs<1:
        raise ValueError('Training requires samples, at least two classes and positive epochs.')
    if not 8<=hidden<=512:
        raise ValueError('Hidden units must be between 8 and 512.')
    expected=len(s.ROLE_FEATURES if kind=='role' else s.JOIN_FEATURES)
    if any(len(v[0])!=expected or not all(math.isfinite(x) for x in v[0]) or not 0<=v[1]<classes for v in samples):
        raise ValueError('Nonfinite features, wrong dimensions or invalid class label.')
    if any(not math.isfinite(w) or w<0 for w in (constraint_weight,consistency_weight)):
        raise ValueError('Loss weights must be finite and nonnegative.')
    rng=np.random.default_rng(seed);original=np.asarray([v[0] for v in samples]);y=np.asarray([v[1] for v in samples]);mean=original.mean(0);scale=np.maximum(original.std(0),.05);x=np.clip((original-mean)/scale,-12,12)
    cost=np.asarray([constraint_cost(v[0],kind) for v in samples]);conflicting=cost[np.arange(len(y)),y]>0;cost[conflicting]=0
    w=rng.normal(0,.15,(x.shape[1],hidden));b=np.zeros(hidden);v=rng.normal(0,.15,(hidden,classes));vb=np.zeros(classes);params=[w,b,v,vb];mom=[np.zeros_like(p) for p in params];var=[np.zeros_like(p) for p in params]
    freq=np.bincount(y,minlength=classes);class_weight=np.sqrt(len(y)/np.maximum(freq,1)/classes);step=0
    importance=np.asarray([1. if sample[2].startswith('owned-synthetic') else 10. for sample in samples]);importance/=importance.mean()
    log=[]
    for epoch in range(epochs):
        order=rng.permutation(len(y));loss=weighted_loss=physical=consistency=0
        for start in range(0,len(y),512):
            idx=order[start:start+512];xx=x[idx];yy=y[idx];n=len(idx)
            h=np.tanh(np.einsum('ni,ij->nj',xx,w,optimize=False)+b);z=np.einsum('ni,ij->nj',h,v,optimize=False)+vb
            e=np.exp(z-z.max(1,keepdims=True));p=e/e.sum(1,keepdims=True)
            ce=-np.log(np.maximum(p[np.arange(n),yy],1e-12));loss+=float(ce.sum())
            weighted_loss+=float((ce*class_weight[yy]*importance[idx]).sum())
            dz=p.copy();dz[np.arange(n),yy]-=1;dz*=class_weight[yy,None]*importance[idx,None]/n
            cc=cost[idx];expect=(p*cc).sum(1,keepdims=True);physical+=float(expect.sum());dz+=constraint_weight*p*(cc-expect)/n
            # The same physical text exported as word spans or whole-line spans
            # should keep its class. Train an explicit second-view consistency loss.
            second=xx.copy()
            if kind=='role':
                k=s.ROLE_FEATURES.index('log_spans');values=rng.uniform(0,.85,n);second[:,k]=np.clip((values-mean[k])/scale[k],-12,12)
            # native_adjacent is evidence about order, not an invariant nuisance.
            # Randomizing it in isolation fabricated contradictory pair views.
            h2=np.tanh(np.einsum('ni,ij->nj',second,w,optimize=False)+b);z2=np.einsum('ni,ij->nj',h2,v,optimize=False)+vb;e2=np.exp(z2-z2.max(1,keepdims=True));p2=e2/e2.sum(1,keepdims=True)
            delta=p-p2;consistency+=float((delta*delta).sum()/2);gp=(consistency_weight if kind=='role' else 0)*delta/n;gq=-gp
            dz+=p*(gp-(gp*p).sum(1,keepdims=True));dz2=p2*(gq-(gq*p2).sum(1,keepdims=True))
            dh=np.einsum('nj,ij->ni',dz,v,optimize=False)*(1-h*h);dh2=np.einsum('nj,ij->ni',dz2,v,optimize=False)*(1-h2*h2)
            grads=[np.einsum('ni,nj->ij',xx,dh,optimize=False)+np.einsum('ni,nj->ij',second,dh2,optimize=False)+.0001*w,(dh+dh2).sum(0),np.einsum('ni,nj->ij',h,dz,optimize=False)+np.einsum('ni,nj->ij',h2,dz2,optimize=False)+.0001*v,(dz+dz2).sum(0)]
            step+=1
            for j,(param,grad) in enumerate(zip(params,grads)):
                rate=.004*(.1+.9*(1-epoch/max(1,epochs-1)))
                mom[j]=.9*mom[j]+.1*grad;var[j]=.999*var[j]+.001*grad*grad;param-=rate*(mom[j]/(1-.9**step))/(np.sqrt(var[j]/(1-.999**step))+1e-8)
                if not np.isfinite(param).all():raise ValueError('Nonfinite learned parameter.')
        if epoch%20==0 or epoch==epochs-1:
            entry={'epoch':epoch+1,'classes':classes,'examples':len(y),'cross_entropy':loss/len(y),'weighted_cross_entropy':weighted_loss/len(y),'geometry_loss':physical/len(y),'consistency_loss':consistency/len(y)};log.append(entry);print(json.dumps(entry),flush=True)
    rounded=lambda a:np.round(a,9).tolist()
    return {'architecture':[x.shape[1],hidden,classes],'activation':'tanh','mean':rounded(mean),'scale':rounded(scale),'weights':rounded(w),'bias':rounded(b),'output':rounded(v),'output_bias':rounded(vb),'feature_min':rounded(original.min(0)),'feature_max':rounded(original.max(0)),
            'loss':{'supervised':'class-balanced source labels, real inspected samples weight 10','geometry_weight':constraint_weight,'consistency_weight':consistency_weight,'label_constraint_conflicts_disabled':int(conflicting.sum()),'curve':log}}


def evaluate(head,samples,threshold):
    probabilities=s.predict_many(head,[x[0] for x in samples]);matrix=[[0]*len(probabilities[0]) for _ in probabilities[0]] if probabilities else [];accepted=correct=total_correct=rule_overrides=0;per_doc={}
    for sample,p in zip(samples,probabilities):
        decision=s.role_decision(sample[0],p,threshold) if len(p)==len(s.ROLES) else None
        pred=s.ROLES.index(decision['assigned_role']) if decision else max(range(len(p)),key=lambda i:p[i]);truth=sample[1];matrix[truth][pred]+=1;total_correct+=pred==truth
        rule_overrides+=bool(decision and decision['rule'])
        # A rule can deliberately assign a provisional role while requesting
        # review (e.g. inline fractions). Such a row is never auto-accepted.
        high=(not decision['review_required']) if decision else (max(p)>=threshold and max(p)-sorted(p)[-2]>=.2)
        if high:accepted+=1;correct+=pred==truth
        d=per_doc.setdefault(sample[2],{'examples':0,'correct':0,'accepted':0,'accepted_correct':0});d['examples']+=1;d['correct']+=pred==truth;d['accepted']+=int(high);d['accepted_correct']+=int(high and pred==truth)
    return {'examples':len(samples),'accuracy':total_correct/max(1,len(samples)),'threshold':threshold,'accepted':accepted,'accepted_accuracy':correct/max(1,accepted),'explicit_rule_overrides':rule_overrides,'confusion':matrix,'by_document':per_doc,'calibrated_probability':False}


def validate_document_splits(documents):
    """Reject aliases, repeated source pages and PDF-level split leakage.

    Explicit source hashes identify partial PDFs too. Raw native-page hashes
    catch renamed records lacking source metadata. Test labels never enter loss.
    """
    ids=set();identities={};families={};pages={}
    for document in documents:
        name=document['id'];split=document['split']
        if name in ids:raise ValueError('Duplicate annotation document ID: '+name)
        ids.add(name)
        if split not in {'train','validation','holdout','test'}:raise ValueError('Unknown document split: '+split)
        identity=document.get('source_sha256')
        if identity:
            if identity in identities:raise ValueError('Repeated source document across annotation records: '+name)
            identities[identity]=(name,split)
        for family in source_identities(document):
            if family in families:raise ValueError('Repeated source family or derived copy across annotation records: '+name)
            families[family]=(name,split)
        for page in document['pages']:
            key=page.get('raw_sha256') or s.digest(page.get('native_lines',page['lines']))
            if key in pages:raise ValueError('Repeated native source page across document records: '+name)
            pages[key]=(name,split)
    return {'documents':len(ids),'source_identities':len(identities),'native_page_hashes':len(pages),
            'test_records_excluded_from_training':sum(d['split']=='test' for d in documents)}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--documents',type=int,default=180);ap.add_argument('--epochs',type=int,default=100);ap.add_argument('--hidden',type=int,default=40,help='Hidden units per role/join head (8-512).');ap.add_argument('--seed',type=int,default=173);ap.add_argument('--annotations',action='append',default=[]);ap.add_argument('--train-document',action='append',default=[],help='Promote a reviewed development document into training before fitting.');ap.add_argument('--test-document',action='append',default=[],help='Move a named whole real document to test before training; labels are used only for final metrics.');ap.add_argument('--constraint-weight',type=float,default=.35);ap.add_argument('--consistency-weight',type=float,default=.12);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--evidence',type=Path,required=True);a=ap.parse_args()
    if not 8<=a.hidden<=512:ap.error('--hidden must be between 8 and 512')
    docs=synthetic(a.documents,a.seed)
    for path in a.annotations:
        data=json.loads(Path(path).read_text(encoding='utf-8'));docs.extend(data['documents'])
    requested=set(a.test_document);requested_train=set(a.train_document)
    available={document['id'] for document in docs if not document['id'].startswith('owned-synthetic-')}
    missing=(requested|requested_train)-available
    if missing:raise ValueError('Unknown real test document(s): '+', '.join(sorted(missing)))
    overlap=requested&requested_train
    if overlap:raise ValueError('A document cannot be both train and test: '+', '.join(sorted(overlap)))
    for document in docs:
        if document['id'] in requested:document['split']='test'
        elif document['id'] in requested_train:document['split']='train'
    split_audit=validate_document_splits(docs)
    train=[x for x in docs if x['split']=='train'];held=[x for x in docs if x['split']=='holdout'];validation=[x for x in docs if x['split']=='validation'];test=[x for x in docs if x['split']=='test'];tr,tp=examples(train);hr,hp=examples(held);vr,vp=examples(validation);er,ep=examples(test)
    role=train_head(tr,len(s.ROLES),a.seed,a.epochs,'role',a.constraint_weight,a.consistency_weight,a.hidden);join=train_head(tp,2,a.seed+1,a.epochs,'join',a.constraint_weight,a.consistency_weight,a.hidden)
    transition_feature=s.JOIN_FEATURES.index('column_transition')
    transition_positives=[x for x in tp if x[1] and x[0][transition_feature]]
    training={'documents':len(train),'heldout_documents':len(held),'role_examples':len(tr),'join_examples':len(tp),'epochs':a.epochs,'hidden_units':a.hidden,'synthetic_documents':a.documents,
              'real_train_source_sha256':sorted({d['source_sha256'] for d in train if d.get('source_sha256')}),
              'real_validation_source_sha256':sorted({d['source_sha256'] for d in validation if d.get('source_sha256')}),
              'real_train_source_family_sha256':sorted({identity for d in train for identity in source_identities(d)}),
              'real_validation_source_family_sha256':sorted({identity for d in validation for identity in source_identities(d)}),
              'pipeline_sha256':hashlib.sha256(Path(s.__file__).read_bytes()).hexdigest(),
              'trainer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'annotation_files_sha256':sorted(hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in a.annotations),
              'source_annotations':sum(not d['id'].startswith('owned-synthetic') for d in train),'validation_documents':len(validation),'test_documents_excluded_from_training':len(test),
              'promoted_development_documents':sorted(requested_train),
              'synthetic_cross_column_positive_examples':sum(x[2].startswith('owned-synthetic') for x in transition_positives),
              'real_cross_column_positive_examples':sum(not x[2].startswith('owned-synthetic') for x in transition_positives),
              'label_contract':'Original synthetic known structure and explicitly source-inspected real annotations. Scores are not calibrated confidence. No source completion; hard geometry gates and coverage checks apply.'}
    model={'id':'source-structure-1.0.3','version':'1.0.3','seed':a.seed,'feature_revision':s.FEATURE_REVISION,'role_features':s.ROLE_FEATURES,'join_features':s.JOIN_FEATURES,'roles':s.ROLES,'role_head':role,'join_head':join,'role_threshold':.8,'join_threshold':.94,'training':training}
    report={'version':'1.0.3','model':model['id'],'training':model['training'],'split_audit':split_audit,'heldout_role':evaluate(role,hr,.8),'heldout_join':evaluate(join,hp,.94),'validation_role':evaluate(role,vr,.8),'validation_join':evaluate(join,vp,.94),'test_role':evaluate(role,er,.8),'test_join':evaluate(join,ep,.94),'splits':[{'id':d['id'],'split':d['split'],'label_source':d.get('label_source','not-recorded')} for d in docs],'real_document_generalization':'Real-document test metrics are reported separately; synthetic metrics do not establish source-document correctness.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(model,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'model':str(a.output),'synthetic_heldout_role_accuracy':report['heldout_role']['accuracy'],
                      'synthetic_heldout_join_accuracy':report['heldout_join']['accuracy'],
                      'real_validation_role_accuracy':report['validation_role']['accuracy'] if vr else None,
                      'real_test_role_accuracy':report['test_role']['accuracy'] if er else None,
                      'real_test_join_pair_accuracy':report['test_join']['accuracy'] if ep else None,'training':model['training']}))

if __name__=='__main__':
    from cli_encoding import configure_utf8
    configure_utf8()
    main()
