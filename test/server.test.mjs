import {test} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {WebSocket} from 'ws';
import {createDesktopServer} from '../server.mjs';

async function fixture(t, options={}){
  const app=createDesktopServer({hostKey:'h'.repeat(43),viewerKey:'v'.repeat(43),iceServers:[],...options});
  app.server.listen(0,'127.0.0.1');await once(app.server,'listening');
  const base=`http://127.0.0.1:${app.server.address().port}`;
  t.after(()=>app.close());
  const client=async(role,key)=>{
    const ws=new WebSocket(base.replace('http','ws')+'/ws');
    const messages=[];ws.on('message',(data,binary)=>messages.push(binary?data:JSON.parse(data)));
    await once(ws,'open');
    ws.send(JSON.stringify({type:'auth',role,key:key||(role==='host'?'h':'v').repeat(43)}));
    return {ws,messages};
  };
  return {base,client};
}
async function until(fn){for(let n=0;n<100;n++){if(fn())return;await new Promise(r=>setTimeout(r,10));}assert.fail('Timed out waiting for protocol event');}

test('keys, secrets and unknown paths never appear in HTTP responses',async t=>{
  const {base}=await fixture(t);
  for(const path of ['/.secrets.json','/../server.mjs','/mac/host.py'])assert.equal((await fetch(base+path)).status,404);
  const page=await fetch(base);assert.equal(page.status,200);
  assert.match(page.headers.get('content-security-policy'),/frame-ancestors 'self'/);
  assert.ok(!(await page.text()).includes('h'.repeat(43)));
});
test('wrong keys rejected, roles separated, duplicate peer cannot take over',async t=>{
  const {client}=await fixture(t);
  const bad=await client('viewer','h'.repeat(43));
  assert.equal((await once(bad.ws,'close'))[0],4003);
  const host=await client('host');await until(()=>host.messages.some(m=>m.type==='authenticated'));
  const duplicate=await client('host');assert.equal((await once(duplicate.ws,'close'))[0],4009);
  assert.equal(host.ws.readyState,WebSocket.OPEN);
});
test('only paired authenticated peers exchange video and controls; disconnect is delivered',async t=>{
  const {client}=await fixture(t);
  const host=await client('host');const viewer=await client('viewer');
  await until(()=>host.messages.some(m=>m.type==='viewer-ready'));
  host.ws.send(Buffer.from([255,216,255,217]));
  await until(()=>viewer.messages.some(m=>Buffer.isBuffer(m)));
  viewer.ws.send(JSON.stringify({type:'input',action:'release'}));
  await until(()=>host.messages.some(m=>m.type==='input'));
  viewer.ws.send(JSON.stringify({type:'offer',sdp:'forged'}));
  viewer.ws.close();await until(()=>host.messages.some(m=>m.type==='peer-left'));
  assert.ok(!host.messages.some(m=>m.sdp==='forged'));
});
test('cross-origin socket rejected',async t=>{
  const {base}=await fixture(t);
  const ws=new WebSocket(base.replace('http','ws')+'/ws',{origin:'https://evil.example'});
  const [error]=await once(ws,'error');assert.match(error.message,/403/);
});

test('clipboard requests and replies flow only in their allowed authenticated direction',async t=>{
  const {client}=await fixture(t);
  const host=await client('host'),viewer=await client('viewer');
  await until(()=>host.messages.some(m=>m.type==='viewer-ready'));
  viewer.ws.send(JSON.stringify({type:'clipboard',action:'write',request:1,text:'Hello'}));
  await until(()=>host.messages.some(m=>m.type==='clipboard' && m.text==='Hello'));
  host.ws.send(JSON.stringify({type:'clipboard-result',request:1,ok:true}));
  await until(()=>viewer.messages.some(m=>m.type==='clipboard-result'));
  viewer.ws.send(JSON.stringify({type:'clipboard-result',request:99,ok:true}));
  viewer.ws.send(JSON.stringify({type:'ping',at:99}));
  await until(()=>host.messages.some(m=>m.type==='ping' && m.at===99));
  assert.equal(host.messages.some(m=>m.type==='clipboard-result'),false);
});

test('a queued JPEG does not close the viewer when a pong follows it', async t=>{
  const {client}=await fixture(t);
  const host=await client('host');const viewer=await client('viewer');
  await until(()=>host.messages.some(m=>m.type==='viewer-ready'));
  // Model a JPEG still in the server transport queue on a slow network.
  const original=Object.getOwnPropertyDescriptor(WebSocket.prototype,'bufferedAmount');
  Object.defineProperty(WebSocket.prototype,'bufferedAmount',{configurable:true,get(){return 512*1024;}});
  try {
    host.ws.send(JSON.stringify({type:'pong',at:42}));
    await until(()=>viewer.messages.some(m=>m.type==='pong') || viewer.ws.readyState===WebSocket.CLOSED);
    assert.equal(viewer.ws.readyState,WebSocket.OPEN);
    assert.ok(viewer.messages.some(m=>m.type==='pong' && m.at===42));
  } finally {Object.defineProperty(WebSocket.prototype,'bufferedAmount',original);}
});

test('health endpoint identifies the deployed version without exposing credentials',async t=>{
  const {base}=await fixture(t);
  assert.deepEqual(await (await fetch(base+'/health')).json(),{app:'codespace-desktop',version:'0.2.8'});
});


test('Codespaces rewritten origin works only through the expected local tunnel',async t=>{
  const origin='https://example-3000.app.github.dev';
  const {base}=await fixture(t,{publicOrigin:origin,codespacesPort:3000});
  const headers={Host:'localhost:3000','X-Forwarded-Host':'example-3000.app.github.dev'};
  for(const protocol of ['http','https']){
    const ws=new WebSocket(base.replace('http','ws')+'/ws',{origin:`${protocol}://localhost:3000`,headers});
    await once(ws,'open');
    const received=once(ws,'message');
    ws.send(JSON.stringify({type:'auth',role:'viewer',key:'v'.repeat(43)}));
    assert.equal(JSON.parse((await received)[0]).type,'authenticated');
    ws.close();await once(ws,'close');
  }
  for (const settings of [
    {origin:'https://evil.example',headers},
    {origin:'http://localhost:3001',headers},
    {origin:'http://localhost:3000',headers:{...headers,'X-Forwarded-Host':'evil.example'}},
    {origin:'http://localhost:3000',headers:{Host:'localhost:3000'}},
    {origin:'http://example-3000.app.github.dev',headers},
    {origin:'https://localhost:3001',headers},
    {origin:'https://localhost:3000',headers:{...headers,'X-Forwarded-Host':'evil.example'}},
    {origin:'https://localhost:3000',headers:{Host:'localhost:3000'}},
    {origin:'https://localhost:3000',headers:{...headers,Host:'localhost:3001'}},
    {origin:'ftp://localhost:3000',headers},
    {origin:'[https://localhost:3000](https://localhost:3000)',headers},
  ]) {
    const bad=new WebSocket(base.replace('http','ws')+'/ws',settings);
    const [error]=await once(bad,'error');assert.match(error.message,/403/);
  }
});

test('localhost rewrite is rejected when Codespaces proxy support is not configured',async t=>{
  const {base}=await fixture(t,{publicOrigin:'https://example-3000.app.github.dev'});
  for(const protocol of ['http','https']){
    const ws=new WebSocket(base.replace('http','ws')+'/ws',{origin:`${protocol}://localhost:3000`,headers:{Host:'localhost:3000','X-Forwarded-Host':'example-3000.app.github.dev'}});
    const [error]=await once(ws,'error');assert.match(error.message,/403/);
  }
});
