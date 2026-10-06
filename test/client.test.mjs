import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

function browser(){
  const nodes=new Map();
  const get=id=>{
    if(!nodes.has(id))nodes.set(id,{hidden:['desktop','connection-error'].includes(id),value:'',textContent:'',handlers:{},
      addEventListener(type,fn){this.handlers[type]=fn;},removeAttribute(){},checked:false});
    return nodes.get(id);
  };
  class Socket {
    static OPEN=1;
    constructor(){this.readyState=1;this.sent=[];Socket.latest=this;}
    send(data){this.sent.push(JSON.parse(data));}
    close(code,reason){this.readyState=3;this.onclose({code,reason});}
  }
  const context={document:{getElementById:get,body:{classList:{add(){},remove(){}}},addEventListener(){}},
    window:{addEventListener(){}},location:{protocol:'https:',host:'example.test'},WebSocket:Socket,
    performance:{now:()=>100},setInterval:()=>1,clearInterval(){},setTimeout:()=>1,clearTimeout(){}};
  vm.runInNewContext(readFileSync(new URL('../public/client.js',import.meta.url),'utf8'),context);
  return {get,Socket,submit(){get('key').value='viewer-test-key';get('connect-form').handlers.submit({preventDefault(){}});return Socket.latest;}};
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

test('successful login clears key; later network failure remains visible',()=>{
  const b=browser(),ws=b.submit();ws.onopen();
  ws.onmessage({data:JSON.stringify({type:'authenticated',version:'0.1.1'})});
  assert.equal(b.get('login').hidden,true);
  assert.equal(b.get('desktop').hidden,false);
  assert.equal(b.get('key').value,'');
  ws.close(1006,'');
  assert.equal(b.get('login').hidden,false);
  assert.match(b.get('connection-error').textContent,/1006/);
  assert.match(b.get('details-log').textContent,/key accepted/);
  assert.ok(!b.get('details-log').textContent.includes('viewer-test-key'));
});
