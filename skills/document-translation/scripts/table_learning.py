"""Portable learned native-cell links; no OCR, generated text or ML runtime.
Copyright 2026 Yufeng Zhan. MIT.
"""
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import math
import re

FEATURES=['baseline_step','vertical_gap','left_delta','right_delta','center_delta',
          'horizontal_overlap','size_log_ratio','same_font','same_native_block',
          'first_short','second_short','first_numeric','second_numeric',
          'second_parenthesized','first_bold','second_bold','intervening_rule',
          'first_width','second_width','same_column']
MODEL_PATH=Path(__file__).resolve().parent.parent/'assets/models/table-cell-links.json'


def features(a,b,page,same_column=True):
    if __package__:
        from .source_structure import text_baseline,font_key
    else:
        from source_structure import text_baseline,font_key
    size=max(1,(a['size']+b['size'])/2);aa=a['bbox'];bb=b['bbox']
    top,bottom=sorted([text_baseline(a),text_baseline(b)])
    rule=any(top<y<bottom and min(right,aa[2],bb[2])-max(left,aa[0],bb[0])>
             min(aa[2]-aa[0],bb[2]-bb[0])*.5 for left,y,right in page.get('fraction_rules',[]))
    numeric=lambda r:bool(re.fullmatch(r'[\d\s.,+−–-]+',r['text'].strip()))
    return [(text_baseline(b)-text_baseline(a))/size,(bb[1]-aa[3])/size,
        abs(aa[0]-bb[0])/size,abs(aa[2]-bb[2])/size,
        abs(sum(aa[::2])-sum(bb[::2]))/2/size,
        max(0,min(aa[2],bb[2])-max(aa[0],bb[0]))/max(1,min(aa[2]-aa[0],bb[2]-bb[0])),
        abs(math.log(max(.1,a['size'])/max(.1,b['size']))),
        float(font_key(a['font'])==font_key(b['font'])),float(a['native_block']==b['native_block']),
        float(len(a['text'])<8),float(len(b['text'])<8),float(numeric(a)),float(numeric(b)),
        float(bool(re.match(r'^\s*\(',b['text']))),float(bool(a.get('flags',0)&16)),
        float(bool(b.get('flags',0)&16)),float(rule),(aa[2]-aa[0])/size,(bb[2]-bb[0])/size,float(same_column)]


@lru_cache(maxsize=4)
def load_model(path=None):
    path=Path(path) if path else MODEL_PATH
    if not path.is_file():return None
    model=json.loads(path.read_text(encoding='utf-8'))
    if model.get('features')!=FEATURES or model.get('classes')!=['different-cell','same-cell']:
        raise ValueError('Table link model feature contract mismatch.')
    if __package__:
        from .source_structure import validate_head
    else:
        from source_structure import validate_head
    validate_head(model['network'],len(FEATURES),2)
    return model


def predict(pairs,page):
    """Return actual numerical predictions and immutable parameter evidence."""
    model=load_model()
    if not model or not pairs:return [],None
    if __package__:
        from . import source_structure as structure
    else:
        import source_structure as structure
    rows=[features(a,b,page) for a,b in pairs]
    probabilities=structure.predict_many(model['network'],rows)
    decisions=[{'from':a['id'],'to':b['id'],'same_cell_score':round(p[1],8),
                'accepted':p[1]>=model['threshold']} for (a,b),p in zip(pairs,probabilities)]
    return decisions,{'model_id':model['id'],'model_sha256':hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(),
        'features_sha256':structure.digest(rows),'predictions_sha256':structure.digest(probabilities),
        'pairs':len(pairs),'calibrated_probability':False,'semantic_certification':False}
