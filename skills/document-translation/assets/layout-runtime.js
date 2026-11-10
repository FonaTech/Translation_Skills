/* Original DOM-measured column pagination and bounded layout search. MIT, Yufeng Zhan. */
const Layout = (()=>{
 const mm=96/25.4,esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const baseCSS=`:root{--page-width:210mm;--page-height:297mm;--margin-x:20mm;--margin-y:20mm;--body-size:11pt;--body-leading:1.7;--column-count:1;--column-gap:7mm;--para-gap:3mm;--head-gap:5mm;--accent:#304659;--heading-ratio:1.7}*{box-sizing:border-box}body{margin:0;background:transparent;color:#22313e;font-family:"Songti SC","Times New Roman",serif}.ed-doc{background:white;width:var(--page-width);padding:var(--margin-y) var(--margin-x);margin:0 auto 24px;min-height:var(--page-height);box-shadow:0 2px 12px #1232;font-size:var(--body-size);line-height:var(--body-leading);overflow-wrap:anywhere;outline:0}.ed-doc p,.ed-doc .paragraph{font-size:inherit;line-height:inherit;margin:0 0 var(--para-gap);white-space:pre-wrap}.ed-doc h1{font-size:calc(var(--body-size)*var(--heading-ratio));line-height:1.35}.ed-doc h2{font-size:1.4em}.ed-doc h3{font-size:1.2em}.ed-doc h1,.ed-doc h2,.ed-doc h3{color:var(--accent);margin:var(--head-gap) 0 3mm;break-after:avoid}.ed-doc img{max-width:100%;height:auto;object-fit:contain}.ed-doc figure{margin:2mm 0;break-inside:avoid}.ed-band figure,.ed-band table,.ed-band .table-wrap,.ed-band tr,.ed-band h1,.ed-band h2,.ed-band h3,.ed-band h4{break-inside:avoid}.ed-band h3,.ed-band h4,.ed-band [data-keep-next="true"]{break-after:avoid}.ed-doc caption{text-align:start;caption-side:top;color:#405565}.ed-doc .block-equation{text-align:center;font-family:serif}.ed-doc .block-note{font-size:.8em}.ed-doc figcaption{font-size:.85em;color:#607080;line-height:1.6}.ed-doc table{border-collapse:collapse;table-layout:fixed;width:100%;font-size:.9em;margin:2mm 0 4mm}.ed-doc td,.ed-doc th{padding:2mm;border:1px solid #cdd7de;vertical-align:top;overflow-wrap:anywhere;white-space:pre-wrap}.ed-doc th{background:#eff5f5}.ed-doc blockquote{border-left:3px solid var(--accent);padding-left:4mm;margin-left:0;color:#566b79}.ed-doc pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f7;padding:3mm;font: .9em/1.6 monospace}.ed-doc li{margin-bottom:1.5mm}.ed-doc a{color:var(--accent)}.ed-doc .editor-note{background:#f1f6f7;padding:3mm;border-left:2px solid var(--accent)}.ed-doc .ed-comment{background:#fff3c6;border-bottom:1px dashed #9a6a18}.ed-doc .ed-break{border-top:1px dashed #9baeba;margin:8mm 0;min-height:1px;break-after:page}.ed-doc .ed-break::after{content:var(--page-break-label,'Page break');font:9px sans-serif;color:#8196a3;display:block}.ed-page{width:var(--page-width);height:var(--page-height);padding:var(--margin-y) var(--margin-x);position:relative;background:white;margin:0 auto 24px;box-shadow:0 2px 12px #1232;font-size:var(--body-size);line-height:var(--body-leading);overflow:visible}.ed-page-body{height:calc(var(--page-height) - 2 * var(--margin-y) - 14mm);display:flow-root}.ed-page-header{height:8mm;font:8pt/1.4 sans-serif;color:#768792;border-bottom:1px solid #d1dbe0;display:flex;justify-content:space-between;overflow:hidden}.ed-page-footer{position:absolute;bottom:6mm;left:var(--margin-x);right:var(--margin-x);font:8pt/1.3 sans-serif;border-top:1px solid #d1dbe0;color:#768792;display:flex;justify-content:space-between;padding-top:2mm}.ed-band{display:grid;grid-template-columns:repeat(var(--column-count),minmax(0,1fr));gap:var(--column-gap);align-items:start}.ed-column{display:flow-root;min-width:0}.ed-page.ed-doc{min-height:0}.ed-page .ed-break{display:none}.ed-doc .ed-selected-image{outline:2px solid #2a9a8b;outline-offset:3px}.ed-page .pair .pair-source .paragraph{white-space:normal}.alignment-page-legend{display:grid;grid-template-columns:1.12fr 1fr 1fr;gap:3mm;height:6mm;align-items:center;font:7pt/1.2 sans-serif;color:#405565;border-bottom:.5px solid #cdd7de}.ed-page.alignment-page .ed-page-body{height:calc(var(--page-height) - 2 * var(--margin-y) - 20mm)}.ed-page .pair{margin:0 0 var(--para-gap);padding:1mm 0 0}.ed-page .pair .pair-start{margin:0 0 .5mm;font-size:6pt}.ed-page .pair .pair-grid{gap:3mm}.ed-page .pair .paragraph{font-size:var(--body-size);line-height:var(--body-leading);margin:0}@media print{body{background:white}.ed-doc:not(.ed-page){display:none}.ed-page{box-shadow:none;margin:0;break-after:page}.ed-page:last-child{break-after:auto}}`;
 const fonts={serif:'"Noto Serif","Noto Serif CJK SC","Songti SC","Noto Naskh Arabic","Times New Roman",serif',sans:'"Noto Sans","Arial Unicode MS","Arial",sans-serif',mono:'"Noto Sans Mono","Courier New",monospace'};
 function vars(d,important=false){let value= '--table-size:'+(d.tableSize??8)+'pt;--cell-pad:'+(d.cellPad??1)+'mm;--title-size:'+(d.titleSize??20)+'pt;--caption-size:'+(d.captionSize??8)+'pt;--page-width:'+d.w+'mm;--page-height:'+d.h+'mm;--margin-x:'+d.mx+'mm;--margin-y:'+d.my+'mm;--body-size:'+d.size+'pt;--body-leading:'+d.leading+';--column-count:'+d.cols+';--column-gap:'+d.gap+'mm;--accent:'+d.accent+';--para-gap:'+d.para+'mm;--head-gap:'+d.head+'mm;';if(fonts[d.font])value+='font-family:'+fonts[d.font]+';';return important?value.replace(/;/g,'!important;'):value;}
 // Imported document rules follow defaults; current editable overrides follow both.
 // Reversing this cascade changes captions, headings and pagination on import.
 function styles(sections,sourceCSS=''){return baseCSS+'\n'+FAMILY_CSS+'\n'+sourceCSS+'\n'+(typeof CONTENT_CSS==='undefined'?'':CONTENT_CSS)+'\n'+sections.map((s,i)=>{
  const sel='.ed-doc.ed-section-'+i, o=s.overrides||{};
  let rules=sel+'{'+vars(s.design,true)+'width:var(--page-width)!important;padding:var(--margin-y) var(--margin-x)!important;font-size:var(--body-size);line-height:var(--body-leading)}'+sel+'.ed-page{height:var(--page-height)!important;min-height:0!important;max-width:none!important}';
  if(o.size||o.leading||o.para){let body=sel+' :is(p,.paragraph,.prose):not(.locator,.pair-label,.block-caption,.block-metadata,.block-note,.block-keywords):not(figcaption *,table *,pre *,code *)';rules+=body+'{'+(o.size?'font-size:var(--body-size)!important;':'')+(o.leading?'line-height:var(--body-leading)!important;':'')+(o.para?'margin-bottom:var(--para-gap)!important;':'')+'}';}
  if(o.font&&fonts[s.design.font])rules+=sel+' :is(p,.paragraph,.prose,h1,h2,h3,h4,h5,h6,figcaption,td,th):not(pre *,code *){font-family:'+fonts[s.design.font]+'!important}';
  if(o.head)rules+=sel+' :is(h1,h2,h3,h4,h5,h6){margin-top:var(--head-gap)!important}';
  if(o.cols||o.gap)rules+=sel+' :is(.flowcols,.screen-flow,.columns,.cols){'+(o.cols?'column-count:var(--column-count)!important;':'')+'column-gap:var(--column-gap)!important}';
  if(o.para)rules+=sel+' .pair{margin-bottom:var(--para-gap)!important}'+sel+' .pair .paragraph{margin-bottom:0!important}';
  if(o.tableSize)rules+=sel+' table,'+sel+' td,'+sel+' th{font-size:var(--table-size)!important}';
  if(o.cellPad)rules+=sel+' td,'+sel+' th{padding:var(--cell-pad)!important}';
  if(o.titleSize)rules+=sel+' :is(h1,[data-title="true"],.mast h2){font-size:var(--title-size)!important}';
  if(o.captionSize)rules+=sel+' figcaption,'+sel+' figcaption p{font-size:var(--caption-size)!important}';
  if(o.accent)rules+=sel+' :is(h1,h2,h3,h4,h5,h6){color:var(--accent)!important}';

  rules+=' @page ed'+i+'{size:'+s.design.w+'mm '+s.design.h+'mm;margin:0}'+sel+'.ed-page{page:ed'+i+'}';return rules;
 }).join('\n');}
 function flowText(root){if(root.nodeType===3)return root.data;if(root.nodeType!==1)return '';if(root.matches('img,.inline-math-literal'))return '\uFFFC';return [...root.childNodes].map(flowText).join('');}
 function canonicalText(root){return flowText(root).replace(/\s+/g,'');}
 // Inline union boxes include hanging pre-wrap spaces at justified line edges.
 // They are not painted overflow. The containing block's scroll width and the
 // actual block/replaced-element bounds remain independent hard constraints.
 function boundedElement(e){const display=e.ownerDocument.defaultView.getComputedStyle(e).display;return display!=='inline'||e.matches('img,svg,canvas,video,input,iframe,object');}
 function sliceNode(el,start,end){let offset=0;function crop(n){if(n.nodeType===3){let a=offset,b=a+n.data.length;offset=b;return el.ownerDocument.createTextNode(n.data.slice(Math.max(0,start-a),Math.max(0,Math.min(n.data.length,end-a))));}if(n.nodeType!==1)return null;if(n.matches('img,.inline-math-literal')){const a=offset++;return a>=start&&a<end?n.cloneNode(true):null;}let a=offset,out=n.cloneNode(false);for(let c of n.childNodes){let v=crop(c);if(v&&(v.nodeType!==3||v.data))out.append(v);}if(out.childNodes.length||offset===a&&a>=start&&a<end)return out;return null;}let out=el.cloneNode(false);for(let c of el.childNodes){let v=crop(c);if(v&&(v.nodeType!==3||v.data))out.append(v);}return out;}

 function flatten(root){let out=[];function walk(el){for(const c of [...el.children]){if(c.matches('.print-stage,.toolbar,.running,.page-footer,.ed-page-header,.ed-page-footer,script,style,nav'))continue;if(c.matches('table,.table-wrap,figure,h1,h2,h3,h4,h5,h6,p,pre,blockquote,ul,ol,hr,aside[role="doc-footnote"],.ed-break,.mast,.scope-list,.editor-note,.pair,.alignment-figure'))out.push(c);else if(c.children.length)walk(c);else if(c.textContent.trim())out.push(c);}}walk(root);return out;}
 async function paginate(doc,sections,root){
  await doc.fonts.ready;await Promise.all([...root.querySelectorAll('img')].map(x=>x.decode().catch(()=>{})));
  let report={pages:[],errors:[...root.querySelectorAll('img')].filter(x=>!x.complete||!x.naturalWidth).map(x=>'Image failed to decode: '+(x.alt||x.closest('[data-block]')?.dataset.block||'unnamed image')),warnings:[],originalChars:0,renderedChars:0,pass:false};let allExpected='',allActual='';const stage=doc.createElement('div');stage.id='edPages';stage.style.setProperty('display','block','important');root.after(stage);
  for(let si=0;si<sections.length;si++){
   const s=sections[si],source=root.children[si],d=s.design;let page,body,band,col,ci=0,available=0;let pagesFor=0;
   const full=e=>e.matches('.pair,.editor-note')||e.dataset.span==='all'||(e.dataset.span!=='column'&&e.matches('h1,h2,figure,.table-wrap,table,.mast,.scope-list'));
   // Integer CSS-pixel heights survive serialization at line-fragment boundaries.
   function balanceBand(){if(!band||d.cols<2)return;const columns=[...band.children],nodes=columns.flatMap(c=>[...c.children]);if(!nodes.length)return;const total=columns.reduce((n,c)=>n+c.getBoundingClientRect().height,0),saved=columns.map(c=>c.cloneNode(true)),width=band.getBoundingClientRect().width;band.replaceChildren(...nodes);band.style.display='block';band.style.columnCount=String(d.cols);band.style.columnGap=d.gap+'mm';band.style.columnFill='balance';band.style.height=Math.ceil(Math.min(available,Math.max(1,total/d.cols)))+'px';let fit=false;for(let n=0;n<32;n++){void band.offsetHeight;const fragmented=[...band.querySelectorAll('table,tr,figure,.table-wrap')].some(e=>[...e.getClientRects()].filter(r=>r.width>.1&&r.height>.1).length>1);if(band.scrollWidth<=width+1&&!fragmented){fit=true;break;}let h=parseFloat(band.style.height);if(h>=available)break;band.style.height=Math.ceil(Math.min(available,h+Math.max(8,available*.035)))+'px';}if(!fit){band.replaceChildren(...saved);band.style.display='grid';band.style.columnCount='';band.style.height='';}}
   function newPage(){if(++pagesFor>1000)throw Error('Pagination exceeded 1000 pages; stopped to protect the browser');page=doc.createElement('section');page.className=[...new Set(['ed-doc','ed-page','ed-section-'+si,s.familyClass,...String(s.sourceClass||'').split(/\s+/).filter(c=>/^[\w-]+$/.test(c))])].join(' ');for(const [k,v] of Object.entries(s.sourceAttrs||{}))if(/^data-[a-z0-9_.:-]+$/i.test(k))page.setAttribute(k,v);page.style.cssText=(s.sourceStyle||'')+';'+vars(d,true);page.dir=s.dir||'auto';page.lang=s.lang||source.lang||doc.documentElement.lang||'und';page.innerHTML='<div class="ed-page-header"><span>'+esc(s.header||s.title)+'</span><span class="source-pages"></span></div><div class="ed-page-body"></div><div class="ed-page-footer"><span>'+esc(s.footer||'')+'</span><span class="ed-page-number"></span></div>';if(s.alignmentLabels){page.classList.add('alignment-page');const legend=doc.createElement('div');legend.className='alignment-page-legend';legend.setAttribute('aria-hidden','true');for(const label of s.alignmentLabels){const cell=doc.createElement('span');cell.textContent=label;legend.append(cell);}page.querySelector('.ed-page-header').after(legend);}stage.append(page);body=page.querySelector('.ed-page-body');band=null;col=null;ci=0;}
   function makeBand(){band=doc.createElement('div');band.className='ed-band';body.append(band);available=body.getBoundingClientRect().bottom-band.getBoundingClientRect().top;for(let i=0;i<d.cols;i++){let c=doc.createElement('div');c.className='ed-column';band.append(c);}ci=0;col=band.children[0];}
   function nextColumn(){if(band&&ci+1<d.cols){col=band.children[++ci];}else{if(band)balanceBand();band=null;col=null;newPage();makeBand();}}
   function empty(){return !col||!col.children.length;}
   let fitReason='';function fitColumn(){if(!col)return true;let r=col.getBoundingClientRect();if(r.height>available+2){fitReason='height '+Math.round(r.height)+'/'+Math.round(available);return false;}if(col.scrollWidth>col.clientWidth+2){fitReason='width '+col.scrollWidth+'/'+col.clientWidth;return false;}let bad=[...col.querySelectorAll('*')].find(e=>{if(!boundedElement(e))return false;let b=e.getBoundingClientRect();return b.width&&(b.right>r.right+2||b.left<r.left-2);});if(bad){fitReason='child width '+bad.tagName+' '+Math.round(bad.getBoundingClientRect().right-r.right);return false;}return true;}
   function fitPage(){const r=body.getBoundingClientRect();return [...body.children].every(e=>e.getBoundingClientRect().bottom<=r.bottom+.5);}
   function fitGraphicAfterShortPrefix(clone){
    // Try a measured graphic adjustment before stranding a short source title
    // or running furniture on a page by itself. Never change source/editable
    // dimensions, split a caption, or compress the graphic without a bound.
    const prefix=[...body.children].filter(x=>x!==clone),img=clone.querySelector('img');
    if(!img||!prefix.length||prefix.some(x=>x.querySelector('img,table,pre,.pair'))||prefix.reduce((n,x)=>n+x.textContent.trim().length,0)>240)return false;
    const area=body.getBoundingClientRect(),box=clone.getBoundingClientRect(),picture=img.getBoundingClientRect();
    if(box.top-area.top>area.height*.2||picture.height<=0)return false;
    const limit=picture.height-(box.bottom-area.bottom)-2;
    if(limit<60||limit<picture.height*.65)return false;
    const saved=img.getAttribute('style');img.style.maxHeight=limit+'px';img.style.width='auto';img.style.maxWidth='100%';
    if(fitPage()){
     (report.prefixGraphicFits??=[]).push({block:clone.dataset.block||clone.tagName,previous_height:picture.height,height:img.getBoundingClientRect().height,source_parameters_unchanged:true});return true;
    }
    if(saved===null)img.removeAttribute('style');else img.setAttribute('style',saved);return false;
   }
   function atomic(el,isFull){let clone=el.cloneNode(true);if(isFull){if(band){balanceBand();band=null;col=null;}body.append(clone);if(!fitPage()&&!fitGraphicAfterShortPrefix(clone)){clone.remove();if(body.children.length)newPage();body.append(clone);}if(!fitPage()){let img=clone.matches('img')?clone:clone.querySelector('img');if(img){let rem=body.getBoundingClientRect().bottom-clone.getBoundingClientRect().top-30;img.style.maxHeight=Math.max(30,rem)+'px';img.style.width='auto';img.style.maxWidth='100%';}if(!fitPage())report.errors.push('Full-width block is too tall: '+(el.dataset.block||el.tagName));}}else{if(!band)makeBand();col.append(clone);if(!fitColumn()){clone.remove();if(!empty())nextColumn();col.append(clone);if(!fitColumn()&&body.children.length>1){clone.remove();if(band)balanceBand();newPage();makeBand();col.append(clone);}if(!fitColumn()){let img=clone.matches('img')?clone:clone.querySelector('img');if(img){let caption=clone.querySelector('figcaption'),captionHeight=caption?caption.getBoundingClientRect().height:0,limit=Math.max(60,available-captionHeight-24);img.style.maxHeight=limit+'px';img.style.width='auto';img.style.maxWidth='100%';}if(!fitColumn()){if(clone.matches('figure')){clone.remove();clone.dataset.span='all';if(band)balanceBand();band=null;col=null;atomic(clone,true);}else report.errors.push('Block exceeds the available column height: '+(el.dataset.block||el.tagName)+' ('+fitReason+')');}}}}}
   function textBlock(el){if(!band)makeBand();const text=flowText(el);if(!text.length){atomic(el,false);return;}let start=0;while(start<text.length){let clone=sliceNode(el,start,text.length);col.append(clone);if(fitColumn())break;
   if(start===0&&el.dataset.referenceEntry==='true'&&clone.getBoundingClientRect().height<=available&&col.children.length>1){clone.remove();nextColumn();col.append(clone);if(fitColumn())break;}
   clone.remove();let lo=start,hi=text.length;while(lo<hi){let mid=Math.ceil((lo+hi)/2); // Avoid splitting a UTF-16 surrogate pair.
    if(mid<text.length&&/[\uDC00-\uDFFF]/.test(text[mid]))mid--;
    if(mid<=lo){hi=lo;break;}let probe=sliceNode(el,start,mid);col.append(probe);let fits=fitColumn();probe.remove();if(fits)lo=mid;else hi=mid-1;
   }let end=lo;
   // Keep at least two lines where there is room; do not leave a one-word stub.
   if(end<=start){if(empty()){if(body.children.length>1){newPage();makeBand();continue;}report.errors.push('A character exceeds the content area');col.append(clone);break;}nextColumn();continue;}
   let tail=text.slice(Math.max(start,end-35),end),boundary=Math.max(tail.lastIndexOf(' '),tail.lastIndexOf('。'),tail.lastIndexOf('，'));
   if(boundary>12&&end<text.length)end=end-tail.length+boundary+1;
   if(end<text.length&&/[\uDC00-\uDFFF]/.test(text[end]))end--;
   clone=sliceNode(el,start,end);clone.dataset.continued=String(start>0);col.append(clone);start=end;if(start<text.length)nextColumn();
  }}
   function pairBlock(el){
    // A source/dual-target row stays together when it fits. Oversized units
    // fall back to sequential source/target blocks with the same locators.
    if(band){balanceBand();band=null;col=null;}
    let clone=el.cloneNode(true);body.append(clone);
    if(fitPage())return;clone.remove();
    if(body.children.length)newPage();
    body.append(clone);if(fitPage())return;clone.remove();
    report.warnings.push('Oversized alignment unit reflowed sequentially: '+(el.dataset.block||''));
    for(const node of flatten(el)){let part=node.cloneNode(true);
     if(el.dataset.sourcePage)part.dataset.sourcePage=el.dataset.sourcePage;
     if(el.dataset.sourcePages)part.dataset.sourcePages=el.dataset.sourcePages;
     if(el.dataset.block)part.dataset.block=el.dataset.block;
     if(part.matches('p,.paragraph,pre,blockquote,ul,ol'))textBlock(part);
     else atomic(part,false);
    }
   }
   function alignmentFigureBlock(el){
    // Keep a complete figure plus its bilingual caption together when it fits.
    if(band){balanceBand();band=null;col=null;}
    const probe=el.cloneNode(true);body.append(probe);
    const height=probe.getBoundingClientRect().height,capacity=body.clientHeight;
    probe.remove();
    if(height<=capacity+.5){atomic(el,true);return;}
    const children=flatten(el);
    for(let i=0;i<children.length;i++){
     const child=children[i];reserveNext(child,children[i+1]);
     if(child.matches('.pair'))pairBlock(child);
     else if(child.matches('table,.table-wrap'))tableBlock(child);
     else atomic(child,full(child));
    }
   }
   function tableBlock(el){
    let t=el.matches('table')?el:el.querySelector('table');if(!t){atomic(el,full(el));return;}
    const isFull=full(el);
    if(isFull){if(band){balanceBand();band=null;col=null;}}else if(!band)makeBand();
    // Keep a table intact when it fits a fresh page/column. Split only tables
    // exceeding that capacity; repeated headers must never create an empty page.
    const target=isFull?body:col,probe=el.cloneNode(true);target.append(probe);
    const bounds=probe.getBoundingClientRect(),capacity=isFull?body.clientHeight:available;
    const fitsNow=isFull?fitPage():fitColumn(),hasPrior=target.children.length>1;probe.remove();
    if(!fitsNow&&hasPrior&&bounds.height<=capacity+.5){if(isFull)newPage();else nextColumn();}
    let rows=[...t.rows],headers=rows.filter(r=>r.parentElement.tagName==='THEAD'),data=rows.filter(r=>!headers.includes(r));let wrap,tab,tb;
    const fits=()=>isFull?fitPage():fitColumn();
    function fresh(repeat){
     wrap=el.matches('table')?null:el.cloneNode(false);tab=t.cloneNode(false);
     for(const group of t.children)if(group.matches('colgroup'))tab.append(group.cloneNode(true));
     if(t.caption){let cap=t.caption.cloneNode(true);if(repeat)cap.dataset.repeat='true';tab.append(cap);}
     if(headers.length){let th=doc.createElement('thead');headers.forEach(r=>th.append(r.cloneNode(true)));if(repeat)th.dataset.repeat='true';tab.append(th);}
     tb=doc.createElement('tbody');tab.append(tb);if(wrap)wrap.append(tab);(isFull?body:col).append(wrap||tab);
    }
    // A vertical merge is one pagination group. Splitting its rows independently
    // loses the cell owner on the continuation page.
    const groups=[];for(let i=0;i<data.length;){let end=i+1;const group=[];for(let j=i;j<end&&j<data.length;j++){group.push(data[j]);for(const cell of data[j].cells)end=Math.max(end,cell.rowSpan===0?data.length:j+cell.rowSpan);}groups.push(group);i=end;}
    fresh(false);for(let group of groups){
     let copies=group.map(row=>row.cloneNode(true));copies.forEach(copy=>tb.append(copy));
     if(!fits()){copies.forEach(copy=>copy.remove());let hadRows=tb.children.length>0;
      if(!hadRows)(wrap||tab).remove();
      if(isFull)newPage();else nextColumn();
      fresh(hadRows);copies.forEach(copy=>tb.append(copy));if(!fits())report.errors.push('Table row exceeds the content area; split it manually');
     }
    }if(!data.length&&!fits())report.errors.push('Table header exceeds the content area');
   }
   // Measure explicit prose-to-equation/figure keeps in the actual destination.
   // Long prose remains splittable; never reserve an oversized pair or cross a
   // manual break. The same flag also survives CSS column balancing.
   function reserveNext(el,next){
    if(!next||next.matches('.ed-break')||!(el.dataset.keepNext==='true'||el.matches('h1,h2,h3,h4,h5,h6')))return;
    const isFull=full(el);
    if(isFull&&band){balanceBand();band=null;col=null;}
    if(el.matches('.pair')&&!full(next)){
     // A full-page alignment row can precede a source column graphic.
     // Measure its real column without overriding either explicit span.
     const probe=el.cloneNode(true),wrap=doc.createElement('div');wrap.className='ed-band';
     const column=doc.createElement('div');column.className='ed-column';wrap.append(column);
     for(let i=1;i<d.cols;i++){const c=doc.createElement('div');c.className='ed-column';wrap.append(c);}
     const following=next.cloneNode(true);column.append(following);body.append(probe,wrap);
     const a=probe.getBoundingClientRect(),b=following.getBoundingClientRect(),line=d.size*96/72*d.leading;
     const prose=next.matches('p,pre,blockquote,ul,ol,.paragraph');
     const required=b.top-a.top+(prose?Math.min(b.height,Math.max(36,line*2)):b.height);
     const capacity=body.clientHeight,remaining=body.getBoundingClientRect().bottom-a.top;
     const short=a.height<=Math.max(line*6,capacity*.45);probe.remove();wrap.remove();
     if(short&&required<=capacity+.5&&required>remaining+.5&&body.children.length){
      newPage();(report.keepNextMoves??=[]).push({block:el.dataset.block||el.tagName,next:next.dataset.block||next.tagName});
     }
     return;
    }
    if(isFull!==full(next)){
     // Full-width headings may introduce column prose. Retain the two-line
     // reserve without overriding the source's explicit span choices.
     if(isFull&&el.matches('h1,h2,h3,h4,h5,h6')){
      const probe=el.cloneNode(true);body.append(probe);
      const needed=probe.getBoundingClientRect().height+Math.max(36,d.size*96/72*d.leading*2),remaining=body.getBoundingClientRect().bottom-probe.getBoundingClientRect().top;
      probe.remove();if(remaining<needed&&body.children.length)newPage();
     }
     return;
    }
    if(!isFull&&!band)makeBand();const target=isFull?body:col;
    const probe=el.cloneNode(true),following=next.cloneNode(true);target.append(probe,following);
    const a=probe.getBoundingClientRect(),b=following.getBoundingClientRect(),line=d.size*96/72*d.leading;
    const prose=next.matches('p,pre,blockquote,ul,ol,.paragraph');
    const required=(prose?Math.min(b.height,Math.max(36,line*2)):b.height)+b.top-a.top;
    const limit=isFull?body.getBoundingClientRect().bottom:band.getBoundingClientRect().top+available;
    const remaining=limit-a.top,capacity=isFull?body.clientHeight:available;
    const short=a.height<=Math.max(line*6,capacity*.45);probe.remove();following.remove();
    if(short&&required<=capacity+.5&&required>remaining+.5&&(isFull?body.children.length:!empty())){
     if(isFull)newPage();else nextColumn();
     (report.keepNextMoves??=[]).push({block:el.dataset.block||el.tagName,next:next.dataset.block||next.tagName});
    }
   }
   newPage();const blocks=flatten(source);allExpected+=blocks.map(c=>canonicalText(c)).join('');
   let lastSourcePage=null;
   for(let i=0;i<blocks.length;i++){let e=blocks[i],sourcePage=e.dataset.sourcePage;if(sourcePage&&lastSourcePage&&sourcePage!==lastSourcePage&&(s.preserveSourcePageBreaks===true||!Number.isFinite(Number(sourcePage))||!Number.isFinite(Number(lastSourcePage))||Number(sourcePage)!==Number(lastSourcePage)+1)){const hasContent=[...body.querySelectorAll('[data-uid],img,td,th')].some(x=>x.textContent.trim()||x.tagName==='IMG');const tail=blocks.slice(i).filter(x=>x.dataset.sourcePage===sourcePage),tailText=tail.map(x=>x.textContent).join(' '),footerOnly=tail.length>0&&tail.length<=5&&tail.every(x=>x.matches('p,.paragraph')&&x.textContent.length<260)&&/(authorized licensed use|copyright|all rights reserved|downloaded on|permissions apply|rights reserved|授權|保留所有权利|许可使用|下载于|版權|版權所有)/i.test(tailText);if(hasContent&&!footerOnly){if(band)balanceBand();band=null;col=null;newPage();}}if(sourcePage)lastSourcePage=sourcePage;if(e.classList.contains('ed-break')){if(body.children.length){if(band)balanceBand();band=null;col=null;newPage();}continue;}reserveNext(e,blocks[i+1]);if(e.matches('.alignment-figure'))alignmentFigureBlock(e);else if(e.matches('table,.table-wrap'))tableBlock(e);else if(e.matches('.pair'))pairBlock(e);else if(e.matches('p,pre,blockquote,ul,ol,aside[role="doc-footnote"],.paragraph')){if(full(e))atomic(e,true);else textBlock(e);}else{atomic(e,full(e));}}
   balanceBand();
  }
  const pages=[...stage.children];const artworkAlignment=alignArtwork(stage);report.inlineMathAlignment=artworkAlignment.inline;report.smallGraphicAlignment=artworkAlignment.figures;for(let i=0;i<pages.length;i++){const p=pages[i],b=p.querySelector('.ed-page-body'),r=b.getBoundingClientRect();p.querySelector('.ed-page-number').textContent=(i+1)+' / '+pages.length;let overflow=[...b.querySelectorAll('*')].filter(e=>{if(!boundedElement(e))return false;let a=e.getBoundingClientRect();return a.width&&a.height&&(a.bottom>r.bottom+2||a.right>r.right+2||a.left<r.left-2);});const visible=[...b.querySelectorAll('p,h1,h2,h3,h4,h5,h6,figure,table,.scope-list,.mast')].map(e=>e.getBoundingClientRect()).filter(a=>a.height&&a.width);if(!Number.isFinite(r.width)||!Number.isFinite(r.height)||r.width<=0||r.height<=0)report.errors.push('Pagination has no measurable content area on page '+(i+1));const bottom=Math.max(r.top,...visible.map(a=>a.bottom));const sourcePages=[...new Set([...b.querySelectorAll('[data-source-page],[data-source-pages]')].flatMap(x=>[x.dataset.sourcePage,...(x.dataset.sourcePages||'').split(',')]).filter(Boolean))];p.querySelector('.source-pages').textContent=sourcePages.length?'source p. '+sourcePages.join(', '):'';const bands=[...b.querySelectorAll('.ed-band')].map(a=>{if(a.children.length&&!a.children[0].classList.contains('ed-column')){let groups={};for(let n of a.children){let x=Math.round(n.getBoundingClientRect().left);groups[x]=Math.max(groups[x]||0,n.getBoundingClientRect().bottom-a.getBoundingClientRect().top);}let heights=Object.values(groups);return {balanced:true,heights:heights.map(x=>Math.round(x)),imbalance:heights.length>1?Math.round(Math.max(...heights)-Math.min(...heights)):0};}let cs=[...a.children].filter(x=>x.classList.contains('ed-column'));let heights=cs.map(x=>x.getBoundingClientRect().height);return {balanced:false,heights:heights.map(x=>Math.round(x)),imbalance:heights.length>1?Math.round(Math.max(...heights)-Math.min(...heights)):0};});report.pages.push({page:i+1,overflow:overflow.length,chars:b.textContent.length,images:b.querySelectorAll('img').length,tables:b.querySelectorAll('table').length,source_pages:sourcePages,block_ids:[...new Set([...b.querySelectorAll('[data-block]')].map(x=>x.dataset.block))],vertical_fill:Math.round((bottom-r.top)/r.height*1000)/1000,column_bands:bands});const clone=b.cloneNode(true);clone.querySelectorAll('[data-repeat]').forEach(x=>x.remove());allActual+=canonicalText(clone);}
  report.sparsePages=report.pages.filter(p=>p.chars<80&&!p.images&&!p.tables&&p.vertical_fill<.15&&report.pages.length>1).map(p=>p.page);for(const n of report.sparsePages)report.warnings.push('Sparse page requires source review: '+n);report.readability=readability(stage);for(const issue of report.readability.issues)report.warnings.push('Readability review: '+issue.code+' '+issue.block+' row '+issue.row+' column '+issue.column);report.originalChars=allExpected.length;report.renderedChars=allActual.length;report.textPreserved=allExpected===allActual;const mathKeys=root=>[...root.querySelectorAll('[data-math-token]')].map(e=>e.dataset.mathToken+'|'+e.dataset.mathSha256);report.mathPreserved=JSON.stringify(mathKeys(root))===JSON.stringify(mathKeys(stage));if(!report.mathPreserved)report.errors.push('Formula artwork lost, duplicated or reordered during pagination');report.pass=!report.errors.length&&report.pages.every(x=>!x.overflow)&&report.textPreserved;
  return {stage,report};
 }
 // Freeze every artwork size before snapping any position: resizing a later
 // figure can move earlier baselines within the same grid or balanced column.
 // Size/position edits apply only to the paginated copy, never the source IR.
 function alignArtwork(stage){
  const saved=new Map(),figures=[],inline=[];
  for(const img of stage.querySelectorAll('.ed-page-body figure img,img.inline-math')){
   const r=img.getBoundingClientRect(),cs=img.ownerDocument.defaultView.getComputedStyle(img);
   if(!r.width||!r.height||cs.transform!=='none'||cs.position!=='static'||!['contain','fill','scale-down'].includes(cs.objectFit))continue;
   const page=img.closest('.ed-page').getBoundingClientRect(),parent=img.closest('.pair-source,.pair-target,.ed-column,.ed-page-body'),bounds=parent.getBoundingClientRect();
   const isInline=img.matches('.inline-math'),figure=img.closest('figure'),cap=figure?.querySelector('figcaption'),caption=cap?.getBoundingClientRect();
   saved.set(img,{style:img.getAttribute('style'),from:[r.left-page.left,r.top-page.top,r.width,r.height],isInline,
    captionGap:caption&&caption.width&&caption.height?caption.top-r.bottom:null,figureBottom:figure?.getBoundingClientRect().bottom});
   let w=Math.max(1,Math.min(Math.round(r.width),Math.floor(bounds.width))),h=Math.max(1,Math.round(r.height*w/r.width));
   // Tiny notation may not have an integer box with an adequately close
   // ratio. This applies inside table cells too. Preserve its fractional
   // dimensions while still aligning its position to the print grid.
   if(Math.abs((w/h)/(r.width/r.height)-1)>.005){w=r.width;h=r.height;}
   img.style.setProperty('max-width','none','important');
   img.style.setProperty('width',w+'px','important');img.style.setProperty('height',h+'px','important');img.style.setProperty('object-fit','fill','important');
  }
  // Undo unsafe size changes before measuring final positions. No later size
  // mutation is allowed to invalidate an already aligned baseline.
  for(const [img,before] of saved){
   if(before.isInline)continue;
   const body=img.closest('.ed-page-body').getBoundingClientRect(),figure=img.closest('figure'),r=img.getBoundingClientRect(),cap=figure.querySelector('figcaption')?.getBoundingClientRect();
   if(r.bottom>body.bottom+.01||figure.getBoundingClientRect().bottom>Math.max(body.bottom,before.figureBottom)+.01||before.captionGap!==null&&before.captionGap>=0&&cap.top-r.bottom<-.01){
    if(before.style===null)img.removeAttribute('style');else img.setAttribute('style',before.style);saved.delete(img);
   }
  }
  for(const [img,before] of saved){
   const r=img.getBoundingClientRect(),p=img.closest('.ed-page').getBoundingClientRect(),body=img.closest('.ed-page-body').getBoundingClientRect(),bounds=img.closest('.pair-source,.pair-target,.ed-column,.ed-page-body').getBoundingClientRect();
   const left=Math.ceil(Math.max(body.left,bounds.left)-p.left),right=Math.floor(Math.min(body.right,bounds.right)-p.left-r.width),top=Math.ceil(body.top-p.top),bottom=Math.floor(body.bottom-p.top-r.height);
   if(right<left||bottom<top)continue;
   const x=Math.max(left,Math.min(right,Math.round(r.left-p.left))),y=Math.max(top,Math.min(bottom,Math.round(r.top-p.top)));
   const figure=img.closest('figure'),cap=figure?.querySelector('figcaption')?.getBoundingClientRect(),captionCollision=!before.isInline&&before.captionGap!==null&&before.captionGap>=0&&cap.top-(p.top+y+r.height)<-.01;
   if(!before.isInline&&(r.top<body.top-.01||r.bottom>body.bottom+.01||captionCollision)){
    // Preserve the original style when outward rounding would hit a caption.
    if(before.style===null)img.removeAttribute('style');else img.setAttribute('style',before.style);continue;
   }
   img.style.position='relative';img.style.left=(x-(r.left-p.left))+'px';img.style.top=(y-(r.top-p.top))+'px';
   const final=img.getBoundingClientRect(),record={from:before.from,to:[final.left-p.left,final.top-p.top,final.width,final.height]};
   if(before.isInline)inline.push({token:img.dataset.mathToken,...record});
   else figures.push({block:img.closest('[data-block]')?.dataset.block||'',...record,source_parameters_unchanged:true});
  }
  // Preserve each source glyph's fractional size and baseline. Only its final
  // paginated position is snapped to Chromium's print pixel grid; otherwise
  // tiny SVG glyphs can shift inside their measured PDF destination box.
  for(const glyph of stage.querySelectorAll('.ed-page-body svg[data-source-glyph-sha256]')){
   const r=glyph.getBoundingClientRect(),cs=glyph.ownerDocument.defaultView.getComputedStyle(glyph);
   if(!r.width||!r.height||cs.position!=='static'||cs.transform!=='none')continue;
   const p=glyph.closest('.ed-page').getBoundingClientRect(),body=glyph.closest('.ed-page-body').getBoundingClientRect();
   const bounds=glyph.closest('.pair-source,.pair-target,.ed-column,.ed-page-body').getBoundingClientRect();
   const dx=Math.round(r.left-p.left)-(r.left-p.left),dy=Math.round(r.top-p.top)-(r.top-p.top);
   if(r.left+dx<Math.max(body.left,bounds.left)-.01||r.right+dx>Math.min(body.right,bounds.right)+.01||r.top+dy<body.top-.01||r.bottom+dy>body.bottom+.01)continue;
   glyph.style.position='relative';glyph.style.left=dx+'px';glyph.style.top=dy+'px';
   const final=glyph.getBoundingClientRect();inline.push({kind:'native-source-glyph',sha256:glyph.dataset.sourceGlyphSha256,
    from:[r.left-p.left,r.top-p.top,r.width,r.height],to:[final.left-p.left,final.top-p.top,final.width,final.height],source_parameters_unchanged:true});
  }
  return {inline,figures};
 }
 function readability(stage){
  const issues=[],tables=[];
  for(const table of stage.querySelectorAll('.ed-page-body table')){
   const cells=[...table.querySelectorAll('th,td')].filter(c=>c.closest('table')===table),metrics=[];
   for(const cell of cells){
    const cs=cell.ownerDocument.defaultView.getComputedStyle(cell),box=cell.getBoundingClientRect(),size=parseFloat(cs.fontSize);
    const fragments=[...cell.getClientRects()].filter(r=>r.width>.1&&r.height>.1),paintedWidth=fragments.length?Math.min(...fragments.map(r=>r.width)):box.width;
    const width=paintedWidth-(parseFloat(cs.paddingLeft)||0)-(parseFloat(cs.paddingRight)||0);
    // A tall neighbouring cell stretches the row. Measure this cell's painted
    // text range rather than inferring its line count from the row height.
    const range=cell.ownerDocument.createRange();range.selectNodeContents(cell);
    const rects=[...range.getClientRects()].filter(r=>r.width>.1&&r.height>.1),ys=[];
    for(const r of rects)if(!ys.some(y=>Math.abs(y-r.top)<Math.max(1,size*.25)))ys.push(r.top);
    const lines=ys.length,em=width/Math.max(1,size),text=cell.textContent.trim();
    const narrow=text.length>8&&lines>=5&&em<7,severe=text.length>8&&lines>=6&&em<3;
    metrics.push({row:cell.parentElement.rowIndex+1,column:cell.cellIndex+1,width_px:Math.round(width*10)/10,font_pt:Math.round(size*.75*100)/100,lines,measure_em:Math.round(em*100)/100,narrow,severe});
   }
   const block=table.closest('[data-block]')?.dataset.block||'',page=Number(table.closest('.ed-page')?.querySelector('.ed-page-number')?.textContent.split('/')[0])||null,entry={block,page,span:table.closest('[data-span]')?.dataset.span||'auto',cells:metrics};tables.push(entry);
   for(const m of metrics.filter(m=>m.narrow))issues.push({code:'narrow-table-cell',severity:m.severe?'severe':'review',block,page,row:m.row,column:m.column,measure_em:m.measure_em,lines:m.lines,manual_span_preserved:entry.span==='column',action:entry.span==='column'?'Inspect source and retain the explicit column choice until an authorized presentation patch changes it.':'Compare the source and consider a wider span or source-supported column proportions before reducing type.'});
  }
  return {tables,issues,severe:issues.filter(x=>x.severity==='severe').length,review:issues.filter(x=>x.severity==='review').length,scope:'Measured text density prompts; not semantic or aesthetic certification.'};
 }
 function rank(section,root){const d=section.design,els=root.querySelectorAll('*').length||1,f={columns:d.cols,landscape:Number(d.w>d.h),text:Math.min(1,root.textContent.length/1500),images:Math.min(1,root.querySelectorAll('img').length*.25),tables:Math.min(1,root.querySelectorAll('table').length*.3),headings:Math.min(1,root.querySelectorAll('h1,h2,h3').length*.1),linebreaks:root.querySelector('pre')?.6:0};return CATALOG.map(t=>{let entries=Object.entries(t.fit_features),fit=entries.reduce((a,[k,v])=>a+1-Math.min(1,Math.abs((f[k]??(k==='columns'?1:0))-v)/(k==='columns'?2:1)),0)/entries.length;let ratio=1-Math.min(1,Math.abs(d.w/d.h-t.page_mm[0]/t.page_mm[1]));return {template:t,score:.7*fit+.2*ratio+.1*Number(t.columns===d.cols),features:f};}).sort((a,b)=>b.score-a.score);}
 return {baseCSS,styles,vars,paginate,rank,flatten,esc,readability};
})();
