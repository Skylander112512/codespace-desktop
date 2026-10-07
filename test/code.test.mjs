import {test} from 'node:test';
import assert from 'node:assert/strict';
import {hashViewerCode,verifyViewerCode} from '../viewer-code.mjs';
import {createDesktopServer} from '../server.mjs';
import WebSocket from 'ws';

test('viewer codes use salted hashes and do not authenticate as Mac hosts',async()=>{
  const code='94726'; // Synthetic fixture, never a user's code.
  const record=await hashViewerCode(code);
  assert.notEqual(record.hash,(await hashViewerCode(code)).hash);
  assert.equal(await verifyViewerCode(code,record),true);
  assert.equal(await verifyViewerCode('94725',record),false);
  await assert.rejects(hashViewerCode('1234'));
  const app=createDesktopServer({hostKey:'host-private-test-key',viewerKey:'viewer-private-test-key',viewerCode:record});
  await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve));
  const url=`ws://127.0.0.1:${app.server.address().port}/ws`;
  const auth=(role,key)=>new Promise((resolve,reject)=>{
    const ws=new WebSocket(url);
    ws.on('error',reject);
    ws.on('open',()=>ws.send(JSON.stringify({type:'auth',role,key})));
    ws.on('message',raw=>{const message=JSON.parse(raw);if(message.type==='authenticated'){resolve(message);ws.close();}});
    ws.on('close',code=>resolve({close:code}));
  });
  try{
    assert.equal((await auth('host',code)).close,4003);
    // Wrong guesses never lock out the correct code, as requested.
    for(let i=0;i<65;i++)assert.equal((await auth('viewer','94725')).close,4003);
    assert.equal((await auth('viewer',code)).role,'viewer');
  }finally{await app.close();}
});
