/* Shared original DOM pagination; source layout is adjusted before fallback. */
let paginationQueue=Promise.resolve();
function paginate(){paginationQueue=paginationQueue.catch(()=>{}).then(runPagination);return paginationQueue;}
async function runPagination(){
 window.translationReady=false;window.translationError=null;
 document.querySelectorAll('#edPages').forEach(e=>e.remove());
 const root=document.querySelector('.reader');
 const adjustment=Number(window.layoutAdjustmentRound||0);
 const sections=JSON.parse(JSON.stringify(window.layoutChosenSections||window.layoutSections));
 for(const s of sections){if(adjustment>=1){s.design.para=Math.min(s.design.para,1.5);s.design.head=Math.min(s.design.head,2.5);}if(adjustment>=2){s.design.para=Math.min(s.design.para,1.2);s.design.head=Math.min(s.design.head,2);s.design.leading=Math.max(1.4,s.design.leading-.04);s.design.size=Math.max(9.5,s.design.size*.97);}}
 let style=document.getElementById('measured-layout-style');if(!style){style=document.createElement('style');style.id='measured-layout-style';document.head.append(style);}style.textContent=Layout.styles(sections)+'\n.ed-page .paragraph{font-size:inherit;line-height:inherit}.ed-page .mast,.ed-page .scope-list{width:100%}.ed-page-header span{max-width:100%;overflow:hidden}.ed-page .block-metadata{font-size:.78em;line-height:1.45;color:#52616b}.ed-page .block-abstract{font-weight:500;border-inline-start:2px solid var(--accent);padding-inline-start:2mm}.ed-page .block-keywords{font-size:.82em;line-height:1.5}.ed-page .block-caption{font-size:.8em;line-height:1.5}.ed-page table{font-size:var(--table-size,8pt);line-height:1.35}.ed-page td,.ed-page th{padding:var(--cell-pad,1mm) .8mm}.ed-page .pair-label{font-size:7.5pt;margin:1mm 0 .5mm}.ed-page .pair-start{font-size:6.5pt;margin-top:1.5mm;padding-top:1mm}.ed-page h2{font-size:var(--title-size,20pt);line-height:1.3;margin:2mm 0 3mm}.ed-page h3{font-size:1.18em;line-height:1.35;margin:3mm 0 1.5mm}.ed-page figure .locator{font-size:6pt}.ed-page figure figcaption{font-size:var(--caption-size,8pt);line-height:1.45}';
 root.querySelectorAll(':scope > .layout-document').forEach((el,i)=>{const s=sections[i];if(s)el.setAttribute('data-studio-layout',JSON.stringify({design:s.design,header:s.header,footer:s.footer,overrides:s.overrides||{},locks:s.locks||{}}));});
 const result=await Layout.paginate(document,sections,root);result.stage.className='print-stage';result.stage.setAttribute('aria-hidden','false');document.body.classList.add('layout-ready');
 const expected=new Map(),actual=new Map();for(const x of root.querySelectorAll('[data-uid]'))expected.set(x.dataset.uid,(expected.get(x.dataset.uid)||'')+x.textContent);for(const x of result.stage.querySelectorAll('[data-uid]'))if(!x.closest('[data-repeat]'))actual.set(x.dataset.uid,(actual.get(x.dataset.uid)||'')+x.textContent);
 const missing=[...expected.keys()].filter(k=>!actual.has(k)),altered=[...expected].filter(([k,v])=>actual.get(k)!==v).map(([k])=>k);
 window.translationLayout={...result.report,missingUnits:missing,alteredUnits:altered,pass:result.report.pass&&!missing.length&&!altered.length};window.translationReady=true;return window.translationLayout;
}
window.optimizeTranslationLayout=async function(){
 const original=JSON.parse(JSON.stringify(window.layoutSections)),planned=LayoutAssist.candidates(original),candidates=[];let baselinePages=1;
 for(let i=0;i<planned.length;i++){
  const candidate=planned[i];window.layoutChosenSections=candidate.sections;window.layoutAdjustmentRound=0;const report=await paginate();
  if(i===0)baselinePages=report.pages.length;candidates.push(LayoutAssist.evaluate(candidate,report,original,baselinePages));
 }
 const ranked=LayoutAssist.rank(candidates),best=ranked.find(c=>c.safe);window.layoutChosenSections=best?best.sections:original;
 const result=await paginate();window.layoutOptimization={model:typeof LayoutModel==='undefined'?null:LayoutModel.info,chosen:best?.id||null,ranking_mode:best?.model||null,candidates:ranked.map(c=>({id:c.id,score:c.score,safe:c.safe,pages:c.report.pages.length,features:c.features,model:c.model,model_fallback:c.model_fallback,learned_score:c.learned_score??null})),visual_review_required:true};return {layout:result,optimization:window.layoutOptimization};
};
window.addEventListener('load',()=>paginate().catch(e=>{window.translationError=String(e);window.translationLayout={pass:false,error:String(e)};console.error(e);}));
