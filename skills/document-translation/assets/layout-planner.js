/* Original layout candidate planning. Copyright 2026 Yufeng Zhan. MIT. */
const LayoutAssist=(()=>{
 const keys=['size','leading','para','head','gap','tableSize','cellPad','titleSize','captionSize'];
 const names=['invalid','overflow','errors','empty','sparse','mean_fill','fill_variation','tail_fill','imbalance','font_delta','leading_delta','spacing_delta','small_type','narrow_measure','page_expansion','figure_fraction','table_fraction','page_count','title_delta','caption_delta','table_type_delta','cell_padding_delta','column_gap_delta','interior_sparse'];
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,Number(x)||0));
 function candidates(original){
  const profiles=[
   ['source','原始版式',{}],
   ['rhythm-compact','收紧段落节奏',{para:-.5,head:-.5}],
   ['rhythm-open','放松段落节奏',{para:.5,head:.6}],
   ['heading-compact','收紧标题间距',{head:-1}],
   ['heading-open','增加标题留白',{head:1}],
   ['leading-compact','紧凑行距',{leading:-.07,para:-.25}],
   ['leading-open','舒展行距',{leading:.07}],
   ['type-compact','小幅缩小正文',{size:-.35,leading:-.03,para:-.3}],
   ['type-open','小幅放大正文',{size:.35,leading:.02}],
   ['type-compact-plus','紧凑正文与段距',{size:-.55,leading:-.04,para:-.45}],
   ['type-open-plus','舒展正文与段距',{size:.55,leading:.03,para:.3}],
   ['table-compact','收紧表格字距与边距',{cellPad:-.35,tableSize:-.3}],
   ['table-open','增加表格留白',{cellPad:.35}],
   ['table-type-open','放大表格文字',{tableSize:.35,cellPad:-.15}],
   ['column-gap-compact','缩小栏间距',{gap:-.8}],
   ['column-gap-open','增大栏间距',{gap:.8}],
   ['title-compact','微调主标题字号',{titleSize:-1}],
   ['title-open','微调主标题字号',{titleSize:1}],
   ['caption-compact','收紧图注字号',{captionSize:-.4}],
   ['caption-open','放大图注字号',{captionSize:.4}],
   ['balanced-compact','正文、行距与留白协调',{size:-.25,leading:-.025,para:-.3,head:-.35,gap:-.3,cellPad:-.15}],
   ['balanced-open','正文与留白协调放松',{size:.2,leading:.025,para:.25,head:.35,gap:.3}],
   ['dense-but-readable','保守提高页面利用率',{size:-.2,leading:-.035,para:-.45,head:-.45,cellPad:-.2}],
   ['airy-readable','增加正文呼吸感',{size:.2,leading:.04,para:.4,head:.5,gap:.35}]
  ],seen=new Set();return profiles.map(([id,label,delta])=>{
   const sections=JSON.parse(JSON.stringify(original));let changed=0;
   for(const s of sections){s.overrides={...(s.overrides||{})};for(const [k,v] of Object.entries(delta)){
    if(s.locks?.[k])continue;let old=s.design[k]??({tableSize:8,cellPad:1,titleSize:20,captionSize:8}[k]);
    const bounds={size:[Math.min(old,9.5),Math.max(old,16)],leading:[Math.min(old,1.35),2.2],para:[0,12],head:[0,14],gap:[2,20],tableSize:[Math.min(old,7),16],cellPad:[0,4],titleSize:[10,42],captionSize:[6,14]}[k]||[0,100];
    let value=clamp(old+v,...bounds);if(Math.abs(old-value)>.00001){s.design[k]=value;s.overrides[k]=true;changed++;}
   }}
   const hash=JSON.stringify(sections.map(s=>s.design));if(seen.has(hash))return null;seen.add(hash);return {id,label,sections,changed};
  }).filter(Boolean);
 }
 function features(report,sections,original,baselinePages){
  const pages=report.pages||[],n=Math.max(1,pages.length),fills=pages.map(p=>clamp(p.vertical_fill,0,1.5)),mean=fills.reduce((a,b)=>a+b,0)/n;
  let deltas={size:0,leading:0,spacing:0,small:0,narrow:0},extras=[0,0,0,0,0];
  sections.forEach((s,i)=>{let d=s.design,o=original[i].design;deltas.size+=Math.abs(d.size-o.size)/Math.max(1,o.size);deltas.leading+=Math.abs(d.leading-o.leading);deltas.spacing+=(Math.abs(d.para-o.para)+Math.abs(d.head-o.head))/10;deltas.small+=Math.max(0,10-d.size)/3;let measure=(d.w-2*d.mx-(d.cols-1)*d.gap)/d.cols;deltas.narrow+=Math.max(0,42-measure)/42;});
  sections.forEach((s,i)=>['titleSize','captionSize','tableSize','cellPad','gap'].forEach((k,j)=>{extras[j]+=Math.abs((s.design[k]??0)-(original[i].design[k]??0))/Math.max(1,original[i].design[k]??1);}));
  const count=Math.max(1,sections.length),imbalance=pages.flatMap(p=>p.column_bands||[]).map(b=>clamp(b.imbalance/500,0,1));
  return [Number(!report.pass),clamp(pages.reduce((a,p)=>a+p.overflow,0)/10,0,5),clamp((report.errors||[]).length/4,0,5),pages.filter(p=>!p.chars&&!p.images).length/n,pages.filter(p=>p.vertical_fill<.2&&!p.images).length/n,mean,Math.sqrt(fills.reduce((a,x)=>a+(x-mean)**2,0)/n),fills.at(-1)||0,imbalance.reduce((a,x)=>a+x,0)/Math.max(1,imbalance.length),deltas.size/count,deltas.leading/count,deltas.spacing/count,deltas.small/count,deltas.narrow/count,clamp(n/Math.max(1,baselinePages)-1,-1,5),pages.filter(p=>p.images>0).length/n,pages.filter(p=>p.tables>0).length/n,Math.log1p(n)/5,...extras.map(x=>x/count),pages.slice(0,-1).filter(p=>p.vertical_fill<.4&&!p.images&&!p.tables).length/Math.max(1,n-1)];
 }
 function isSafe(report){return Boolean(report.pass&&report.textPreserved&&(report.pages||[]).length&&report.pages.every(p=>!p.overflow&&(p.chars>0||p.images>0)));}
 function rank(candidates){
  // Learned logits and engineering utility have different scales. If any viable
  // candidate needs fallback, score the entire comparison with the same rule.
  const fallback=candidates.some(c=>c.safe&&c.model==='deterministic-rule-fallback');
  const comparable=candidates.map(c=>fallback?{...c,learned_score:c.model==='deterministic-rule-fallback'?null:c.score,score:ruleScore(c.features),model:'deterministic-rule-fallback',model_fallback:c.model_fallback||'comparison-contains-outside-envelope-candidate'}:c);
  return comparable.sort((a,b)=>Number(b.safe)-Number(a.safe)||b.score-a.score||a.changed-b.changed);
 }
 function ruleScore(x){return -50*x[0]-24*x[1]-16*x[2]-50*x[3]-3*Math.max(0,.4-x[5])-3*Math.max(0,x[5]-.95)-1.5*x[6]-.7*x[8]-5*x[9]-1.6*x[10]-1.2*x[11]-5*x[12]-2*x[13]-.9*Math.max(0,x[14])-.5*x[18]-.7*x[19]-.8*x[20]-.25*x[21]-.3*x[22]-2*x[23];}
 function evaluate(candidate,report,original,baselinePages){
  const x=features(report,candidate.sections,original,baselinePages),prediction=typeof LayoutModel!=='undefined'?LayoutModel.predict(x):null;
  const learned=Number.isFinite(prediction?.score),score=learned?prediction.score:ruleScore(x);
  return {...candidate,report,features:x,score,safe:isSafe(report),model:learned?prediction.model:'deterministic-rule-fallback',model_fallback:learned?null:prediction?.reason||'model-unavailable'};
 }
 return {keys,names,candidates,features,isSafe,rank,evaluate,ruleScore};
})();
