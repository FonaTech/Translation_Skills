"""Resumable host-agent orchestration, without a hidden model service. MIT."""
import argparse,json
from pathlib import Path
from translate import project,write,units,source_snap,snap

def valid_review(r,m,c,kind,record):
    from refinement import check_manifest
    from translate import safe,sha
    try:
        if record.get('kind')!=kind or record.get('snapshot')!=snap(m,c) or record.get('scope')!='all' or not record.get('evidence'):return False
        check_manifest(r,m,c,kind,record['evidence'])
        if kind=='visual':
            if not record.get('artifacts'):return False
            if any(not safe(r,f).is_file() or sha(safe(r,f))!=h for f,h in record['artifacts'].items()):return False
        return True
    except (ValueError,KeyError,FileNotFoundError):return False

def checklist_current(r,m,c,kind,data):
    from translate import safe,sha
    if data.get('snapshot')!=snap(m,c):return False
    if kind=='visual':
        try:return bool(data.get('pages')) and all(sha(safe(r,x['preview']))==x['sha256'] for x in data['pages'])
        except (ValueError,KeyError,FileNotFoundError):return False
    return True

def run(a):
    r,m,c=project(a.project);state={'schema_version':'1.0.2','source_hash':source_snap(m,c),'snapshot':snap(m,c),'translation_provider':'current invoking agent loop','external_model_required':False,'complete':False}
    if not c['sources']:state.update(stage='ingest',next_action='Ingest the selected original documents.')
    elif any(x.get('status')=='open' for x in c.get('issues',[])):
        from source_review import prepare
        state.update(stage='source-review',task=str(prepare(r).relative_to(r)),next_action='Current host agent opens all selected source images and OCR/crop evidence, returns checked source-review operations, then resumes workflow. Never use document-specific repair scripts.')
    else:
        missing={l:sum(not all(isinstance(u.get('translations',{}).get(l,{}).get(e),str) and (not u['source'].strip() or u['translations'][l][e].strip()) for e in m['editions']) for _,u in units(c)) for l in m['target_languages']}
        if any(missing.values()):
            from translate import tasks
            for l,count in missing.items():
                if count:tasks(argparse.Namespace(project=str(r),language=l,size=12,all=False,max_chars=6000,context_chars=1000))
            state.update(stage='translate',pending_units=missing,next_action='Current host agent translates every pending packet into both editions, checks source clauses and applies by expected_ids. No Ollama/API prerequisite.')
        else:
            from translate import read
            from publishing import artifacts_current
            build=r/'reports/build.json';layout=r/'reports/layout.json'
            if a.advance and not artifacts_current(r,m,c,'build'):
                from publishing import build as build_outputs
                build_outputs(r,a.browser);r,m,c=project(r)
            if not artifacts_current(r,m,c,'build'):state.update(stage='build',next_action='Run workflow --advance to build source-adapted HTML and editor.')
            else:
                if a.advance and not artifacts_current(r,m,c,'render'):
                    from publishing import render
                    try:render(r,a.browser,True)
                    except ValueError:
                        # A recorded failed layout is a repair task, not a dead
                        # exception. Unexpected failures retain their traceback.
                        if not layout.exists() or read(layout).get('snapshot')!=snap(m,c) or read(layout).get('pass'):raise
                    r,m,c=project(r)
                if layout.exists() and read(layout).get('snapshot')==snap(m,c) and not read(layout).get('pass'):state.update(stage='visual-repair',next_action='Current host agent inspects recorded candidate images, applies a generic presentation refinement, then resumes workflow. Preserve failed attempts. Use the closest ranked preset only after severe source-layout rejection.')
                elif not artifacts_current(r,m,c,'render'):state.update(stage='render',next_action='Run workflow --advance to render and rank source-preserving adjustments.')
                elif not read(layout).get('pass'):state.update(stage='visual-repair',next_action='Inspect failed page images; apply evidence-backed refine patch, rebuild and rerender. Template fallback requires severe unadjustable failure.')
                else:
                    reviews=read(r/'reports/reviews.json') if (r/'reports/reviews.json').exists() else []
                    pending=[kind for kind in ('extraction','semantic','visual') if not any(valid_review(r,m,c,kind,x) for x in reviews)]
                    if pending:
                        from review_evidence import create
                        for kind in pending:
                            out=r/'tasks'/('review-'+kind+'.json')
                            if not out.exists() or not checklist_current(r,m,c,kind,read(out)):
                                if out.exists():
                                    from translate import sha
                                    old=r/'reports/review-history'/(out.stem+'-'+sha(out)[:16]+'.json');write(old,read(out))
                                create(r,kind,out)
                        state.update(stage='agent-review',pending=pending,next_action='Current host agent inspects every enumerated source block, both translations and actual rendered page. Fill observations and record review --evidence. Never auto-attest.')
                    else:
                        from translate import release
                        result=release(argparse.Namespace(project=str(r),zip=None))
                        state.update(stage='released' if result==0 else 'release-repair',complete=result==0,next_action='Deliver outputs and editor.' if result==0 else 'Read reports/release.json and repair exact failing gates; rerun workflow.')
    state['snapshot']=snap(m,c);write(r/'reports/workflow.json',state);print(json.dumps(state,ensure_ascii=False,indent=2));return 0
