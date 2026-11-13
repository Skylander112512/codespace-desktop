// Installation is optional. The app uses the exact same viewer and server.
// No service worker, offline cache, saved key, or second connection is created.
export function setupInstall(win=window, doc=document){
  const card=doc.getElementById('app-install');
  const button=doc.getElementById('install-app');
  const status=doc.getElementById('install-status');
  const standalone=win.matchMedia?.('(display-mode: standalone)');
  let pending=null, busy=false;
  let embedded=false;
  try{embedded=win.top!==win;}catch{embedded=true;}
  const installed=()=>Boolean(standalone?.matches);
  function refresh(){
    card.hidden=embedded || installed();
    button.hidden=!pending || busy;
  }
  win.addEventListener('beforeinstallprompt',event=>{
    event.preventDefault();
    pending=event;
    status.textContent='Install this viewer in its own window, or keep using this tab.';
    refresh();
  });
  win.addEventListener('appinstalled',()=>{
    pending=null;
    status.textContent='Installed. Disconnect this viewer before opening the app, so only one viewer connects at a time.';
    refresh();
  });
  standalone?.addEventListener('change',refresh);
  button.addEventListener('click',async()=>{
    const prompt=pending;
    if(!prompt || busy)return;
    pending=null;busy=true;refresh();
    try{
      await prompt.prompt();
      const result=await prompt.userChoice;
      status.textContent=result.outcome==='accepted'
        ? 'Installation requested. Once installed, disconnect this viewer before opening the app.'
        : 'Installation canceled. You can keep using this tab or install later from Chrome’s menu.';
    }catch{
      status.textContent='Chrome could not show the install prompt. Try Install page as app in Chrome’s menu, or keep using this tab.';
    }finally{busy=false;refresh();}
  });
  refresh();
}

if(typeof window!=='undefined')setupInstall();
