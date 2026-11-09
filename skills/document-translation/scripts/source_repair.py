"""Source-verified joins of extraction fragments, never source completion.

Only the invoking agent decides which visible fragments belong together. The
operation concatenates existing text and records every contributor and image.
Copyright 2026 Yufeng Zhan. MIT.
"""
import copy
from translate import project,read,write,safe,sha,source_snap,now,units


def join(a):
    r,m,original=project(a.project)
    packet=read(a.packet)
    if not isinstance(packet,dict) or set(packet)-{'source_hash','reviewer','reason','evidence','merges'}:
        raise ValueError('Source join accepts provenance and contributor IDs, never replacement text.')
    if packet.get('source_hash')!=source_snap(m,original):
        raise ValueError('Source join packet is stale; inspect current extraction.')
    if any(not isinstance(packet.get(key),str) or not packet[key].strip() for key in ['reviewer','reason']):
        raise ValueError('A source join requires the inspecting reviewer and reason.')
    evidence={}
    paths=packet.get('evidence')
    if not isinstance(paths,list) or not paths or any(not isinstance(x,str) or not x.strip() for x in paths):
        raise ValueError('Supply a list of inspected source-page evidence paths.')
    for relative in paths:
        p=safe(r,relative)
        if not p.is_file():raise ValueError('Missing inspected source image: '+relative)
        evidence[relative]=sha(p)
    if not evidence:raise ValueError('Supply inspected source-page evidence.')
    merges=packet.get('merges',[])
    if not isinstance(merges,list) or not merges:raise ValueError('No explicit joins supplied.')
    content=copy.deepcopy(original)
    ordered=list(units(content));lookup={u['id']:(b,u,i) for i,(b,u) in enumerate(ordered)}
    all_ids=set(lookup);consumed=set();records=[]
    for merge in merges:
        if not isinstance(merge,dict) or set(merge)-{'unit_ids','observation','separators'}:
            raise ValueError('Join entries accept only ordered unit_ids and an observation.')
        ids=merge.get('unit_ids',[])
        if not isinstance(ids,list) or len(ids)<2 or any(not isinstance(uid,str) or not uid for uid in ids) or len(ids)!=len(set(ids)):
            raise ValueError('A join requires at least two distinct source unit IDs.')
        if not isinstance(merge.get('observation'),str) or not merge['observation'].strip():raise ValueError('Describe the source-verified continuation.')
        if any(uid not in lookup or uid in consumed for uid in ids):
            raise ValueError('Unknown or repeated source contributor.')
        contributors=[lookup[uid] for uid in ids]
        separators=merge.get('separators',[' ']*(len(ids)-1))
        if not isinstance(separators,list) or len(separators)!=len(ids)-1 or any(s not in ('',' ') for s in separators):
            raise ValueError('Supply one empty or single-space separator per inspected boundary.')
        if [item[2] for item in contributors]!=sorted(item[2] for item in contributors):
            raise ValueError('Source contributors must remain in reading order.')
        did=contributors[0][0]['source']['document_id']
        family='reference' if contributors[0][0]['type']=='reference' else 'prose'
        for b,u,_ in contributors:
            eligible=(b['type']=='reference' and family=='reference' or
                b['type']=='paragraph' and family=='prose' and b.get('presentation',{}).get('role','body') in {'body','abstract'})
            if b['source']['document_id']!=did or not eligible:
                raise ValueError('Join only one family of prose or reference fragments of one document.')
            if not isinstance(u.get('source'),str) or not u['source'].strip():
                raise ValueError('Join requires nonempty visible source fragments.')
            if u.get('translations') or u.get('alignment') or u.get('notes'):
                raise ValueError('Join before translating/annotating affected units; preserve existing work.')
        selected=set(ids)
        for b,u in ordered[contributors[0][2]:contributors[-1][2]+1]:
            role=b.get('presentation',{}).get('role','body')
            if u['id'] not in selected and (b['type'] in {'heading','reference'} or b['type']=='paragraph' and role in {'body','abstract'}):
                raise ValueError('Join cannot skip intervening narrative content.')
        first_block,first,_=contributors[0]
        suffix=1
        while first['id']+'-J'+str(suffix).zfill(4) in all_ids:suffix+=1
        new_id=first['id']+'-J'+str(suffix).zfill(4);all_ids.add(new_id)
        segments=[]
        for b,u,_ in contributors:
            segments.extend(copy.deepcopy(u.get('source_segments') or [{'unit_id':u['id'],'block_id':b['id'],'locator':b['source'],'text':u['source']}]))
        text=contributors[0][1]['source'].strip()
        for sep,(_,u,_) in zip(separators,contributors[1:]):text+=sep+u['source'].strip()
        merged={'id':new_id,'source':text,'translations':{},'notes':[],'source_segments':segments}
        first_index=first_block['units'].index(first)
        first_block['units'][first_index]=merged
        for b,u,_ in contributors[1:]:b['units'].remove(u)
        consumed.update(ids)
        records.append({'new_unit_id':new_id,'contributing_units':ids,'segments':segments,'separators':separators,'observation':merge['observation'],'text_operation':'concatenate existing fragments with inspected space/empty boundaries; no new words'})
    touched_blocks={lookup[uid][0]['id'] for uid in consumed}
    content['blocks']=[b for b in content['blocks'] if b['id'] not in touched_blocks or b.get('units')]
    content.setdefault('extraction_corrections',[]).append({'operation':'source-verified-fragment-joins','at':now(),'reviewer':packet['reviewer'],'reason':packet['reason'],'before_source_hash':packet['source_hash'],'evidence':evidence,'joins':records})
    # Refresh the hash-bound parser/layout handoff in this operation, so a
    # checked join cannot leave the next automatic build with a stale map.
    from structure_layout import write_map
    affected={lookup[uid][0]['source']['document_id'] for uid in consumed}
    for source in content['sources']:
        if source['id'] in affected and source.get('layout_ir'):
            write_map(r,content,source)
    write(r/'content.json',content)
    print('Joined '+str(len(records))+' source-verified continuations; '+str(len(consumed))+' original IDs retained in provenance. Translate new IDs, rebuild and review.')
