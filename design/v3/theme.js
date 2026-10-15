// Only appearance is persisted. No user, URL or credential storage.
(()=>{
 let saved; try { saved=localStorage.getItem('rm-v3-theme'); } catch {}
 document.documentElement.dataset.theme=saved==='dark'?'dark':'light';
 document.addEventListener('DOMContentLoaded',()=>{
  const buttons=document.querySelectorAll('.theme-toggle');
  function sync(){const dark=document.documentElement.dataset.theme==='dark';buttons.forEach(b=>{b.setAttribute('aria-pressed',String(dark));b.setAttribute('aria-label',dark?'Włącz tryb jasny':'Włącz tryb ciemny');const text=b.querySelector('span');if(text)text.textContent=dark?'Tryb jasny':'Tryb ciemny';});}
  buttons.forEach(b=>b.addEventListener('click',()=>{document.documentElement.dataset.theme=document.documentElement.dataset.theme==='dark'?'light':'dark';try{localStorage.setItem('rm-v3-theme',document.documentElement.dataset.theme);}catch{}sync();}));sync();
 });
})();
