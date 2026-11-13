import {test} from 'node:test';
import assert from 'node:assert/strict';
import {setupInstall} from '../public/install.js';

function fixture({standalone=false,embedded=false}={}){
  const nodes=new Map(), handlers={};
  const get=id=>{
    if(!nodes.has(id))nodes.set(id,{hidden:false,textContent:'',handlers:{},addEventListener(name,fn){this.handlers[name]=fn;}});
    return nodes.get(id);
  };
  const media={matches:standalone,addEventListener(name,fn){this.change=fn;}};
  const win={matchMedia:()=>media,addEventListener(name,fn){handlers[name]=fn;}};
  win.top=embedded?{}:win;
  setupInstall(win,{getElementById:get});
  return {get,media,handlers};
}

test('installation is optional, hidden in app windows and embedded viewers',()=>{
  const tab=fixture();assert.equal(tab.get('app-install').hidden,false);
  assert.equal(tab.get('install-app').hidden,true);
  for(const opts of [{standalone:true},{embedded:true}])assert.equal(fixture(opts).get('app-install').hidden,true);
  tab.media.matches=true;tab.media.change();assert.equal(tab.get('app-install').hidden,true);
});

test('install needs a click and consumes the prompt once, including double clicks',async()=>{
  const f=fixture();let calls=0,release;
  const choice=new Promise(resolve=>{release=resolve;});
  f.handlers.beforeinstallprompt({preventDefault(){},prompt(){calls++;},userChoice:choice});
  assert.equal(calls,0);assert.equal(f.get('install-app').hidden,false);
  const pending=f.get('install-app').handlers.click();
  await f.get('install-app').handlers.click();assert.equal(calls,1);
  release({outcome:'accepted'});await pending;
  assert.match(f.get('install-status').textContent,/disconnect this viewer/);
  assert.equal(f.get('install-app').hidden,true);
  await f.get('install-app').handlers.click();assert.equal(calls,1);
});

test('dismissal and prompt failure offer the browser path without affecting login',async()=>{
  for(const outcome of ['dismissed','error']){
    const f=fixture();
    f.handlers.beforeinstallprompt({preventDefault(){},prompt(){if(outcome==='error')throw Error('blocked');},userChoice:Promise.resolve({outcome})});
    await f.get('install-app').handlers.click();
    assert.match(f.get('install-status').textContent,/keep using this tab/);
    assert.equal(f.get('install-app').hidden,true);
    f.handlers.beforeinstallprompt({preventDefault(){},prompt(){},userChoice:Promise.resolve({outcome:'accepted'})});
    assert.equal(f.get('install-app').hidden,false);
  }
});

test('browser-menu installation clears a pending prompt',()=>{
  const f=fixture();f.handlers.beforeinstallprompt({preventDefault(){}});
  f.handlers.appinstalled();assert.equal(f.get('install-app').hidden,true);
  assert.match(f.get('install-status').textContent,/one viewer/);
});
