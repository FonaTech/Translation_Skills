/* Original bounded SVG validation and raster fallback. MIT, Yufeng Zhan. */
const VectorImages=(()=>{
 const ns='http://www.w3.org/2000/svg',tags=new Set('svg g defs path rect circle ellipse line polyline polygon use clipPath mask linearGradient radialGradient stop pattern image text tspan title desc symbol'.split(' ')),raster=/^data:image\/(?:png|jpeg|gif|webp);base64,[a-z0-9+/=\s]+$/i,cache=new Map();
 function safeRaster(uri){
  if(!raster.test(uri))return false;
  try{
   const a=Uint8Array.from(atob(uri.split(',')[1]),c=>c.charCodeAt(0));
   if(a.length>32*1024*1024)return false;
   if(a[0]===137&&a[1]===80&&a[2]===78&&a[3]===71&&a[4]===13&&a[5]===10&&a[6]===26&&a[7]===10)return true;
   if(String.fromCharCode(...a.slice(0,6)).match(/^GIF8[79]a$/))return true;
   if(String.fromCharCode(...a.slice(0,4))==='RIFF'&&String.fromCharCode(...a.slice(8,12))==='WEBP')return true;
   if(a[0]!==255||a[1]!==216)return false;
   let i=2;
   while(i<a.length){
    if(a[i++]!==255)return false;while(a[i]===255)i++;const marker=a[i++];
    if(marker===217||marker===218)break;
    if(marker===216||marker===1||(marker>=208&&marker<=215))continue;
    const length=a[i]*256+a[i+1];if(length<2||i+length>a.length)return false;
    if(marker>=192&&marker<=207&&![196,200,204].includes(marker))return length>=8&&[1,3].includes(a[i+7]);
    i+=length;
   }
  }catch{}
  return false;
 }
 function valid(uri){
  if(raster.test(uri))return safeRaster(uri);
  if(!/^data:image\/svg\+xml;base64,[a-z0-9+/=\s]+$/i.test(uri)||uri.length>45*1024*1024)return false;
  if(cache.has(uri))return cache.get(uri);
  let result=false;
  try{
   const bytes=Uint8Array.from(atob(uri.split(',')[1]),c=>c.charCodeAt(0)),source=new TextDecoder('utf-8',{fatal:true}).decode(bytes);
   if(bytes.length>32*1024*1024||/<!\s*(?:DOCTYPE|ENTITY)/i.test(source))throw Error('SVG declarations');
   const doc=new DOMParser().parseFromString(source,'image/svg+xml');
   if(doc.querySelector('parsererror')||doc.documentElement.namespaceURI!==ns||doc.documentElement.localName!=='svg')throw Error('SVG root');
   for(const el of doc.querySelectorAll('*')){
    if(el.namespaceURI!==ns||!tags.has(el.localName))throw Error('SVG element');
    for(const a of el.attributes){
     const key=a.localName.toLowerCase(),value=a.value;
     if(key.startsWith('on')||['src','base'].includes(key))throw Error('SVG active attribute');
     if(key==='href'&&!/^#[A-Za-z_][\w:.-]*$/.test(value)&&!(el.localName==='image'&&safeRaster(value)))throw Error('SVG external reference or unsafe raster colors');
     if(/@import|expression\s*\(|javascript:|<\s*\/?\s*script/i.test(value))throw Error('SVG active value');
     for(const match of value.matchAll(/url\s*\(([^)]*)\)/gi))if(!/^#[A-Za-z_][\w:.-]*$/.test(match[1].trim().replace(/^["']|["']$/g,'')))throw Error('SVG external paint');
    }
   }
   result=true;
  }catch{}
  if(cache.size>=8)cache.delete(cache.keys().next().value);cache.set(uri,result);return result;
 }
 async function prepare(roots){
  for(const root of roots)for(const img of root.querySelectorAll('img')){
   let uri=img.getAttribute('src')||'';
   if(!valid(uri)){
    const fallback=img.dataset.rasterFallback||'';
    if(!/^data:image\/png;base64,/i.test(fallback)||!valid(fallback))throw Error('Unsafe or missing figure; re-export from its original source before export');
    img.src=fallback;uri=fallback;img.dataset.assetColorStatus='unsafe-vector-replaced-with-png';
   }
   await img.decode();
   if(!/^data:image\/(?:svg\+xml|webp);base64,/i.test(uri))continue;
   // A verified source-rendered fallback is more reliable than redrawing SVG
   // in a different renderer, and must survive repeated exports byte for byte.
   const existing=img.getAttribute('data-raster-fallback')||'';
   if(/^data:image\/png;base64,/i.test(existing)&&valid(existing))continue;
   const ratio=img.naturalWidth/Math.max(1,img.naturalHeight),width=Math.min(4096,Math.max(1,img.naturalWidth*2.5)),height=Math.max(1,Math.round(width/ratio));
   if(!Number.isFinite(height)||height>8192||width*height>20*1024*1024)throw Error('Image is too large; provide a verified PNG fallback');
   const canvas=document.createElement('canvas');canvas.width=Math.round(width);canvas.height=height;const context=canvas.getContext('2d');if(!context)throw Error('The browser cannot create a fallback image');context.fillStyle='white';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(img,0,0,canvas.width,canvas.height);img.dataset.rasterFallback=canvas.toDataURL('image/png');
  }
 }
 return {valid,prepare};
})();
