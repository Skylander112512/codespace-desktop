import {receiveQuality} from '../public/video-quality.js';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

function browser(){
  const nodes=new Map();const documentHandlers={};
  const get=id=>{
    if(!nodes.has(id))nodes.set(id,{hidden:['desktop','connection-error'].includes(id),value:'',textContent:'',handlers:{},
      addEventListener(type,fn){this.handlers[type]=fn;},removeAttribute(){},focus(){},hasPointerCapture(){return false;},checked:false});
    return nodes.get(id);
  };
  class Socket {
    static OPEN=1;
    constructor(){this.readyState=1;this.sent=[];Socket.latest=this;}
    send(data){this.sent.push(JSON.parse(data));}
    close(code,reason){this.readyState=3;this.onclose({code,reason});}
  }
  const context={receiveQuality,document:{getElementById:get,body:{classList:{add(){},remove(){}}},addEventListener(name,fn){documentHandlers[name]=fn;},exitPointerLock(){this.pointerLockElement=null;}},
    window:{addEventListener(){}},location:{protocol:'https:',host:'example.test'},WebSocket:Socket,
    performance:{now:()=>100},setInterval:()=>1,clearInterval(){},setTimeout:()=>1,clearTimeout(){}};
  vm.createContext(context);
  vm.runInContext(readFileSync(new URL('../public/client.js',import.meta.url),'utf8').replace(/^import .*;\n/,''),context);
  return {get,Socket,documentHandlers,run:code=>vm.runInContext(code,context),context,submit(){get('key').value='viewer-test-key';get('connect-form').handlers.submit({preventDefault(){}});return Socket.latest;}};
}

test('viewer stays on login until authenticated and retains a rejected key',()=>{
  const b=browser(), ws=b.submit();ws.onopen();
  assert.equal(b.get('login').hidden,false);
  assert.equal(b.get('desktop').hidden,true);
  ws.close(4003,'Invalid access key');
  assert.equal(b.get('key').value,'viewer-test-key');
  assert.equal(b.get('connect-button').disabled,false);
  assert.match(b.get('connection-error').textContent,/4003.*Invalid access key/);
  assert.equal(b.get('connection-error').hidden,false);
});

test('successful login clears the field; network failure keeps the session waiting',()=>{
  const b=browser(),ws=b.submit();ws.onopen();
  ws.onmessage({data:JSON.stringify({type:'authenticated',version:'0.1.2'})});
  assert.equal(b.get('login').hidden,true);
  assert.equal(b.get('desktop').hidden,false);
  assert.equal(b.get('key').value,'');
  ws.close(1006,'');
  assert.equal(b.get('login').hidden,true);
  assert.equal(b.get('desktop').hidden,false);
  assert.match(b.get('status').textContent,/Retrying in 2 seconds/);
  assert.equal(b.run('sessionKey'),'viewer-test-key');
  assert.match(b.get('details-log').textContent,/code accepted/);
  assert.ok(!b.get('details-log').textContent.includes('viewer-test-key'));
});


test('separate motion transport drops stale buffered movement without losing key releases',()=>{
  const b=browser();b.submit();
  b.run(`useRTC=true;channel={readyState:'open',bufferedAmount:0,sent:[],send(data){this.sent.push(JSON.parse(data));}};
    motionChannel={readyState:'open',bufferedAmount:4000,sent:[],send(data){this.sent.push(JSON.parse(data));}};
    control({type:'input',action:'move',x:.5,y:.5});
    control({type:'input',action:'key',code:'KeyA',down:false});`);
  assert.equal(b.run('motionChannel.sent.length'),0);
  assert.equal(b.run('channel.sent[0].action'),'key');
  b.run(`motionChannel.bufferedAmount=0;control({type:'input',action:'move',x:.8,y:.8});`);
  assert.equal(b.run('motionChannel.sent[0].after'),b.run('channel.sent[0].seq'));
});

test('stalled decoded frames fall back even if video currentTime keeps advancing',async()=>{
  const b=browser();b.submit();
  b.get('video').readyState=4;
  b.context.performance.now=()=>10000;
  b.run(`pc={connectionState:'connected',getStats:async()=>new Map([['video',{id:'video',type:'inbound-rtp',kind:'video',framesDecoded:60,timestamp:2000}]])};
    previousStats={id:'video',framesDecoded:60,timestamp:1000};lastVideoAt=100;useRTC=true;`);
  b.get('video').currentTime=500;
  await b.run('sampleStats()');b.run('chooseMode()');
  assert.equal(b.run('useRTC'),false);
  assert.equal(b.get('mode-label').textContent,'Compatibility relay');
});


test('retry reuses only the in-memory code; Disconnect cancels retry and clears it',()=>{
  const b=browser(), first=b.submit();first.onopen();
  first.onmessage({data:JSON.stringify({type:'authenticated'})});
  first.close(1006,'offline');
  b.run('connectWithKey(sessionKey)');
  const second=b.Socket.latest;assert.notEqual(first,second);second.onopen();
  assert.equal(second.sent[0].key,'viewer-test-key');
  second.close(1006,'offline');
  assert.match(b.get('status').textContent,/Retrying in 4 seconds/);
  b.get('disconnect').onclick();
  assert.equal(b.run('sessionKey'),null);assert.equal(b.run('keepTrying'),false);
  b.run('connectWithKey(sessionKey)');assert.equal(b.Socket.latest,second);
  assert.equal(b.get('login').hidden,false);
});

test('authentication rejection after a retry clears memory and requires user input',()=>{
  const b=browser(),first=b.submit();first.onopen();first.close(1006,'offline');
  b.run('connectWithKey(sessionKey)');
  b.Socket.latest.close(4003,'Invalid access code');
  assert.equal(b.run('sessionKey'),null);assert.equal(b.run('keepTrying'),false);
  assert.equal(b.get('login').hidden,false);
});


test('game mouse accumulates relative movement and routes it over motion transport',()=>{
  const b=browser();b.submit();
  b.run('relativeMouseAvailable=true');
  b.run(`useRTC=true;channel={readyState:'open',bufferedAmount:0,send(){}};
    motionChannel={readyState:'open',bufferedAmount:0,sent:[],send(data){this.sent.push(JSON.parse(data));}};`);
  b.context.document.pointerLockElement=b.get('screen');
  b.documentHandlers.pointerlockchange();
  b.documentHandlers.mousemove({movementX:8,movementY:-2});
  b.documentHandlers.mousemove({movementX:5,movementY:3});
  b.run('flushMotion()');
  const input=b.run('motionChannel.sent[0]');
  assert.equal(input.action,'look');assert.equal(input.dx,13);assert.equal(input.dy,1);
  assert.equal(input.after,b.run('lastReliable'));
  assert.equal(b.run('pendingMotion'),null);
});

test('locked clicks stay relative and unlock releases held input and queued turns',()=>{
  const b=browser(),ws=b.submit();
  b.run('relativeMouseAvailable=true');
  b.context.document.pointerLockElement=b.get('screen');b.documentHandlers.pointerlockchange();
  b.get('screen').onpointerdown({button:2,preventDefault(){}});
  assert.equal(ws.sent.at(-1).relative,true);assert.equal(ws.sent.at(-1).button,2);
  b.documentHandlers.mousemove({movementX:12,movementY:0});
  b.context.document.pointerLockElement=null;b.documentHandlers.pointerlockchange();
  assert.equal(ws.sent.at(-1).action,'release');assert.equal(b.run('pendingMotion'),null);
  assert.equal(b.get('game-mouse').textContent,'Game mouse · `');
  b.run('flushMotion()');assert.equal(ws.sent.at(-1).action,'release');
});

test('Esc exits pointer lock without sending Escape to the game',()=>{
  const b=browser(),ws=b.submit();b.context.document.pointerLockElement=b.get('screen');
  b.get('screen').onkeydown({code:'Escape'});
  assert.equal(b.context.document.pointerLockElement,null);
  assert.equal(ws.sent.at(-1).action,'release');
});

test('late pointer lock after disconnect immediately releases the browser mouse',()=>{
  const b=browser();b.submit();b.run('cleanup()');
  b.context.document.pointerLockElement=b.get('screen');b.documentHandlers.pointerlockchange();
  assert.equal(b.context.document.pointerLockElement,null);
});

test('backtick toggles game mouse both ways without interrupting held walking keys',async()=>{
  const b=browser(),ws=b.submit(),screen=b.get('screen');b.run('relativeMouseAvailable=true');
  let locks=0;
  screen.requestPointerLock=async()=>{locks++;b.context.document.pointerLockElement=screen;b.documentHandlers.pointerlockchange();};
  screen.onkeydown({code:'KeyW',preventDefault(){}});
  await screen.onkeydown({code:'Backquote',repeat:false,preventDefault(){}});
  screen.onkeydown({code:'Backquote',repeat:true,preventDefault(){}});
  screen.onkeyup({code:'Backquote',preventDefault(){}});
  assert.equal(locks,1);assert.equal(b.run("held.has('KeyW')"),true);
  assert.equal(ws.sent.at(-1).action,'pointer-lock');assert.equal(ws.sent.at(-1).preserveKeys,true);
  await screen.onkeydown({code:'Backquote',preventDefault(){}});b.documentHandlers.pointerlockchange();
  assert.equal(ws.sent.at(-1).enabled,false);assert.equal(ws.sent.at(-1).preserveKeys,true);
  assert.equal(b.run("held.has('KeyW')"),true);
  assert.equal(ws.sent.some(m=>m.action==='release'||m.code==='Backquote'||m.down===false),false);
  screen.onkeyup({code:'KeyW',preventDefault(){}});
  assert.equal(ws.sent.at(-1).code,'KeyW');assert.equal(ws.sent.at(-1).down,false);
});

test('failed game mouse request preserves walking; actual blur releases everything',async()=>{
  const b=browser(),ws=b.submit(),screen=b.get('screen');b.run('relativeMouseAvailable=true');
  screen.requestPointerLock=async()=>{throw new Error('denied');};
  screen.onkeydown({code:'KeyW',preventDefault(){}});
  await screen.onkeydown({code:'Backquote',preventDefault(){}});
  assert.equal(b.run("held.has('KeyW')"),true);assert.equal(ws.sent.length,1);
  screen.onblur();assert.equal(b.run('held.size'),0);assert.equal(ws.sent.at(-1).action,'release');
});

test('a late mouse lock cannot refocus the game after switching away',()=>{
  const b=browser(),ws=b.submit();b.run('relativeMouseAvailable=true');
  b.context.document.hasFocus=()=>false;
  b.context.document.pointerLockElement=b.get('screen');b.documentHandlers.pointerlockchange();
  assert.equal(b.context.document.pointerLockElement,null);
  assert.equal(ws.sent.some(m=>m.action==='pointer-lock'),false);
});
