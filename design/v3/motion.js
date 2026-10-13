// Closing movement preserves native dialog focus behavior; reduced motion closes immediately.
const navigationToggle = document.querySelector('#navigation-toggle');
const navigationDialog = document.querySelector('#navigation-dialog');
navigationToggle?.addEventListener('click',()=>navigationDialog.showModal());
navigationDialog?.addEventListener('close',()=>{
  if(navigationToggle.getBoundingClientRect().width) navigationToggle.focus();
  else document.querySelector('.sidebar [aria-current="page"]')?.focus();
});
matchMedia('(min-width: 761px)').addEventListener('change',event=>{
  if(event.matches && navigationDialog?.open) navigationDialog.close();
});
function dismissWithMotion(dialog) {
  if (dialog.dataset.closing) return;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) { dialog.close(); return; }
  dialog.dataset.closing = 'true';
  const drawer = dialog.classList.contains('drawer');
  dialog.animate([{opacity:1,transform:'none'},{opacity:0,transform:drawer?'translateX(20px)':'translateY(8px)'}],{duration:180,easing:'cubic-bezier(.2,.65,.3,1)'}).finished.then(()=>{
    delete dialog.dataset.closing;
    dialog.close();
  });
}
document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('cancel',event=>{
  event.preventDefault(); dismissWithMotion(dialog);
}));
document.addEventListener('click',event=>{
  const dialog = event.target.closest('dialog[open]');
  if(!dialog) return;
  let close = Boolean(event.target.closest('[data-close]'));
  if(event.target === dialog){
    const rect=dialog.getBoundingClientRect();
    close = event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom;
  }
  if(close){event.preventDefault();event.stopImmediatePropagation();dismissWithMotion(dialog);}
},true);
