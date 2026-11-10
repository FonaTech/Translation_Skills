#!/usr/bin/env python3
"""Export an offline source/structure review file, without inventing review. MIT.

This tool renders source pages, not translated output. Private annotations and
page images belong outside a redistributable skill package.
"""
from pathlib import Path
import argparse
import base64
import hashlib
import html
import json
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import source_structure as structure


def export(annotations,model,output):
    import fitz
    payload=[]
    for document in json.loads(annotations.read_text(encoding='utf-8'))['documents']:
        source=document.get('source_file')
        if not source:continue
        if hashlib.sha256(Path(source).read_bytes()).hexdigest()!=document['source_sha256']:
            raise ValueError('Source changed since annotation: '+document['id'])
        with fitz.open(source) as pdf:
            for page in document['pages']:
                result=structure.reconstruct(page,document['profile'],model_path=str(model))
                decisions={row['line_id']:row for row in result['line_roles']}
                rows=[]
                for row in page['lines']:
                    if not row['text'].strip():continue
                    prediction=decisions[row['id']]
                    rows.append({'id':row['id'],'text':row['text'],'bbox':row['bbox'],
                                 'expected':None if row.get('_role_unresolved') else row.get('_role'),
                                 'role_truth_unresolved':bool(row.get('_role_unresolved')),
                                 'group':row.get('_group'),**prediction})
                pix=pdf[page['page']-1].get_pixmap(matrix=fitz.Matrix(1.25,1.25),alpha=False)
                payload.append({'document':document['id'],'split':document['split'],'page':page['page'],
                                'width':page['width'],'height':page['height'],
                                'image':'data:image/png;base64,'+base64.b64encode(pix.tobytes('png')).decode(),
                                'rows':rows,'blocks':result['blocks'],'coverage':result['coverage']})
    if not payload:raise ValueError('No annotation source paths available for source-raster review.')
    encoded=json.dumps(payload,ensure_ascii=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    template=r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Source structure review</title><style>
*{box-sizing:border-box}body{margin:0;background:#edf1f5;color:#142333;font:15px system-ui,sans-serif}header{padding:16px 24px;background:#172b3c;color:white;position:sticky;top:0;z-index:4}header h1{margin:0 0 8px;font-size:20px}select,button{font:inherit;padding:7px;max-width:65vw}small{display:block;margin-top:8px;line-height:1.5;color:#cee0ee}main{display:grid;grid-template-columns:minmax(350px,1.1fr) minmax(330px,1fr);gap:20px;max-width:1600px;margin:20px auto;padding:0 20px}.source{position:relative;background:white;align-self:start;box-shadow:0 2px 12px #0001}.source img{width:100%;display:block}.box{position:absolute;border:1px solid #007d9d55;background:#007d9d0a;cursor:pointer}.box.bad{border-color:#dc3f35;background:#dc3f3530}.box.active{outline:3px solid #dc8d00;background:#f7c35455;z-index:2}.results{background:white;padding:24px;overflow-wrap:anywhere}.stats{padding:12px;background:#eaf3f7;line-height:1.6}.block{border-left:3px solid #b3c6cf;padding:12px;margin:12px 0;line-height:1.65}.block.active{border-color:#dc8d00;background:#fff7df}.role{font:12px system-ui;color:#526c7c}details{margin-top:16px}pre{white-space:pre-wrap;font-size:12px}footer{max-width:1400px;margin:24px auto;padding:20px;color:#51616d;font-size:12px;overflow-wrap:anywhere}@media(max-width:850px){main{display:block}.results{margin-top:20px}}@media print{header{position:static}main{display:block}.source{break-after:page}.results{padding:0}.box{display:none}}
</style><header><h1>Source structure review / 源文结构核对</h1><select id="pages" aria-label="Source page"></select> <button id="previous">←</button> <button id="next">→</button><small>Click a source row or a reconstructed paragraph to compare. Red boxes mark role disagreements. These are model proposals and agent-authored labels; this file does not declare semantic or visual review complete.</small></header>
<main><div class="source" id="source"></div><section class="results"><div class="stats" id="stats"></div><div id="blocks"></div><details><summary>Role disagreements / 角色分歧</summary><pre id="errors"></pre></details></section></main>
<footer>Model SHA-256: __MODEL__<br>Annotation SHA-256: __ANNOTATION__<br>Native accounting only confirms that source text-layer rows are retained. Raster figures, source encoding, OCR, table cells and equation topology require separate source review. Source-document rights remain with their owners.</footer>
<script type="application/json" id="data">__DATA__</script><script>
const pages=JSON.parse(document.getElementById('data').textContent),select=document.getElementById('pages');let current=0;
pages.forEach((page,i)=>{const option=document.createElement('option');option.value=i;option.textContent=page.document.split('_')[0]+' · page '+page.page+' · '+page.split;select.append(option)});
function focus(ids){document.querySelectorAll('.active').forEach(x=>x.classList.remove('active'));document.querySelectorAll('[data-line]').forEach(x=>{if(ids.includes(x.dataset.line))x.classList.add('active')});document.querySelectorAll('[data-lines]').forEach(x=>{if(JSON.parse(x.dataset.lines).some(id=>ids.includes(id)))x.classList.add('active')})}
function show(index){current=Math.max(0,Math.min(pages.length-1,index));select.value=current;const page=pages[current],source=document.getElementById('source');source.replaceChildren();const img=new Image();img.src=page.image;img.alt='Original source page '+page.page;source.append(img);page.rows.forEach(row=>{const box=document.createElement('div');box.className='box'+(row.expected&&row.expected!==row.assigned_role?' bad':'');box.dataset.line=row.id;const b=row.bbox;box.style.left=(100*b[0]/page.width)+'%';box.style.top=(100*b[1]/page.height)+'%';box.style.width=(100*(b[2]-b[0])/page.width)+'%';box.style.height=(100*(b[3]-b[1])/page.height)+'%';box.title=row.assigned_role+' ← '+(row.role_truth_unresolved?'role unresolved':row.expected||'unlabeled')+'\n'+row.text;box.onclick=()=>focus([row.id]);source.append(box)});const blocks=document.getElementById('blocks');blocks.replaceChildren();page.blocks.forEach(block=>{const node=document.createElement('article');node.className='block';node.dataset.lines=JSON.stringify(block.line_ids);const role=document.createElement('div');role.className='role';role.textContent=block.role+' · '+block.line_ids.length+' source rows'+(block.review_required?' · review required':'');const text=document.createElement('div');text.textContent=block.text;node.append(role,text);node.onclick=()=>focus(block.line_ids);blocks.append(node)});const errors=page.rows.filter(r=>r.expected&&r.expected!==r.assigned_role);const unresolved=page.rows.filter(r=>r.role_truth_unresolved).length;document.getElementById('stats').textContent=page.document+' · page '+page.page+' | Native accounting: '+(page.coverage.pass?'PASS':'FAIL')+' | Labeled role disagreements: '+errors.length+' / '+page.rows.filter(r=>r.expected).length+' | Role unresolved: '+unresolved;document.getElementById('errors').textContent=errors.map(r=>r.id+' '+r.expected+' → '+r.assigned_role+'\n'+r.text).join('\n\n')||'No role disagreement on the labeled rows. This does not certify assembly or content.'}
select.onchange=()=>show(Number(select.value));document.getElementById('previous').onclick=()=>show(current-1);document.getElementById('next').onclick=()=>show(current+1);show(0);
</script></html>'''
    rendered=template.replace('__MODEL__',html.escape(hashlib.sha256(model.read_bytes()).hexdigest())).replace('__ANNOTATION__',html.escape(hashlib.sha256(annotations.read_bytes()).hexdigest())).replace('__DATA__',encoded)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(rendered,encoding='utf-8')
    return {'output':str(output),'pages':len(payload),'role_review_complete':False,'semantic_review_complete':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--annotations',type=Path,required=True);parser.add_argument('--model',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(export(args.annotations,args.model,args.output)))


if __name__=='__main__':
    from cli_encoding import configure_utf8
    configure_utf8()
    main()
