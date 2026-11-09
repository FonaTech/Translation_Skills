/* Original self-contained HTML image pooling. MIT, Yufeng Zhan. */
const AssetBundle=(()=>{
 const limit=256*1024*1024;
 // Only this fixed resolver runs in an exported document. Imported scripts are
 // always discarded; importing restores validated local data in an inert DOM.
 function hydrate(){const pool=document.querySelector('script[data-studio-image-pool]');if(!pool)return;try{
  const assets=JSON.parse(pool.textContent);
  for(const e of document.querySelectorAll('img[data-studio-src]')){
   const src=assets[e.dataset.studioSrc],fallback=assets[e.dataset.studioFallback];
   if(typeof src==='string'&&/^data:image\/(?:png|jpeg|gif|webp|svg\+xml);base64,/i.test(src))e.src=src;
   if(typeof fallback==='string'&&/^data:image\/png;base64,/i.test(fallback))e.dataset.rasterFallback=fallback;
  }
  window.studioAssetsReady=true;
 }catch(error){window.studioAssetsError=String(error);}}
 function collector(){const assets=[],ids=new Map();
  const id=uri=>{if(!ids.has(uri)){ids.set(uri,String(assets.length));assets.push(uri);}return ids.get(uri);};
  return {assets,collect(root){for(const e of root.querySelectorAll('img')){
   const src=e.getAttribute('src'),fallback=e.getAttribute('data-raster-fallback');
   if(src&&/^data:image\//i.test(src)){e.dataset.studioSrc=id(src);e.removeAttribute('src');}
   if(fallback&&/^data:image\/png;base64,/i.test(fallback)){e.dataset.studioFallback=id(fallback);e.removeAttribute('data-raster-fallback');}
  }return root;}};
 }
 function restore(doc){const pool=doc.querySelector('script[data-studio-image-pool]');if(!pool)return;
  const assets=JSON.parse(pool.textContent);if(!Array.isArray(assets)||assets.length>20000)throw Error('Invalid embedded image pool');
  const checked=new Map(),get=(key,fallback=false)=>{
   if(!/^\d+$/.test(key||'')||Number(key)>=assets.length)throw Error('Missing embedded image');
   const uri=assets[Number(key)];if(typeof uri!=='string'||fallback&&!/^data:image\/png;base64,/i.test(uri))throw Error('Invalid embedded image');
   if(!checked.has(key)){if(!VectorImages.valid(uri))throw Error('Unsafe embedded image');checked.set(key,true);}return uri;
  };
  for(const e of doc.querySelectorAll('img[data-studio-src]')){
   e.setAttribute('src',get(e.dataset.studioSrc));
   if(e.hasAttribute('data-studio-fallback'))e.setAttribute('data-raster-fallback',get(e.dataset.studioFallback,true));
   e.removeAttribute('data-studio-src');e.removeAttribute('data-studio-fallback');
  }
  pool.remove();
 }
 function scripts(assets,nonce){return '<script type="application/json" data-studio-image-pool>'+JSON.stringify(assets).replace(/</g,'\\u003c')+'<'+ '/script><script nonce="'+nonce+'">('+hydrate.toString()+')();<'+ '/script>';}
 return {limit,collector,restore,scripts};
})();
