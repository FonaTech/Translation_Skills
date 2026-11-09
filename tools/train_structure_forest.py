#!/usr/bin/env python3
"""Compare a portable tree role head with the geometry-trained join head.

scikit-learn is an optional training dependency only. This exports numerical
parameters, never library source or private document text. Copyright 2026
Yufeng Zhan. MIT. Source labels/splits retain their original provenance.
"""
from pathlib import Path
import argparse
import json
import sys
import copy
import hashlib

import train_source_structure as trainer
s=trainer.s


def record_head_provenance(model,train,validation,annotations,base_model,documents,seed):
    """Preserve fitting identities of both exported heads without libraries."""
    role_sources={d['source_sha256'] for d in train if d.get('source_sha256')}
    validation_sources={d['source_sha256'] for d in validation if d.get('source_sha256')}
    training=model.setdefault('training',{})
    training['real_train_source_sha256']=sorted(set(training.get('real_train_source_sha256',[]))|role_sources)
    training['real_validation_source_sha256']=sorted(set(training.get('real_validation_source_sha256',[]))|validation_sources)
    training['real_train_source_family_sha256']=sorted(set(training.get('real_train_source_family_sha256',[]))|{identity for d in train for identity in trainer.source_identities(d)})
    training['real_validation_source_family_sha256']=sorted(set(training.get('real_validation_source_family_sha256',[]))|{identity for d in validation for identity in trainer.source_identities(d)})
    training['role_head_provenance']={
        'real_train_source_sha256':sorted(role_sources),'real_validation_source_sha256':sorted(validation_sources),
        'annotation_sha256':hashlib.sha256(annotations.read_bytes()).hexdigest(),
        'base_model_sha256':hashlib.sha256(base_model.read_bytes()).hexdigest(),
        'pipeline_sha256':hashlib.sha256(Path(s.__file__).read_bytes()).hexdigest(),
        'synthetic_documents':documents,'seed':seed}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--annotations',type=Path,required=True)
    ap.add_argument('--base-model',type=Path,required=True)
    ap.add_argument('--documents',type=int,default=240)
    ap.add_argument('--seed',type=int,default=173)
    ap.add_argument('--trees',type=int,default=64)
    ap.add_argument('--depth',type=int,default=18)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--evidence',type=Path,required=True)
    a=ap.parse_args()
    import numpy as np
    import sklearn
    from sklearn.ensemble import ExtraTreesClassifier
    documents=trainer.synthetic(a.documents,a.seed)+json.loads(a.annotations.read_text(encoding='utf-8'))['documents']
    split_audit=trainer.validate_document_splits(documents)
    train=[d for d in documents if d['split']=='train'];validation=[d for d in documents if d['split']=='validation']
    samples,_=trainer.examples(train);held,_=trainer.examples([d for d in documents if d['split']=='holdout']);val,_=trainer.examples(validation)
    x=np.asarray([r[0] for r in samples],dtype=np.float32);y=np.asarray([r[1] for r in samples])
    weight=np.asarray([1 if r[2].startswith('owned-synthetic') else 10 for r in samples])
    classifier=ExtraTreesClassifier(n_estimators=a.trees,max_depth=a.depth,min_samples_leaf=1,
        max_features=.8,class_weight='balanced',random_state=a.seed,n_jobs=1)
    classifier.fit(x,y,sample_weight=weight)
    trees=[]
    for estimator in classifier.estimators_:
        tree=estimator.tree_;value=tree.value[:,0,:];value=value/np.maximum(value.sum(1,keepdims=True),1e-15)
        trees.append({'left':tree.children_left.tolist(),'right':tree.children_right.tolist(),
            'feature':tree.feature.tolist(),'threshold':tree.threshold.tolist(),'value':np.round(value,12).tolist()})
    head={'kind':'extra-trees','architecture':[len(s.ROLE_FEATURES),a.trees,len(s.ROLES)],
          'feature_count':len(s.ROLE_FEATURES),'classes':len(s.ROLES),'trees':trees,
          'training':{'library':'scikit-learn '+sklearn.__version__,'library_vendored':False,
            'objective':'class-balanced weighted classification; geometry/font/context features',
            'constraint_loss':'No differentiable role loss in this comparator. Base join head retains its documented geometric loss.'}}
    model=copy.deepcopy(s.load_model(str(a.base_model)));model['role_head']=head
    model['training']['role_head']='extra-trees comparator; not an accuracy certification'
    # The exported model retains a previously fitted join head. Its fitting
    # identities must be unioned with the new role-head identities, otherwise a
    # caller could accidentally report a role-trained source as a blind test.
    record_head_provenance(model,train,validation,a.annotations,a.base_model,a.documents,a.seed)
    # Verify exported numerical traversal before trusting an end-to-end result.
    checks=x[::max(1,len(x)//60)]
    np.testing.assert_allclose(s.predict_many(head,checks.tolist()),classifier.predict_proba(checks),atol=2e-10,rtol=0)
    report={'version':'1.0.2','split_audit':split_audit,'parity_checked':len(checks),
        'training_examples':len(samples),'validation_role':trainer.evaluate(head,val,.8),
        'heldout_role':trainer.evaluate(head,held,.8),'not_semantic_accuracy':True}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(model,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    a.evidence.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'validation_role':report['validation_role']['accuracy'],'synthetic_role':report['heldout_role']['accuracy'],
        'accepted_validation':report['validation_role']['accepted_accuracy'],'nodes':sum(len(t['left']) for t in trees)}))


if __name__=='__main__':main()
