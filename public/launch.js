// A presentation-only wrapper: authentication remains inside the viewer.
export function setupLaunch(win=window, doc=document){
  const choice=doc.getElementById('tab-choice');
  const error=doc.getElementById('tab-error');
  let cancelPending=()=>{};
  const showViewer=()=>{
    cancelPending();
    choice.hidden=true;
    doc.getElementById('login').hidden=false;
    doc.getElementById('connection-details').hidden=false;
    doc.getElementById('key').focus();
  };
  let inWrapper=false;
  try{inWrapper=win.parent!==win && win.parent.location.href==='about:blank' && win.parent.document.getElementById('desktop-viewer')?.contentWindow===win;}catch{}
  if(inWrapper){showViewer();return;}
  doc.getElementById('login').hidden=true;
  doc.getElementById('connection-details').hidden=true;
  choice.hidden=false;
  doc.getElementById('stay-tab').onclick=showViewer;
  let opening=false;
  doc.getElementById('cloak-tab').onclick=()=>{
    if(opening)return;
    error.hidden=true;
    let popup;
    try{popup=win.open('about:blank','_blank');}catch{}
    if(!popup || popup.closed){
      error.textContent='The browser blocked the new tab. Allow pop-ups for this site and try Cloak again, or choose Stay in this tab.';
      error.hidden=false;return;
    }
    opening=true;
    let active=true,timer;
    cancelPending=()=>{
      active=false;opening=false;win.clearTimeout(timer);popup.close();
      cancelPending=()=>{};
    };
    const fail=()=>{
      if(!active)return;
      cancelPending();
      error.textContent='The viewer did not load in the new tab. Close that tab and try again, or choose Stay in this tab.';
      error.hidden=false;
    };
    try{
      const origin=win.location.origin;
      const shell=popup.document;
      shell.title='Google Classroom';
      const css=shell.createElement('link');css.rel='stylesheet';css.href=origin+'/cloak.css';
      const icon=shell.createElement('link');icon.rel='icon';icon.href=origin+'/cloak-icon.svg';
      shell.head.append(css,icon);
      const frame=shell.createElement('iframe');
      frame.id='desktop-viewer';frame.title='Remote desktop viewer';
      frame.allow='fullscreen; autoplay; clipboard-write';frame.allowFullscreen=true;
      frame.referrerPolicy='no-referrer';
      // No connection code, token, query string or fragment is copied to the new tab.
      frame.src=origin+'/';
      timer=win.setTimeout(fail,15000);
      frame.addEventListener('load',()=>{
        if(!active)return;
        win.clearTimeout(timer);
        try{
          if(popup.closed || !frame.contentDocument?.getElementById('connect-form')){fail();return;}
          popup.opener=null;
          active=false;opening=false;cancelPending=()=>{};
          win.location.replace('https://classroom.google.com/');
        }catch{fail();}
      },{once:true});
      shell.body.append(frame);
    }catch{fail();}
  };
}

if(typeof window!=='undefined')setupLaunch();
