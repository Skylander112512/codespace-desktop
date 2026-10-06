import {test} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {WebSocket} from 'ws';
import {createDesktopServer} from '../server.mjs';

async function fixture(t){
  const app=createDesktopServer({hostKey:'h'.repeat(43),viewerKey:'v'.repeat(43),iceServers:[]});
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
  assert.match(page.headers.get('content-security-policy'),/frame-ancestors 'none'/);
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
  assert.deepEqual(await (await fetch(base+'/health')).json(),{app:'codespace-desktop',version:'0.1.1'});
});
