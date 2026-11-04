"""Checked sentence/phrase groups: complete source coverage without duplicated translations."""
import re

def compact(text):
 return re.sub(r'\s+','',text)

def validate_groups(unit,item,splitter):
 groups=item.get('alignment_groups')
 if groups is None:return None
 sentences=splitter(unit['source']);seen=[];out=[]
 if not groups:raise ValueError('Sentence alignment must not be empty.')
 for i,g in enumerate(groups,1):
  indices=g.get('sentences',[])
  if not indices or any(type(n) is not int or n<1 or n>len(sentences) for n in indices):raise ValueError('Invalid source sentence indices.')
  seen+=indices
  if any(not isinstance(g.get(ed),str) or not g[ed].strip() for ed in ['faithful','interpretive']):raise ValueError('Missing aligned target text.')
  out.append({'id':unit['id']+f'-G{i:04d}','source_sentence_ids':[unit['id']+f'-S{n:04d}' for n in indices],
              'source':' '.join(sentences[n-1] for n in indices),'faithful':g['faithful'],'interpretive':g['interpretive']})
 if seen!=list(range(1,len(sentences)+1)):raise ValueError('Source sentences must be covered once, in order.')
 for ed in ['faithful','interpretive']:
  if compact(''.join(g[ed] for g in out))!=compact(item[ed]):raise ValueError('Aligned text must cover the complete target exactly once.')
 return out

def rows(unit,language):
 groups=unit.get('alignment',{}).get(language)
 if not groups:return [unit]
 return [{'id':g['id'],'source':g['source'],'source_sentence_ids':g['source_sentence_ids'],
          'translations':{language:{ed:g[ed] for ed in ['faithful','interpretive']}},
          'notes':unit.get('notes',[]),'parent_unit_id':unit['id']} for g in groups]
