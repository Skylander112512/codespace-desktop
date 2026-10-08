import {test} from 'node:test';
import assert from 'node:assert/strict';
import {setupLaunch} from '../public/launch.js';

function fixture(){
  const node=()=>({hidden:false,children:[],handlers:{},append(...items){this.children.push(...items);},focus(){this.focused=true;},addEventListener(name,fn){this.handlers[name]=fn;}});
  const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
  const shell={head:node(),body:node(),createElement:node};
  const popup={document:shell,closed:false,opener:{},close(){this.closed=true;}};
  const redirects=[],opens=[],timers=[];
  const win={location:{origin:'https://viewer.example',href:'https://viewer.example/?private=value#secret',replace:url=>redirects.push(url)},
    open(...args){opens.push(args);return popup;},setTimeout(fn){timers.push(fn);return timers.length;},clearTimeout(){}};
  win.parent=win;
  const doc={getElementById:get};
  return {win,doc,get,popup,shell,redirects,opens,timers};
}

test('stay in current tab shows login without opening or navigating anywhere',()=>{
  const f=fixture();setupLaunch(f.win,f.doc);
  assert.equal(f.get('login').hidden,true);
  f.get('stay-tab').onclick();
  assert.equal(f.get('login').hidden,false);assert.equal(f.get('tab-choice').hidden,true);
  assert.equal(f.get('key').focused,true);assert.deepEqual(f.opens,[]);assert.deepEqual(f.redirects,[]);
});
test('blocked popup preserves current page and offers retry or normal tab',()=>{
  const f=fixture();f.win.open=()=>null;setupLaunch(f.win,f.doc);f.get('cloak-tab').onclick();
  assert.match(f.get('tab-error').textContent,/blocked/);assert.deepEqual(f.redirects,[]);
  f.get('stay-tab').onclick();assert.equal(f.get('login').hidden,false);
});
test('cloak embeds only the viewer origin and redirects after the viewer loads',()=>{
  const f=fixture();setupLaunch(f.win,f.doc);f.get('cloak-tab').onclick();f.get('cloak-tab').onclick();
  assert.equal(f.opens.length,1);assert.deepEqual(f.opens[0],['about:blank','_blank']);
  const frame=f.shell.body.children[0];
  assert.equal(frame.src,'https://viewer.example/');assert.equal(frame.allowFullscreen,true);
  assert.equal(frame.allow,'fullscreen; autoplay');assert.equal(f.shell.title,'Google Classroom');
  assert.deepEqual(f.redirects,[]);
  frame.contentDocument={getElementById:id=>id==='connect-form'?{}:null};frame.handlers.load();
  assert.equal(f.popup.opener,null);assert.deepEqual(f.redirects,['https://classroom.google.com/']);
});
test('iframe failure or timeout never redirects and can be retried',()=>{
  for(const timeout of [false,true]){
    const f=fixture();setupLaunch(f.win,f.doc);f.get('cloak-tab').onclick();
    const frame=f.shell.body.children[0];
    if(timeout)f.timers[0]();else frame.handlers.load();
    frame.contentDocument={getElementById:()=>({})};frame.handlers.load();
    assert.deepEqual(f.redirects,[]);assert.equal(f.popup.closed,true);
    assert.equal(f.get('tab-error').hidden,false);
  }
});
test('choosing same tab while loading cancels pending cloak navigation',()=>{
  const f=fixture();setupLaunch(f.win,f.doc);f.get('cloak-tab').onclick();f.get('stay-tab').onclick();
  const frame=f.shell.body.children[0];frame.contentDocument={getElementById:()=>({})};frame.handlers.load();
  assert.equal(f.popup.closed,true);assert.deepEqual(f.redirects,[]);assert.equal(f.get('login').hidden,false);
});
test('the blank wrapper shows login directly without nesting another launch screen',()=>{
  const f=fixture();f.win.parent={location:{href:'about:blank'},document:{getElementById:()=>({contentWindow:f.win})}};
  setupLaunch(f.win,f.doc);assert.equal(f.get('tab-choice').hidden,true);assert.equal(f.get('login').hidden,false);
  assert.deepEqual(f.opens,[]);
});
