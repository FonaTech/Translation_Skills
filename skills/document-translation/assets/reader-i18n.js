/* Original self-contained reader interface localization. MIT, Yufeng Zhan. */
window.TranslationReader=(()=>{
 const catalogs=TRANSLATION_READER_LOCALES,nav=document.querySelector('[data-reader-toolbar]'),key='document-reader-ui-language-v101';
 let locale='en',preference='auto';
 const names={en:'English','zh-Hans':'简体中文','zh-Hant':'繁體中文',ja:'日本語',es:'Español',fr:'Français',de:'Deutsch',pt:'Português',it:'Italiano',ru:'Русский',ko:'한국어',ar:'العربية',hi:'हिन्दी',id:'Bahasa Indonesia',vi:'Tiếng Việt',tr:'Türkçe'};
 function match(tag){tag=String(tag||'').trim().replace(/_/g,'-').toLowerCase();if(!/^[a-z]{2,8}(?:-[a-z0-9]{1,8})*$/.test(tag))return null;if(/^zh(?:-|$)/.test(tag)){if(/-hans(?:-|$)/.test(tag))return 'zh-Hans';if(/-hant(?:-|$)|-(?:tw|hk|mo)(?:-|$)/.test(tag))return 'zh-Hant';return 'zh-Hans';}const base=tag.split('-')[0];return Object.hasOwn(catalogs,base)?base:null;}
 function detect(){let tags=[];try{tags=Array.from(navigator.languages||[]);}catch{}if(!tags.length)try{if(navigator.language)tags=[navigator.language];}catch{}for(const tag of tags){const found=match(tag);if(found)return found;}return 'en';}
 function t(label){return catalogs[locale]?.[label]??catalogs.en[label]??label;}
 function apply(){locale=preference==='auto'?detect():preference;if(!nav)return locale;nav.lang=locale;nav.dir=locale==='ar'?'rtl':'ltr';for(const el of nav.querySelectorAll('[data-reader-label]'))el.textContent=t(el.dataset.readerLabel);const select=nav.querySelector('[data-reader-language]');if(select){select.value=preference;select.setAttribute('aria-label',t('language'));select.title=t('language');}nav.dataset.uiLocale=locale;return locale;}
 function select(value){preference=value==='auto'||Object.hasOwn(catalogs,value)?value:'auto';try{localStorage.setItem(key,preference);}catch{}return apply();}
 function toggle(){const active=document.body.classList.toggle('reading-flow');nav?.querySelector('[data-reader-action="view"]')?.setAttribute('aria-pressed',String(active));return active;}
 if(nav){const select=nav.querySelector('[data-reader-language]');if(select){for(const [tag,name] of Object.entries(names)){const option=document.createElement('option');option.value=tag;option.textContent=name;option.lang=tag;select.append(option);}select.addEventListener('change',()=>window.TranslationReader.select(select.value));}try{const saved=localStorage.getItem(key);if(saved==='auto'||Object.hasOwn(catalogs,saved))preference=saved;}catch{}apply();window.addEventListener('languagechange',()=>{if(preference==='auto')apply();});}
 return {t,match,detect,select,toggle,get locale(){return locale;},get preference(){return preference;},locales:Object.keys(catalogs)};
})();
