const $ = id => document.getElementById(id);
let ws, pc, channel, frameURL, generation=0, gotFrame=false;
let useRTC=false, lastMove=0, statsTimer;
const held=new Set();
const status=text=>{$('status').textContent=text;};
const signal=msg=>{if(ws?.readyState===WebSocket.OPEN)ws.send(JSON.stringify(msg));};
function control(msg){
  const data=JSON.stringify(msg);
  if(useRTC && channel?.readyState==='open' && channel.bufferedAmount<16000)channel.send(data);
  else signal(msg);
}
function release(){held.clear();control({type:'input',action:'release'});}
function closeRTC(){if(pc){pc.close();pc=null;}channel=null;useRTC=false;$('video').srcObject=null;$('video').hidden=true;}
function chooseMode(){
  useRTC=!$('relay').checked && pc?.connectionState==='connected' && $('video').readyState>=2;
  signal({type:'mode',rtc:useRTC});
  $('video').hidden=!useRTC;$('frame').hidden=useRTC||!gotFrame;
  $('mode-label').textContent=useRTC?'Direct / WebRTC video':'Compatibility relay';
  if(gotFrame||useRTC)$('placeholder').hidden=true;
  if(useRTC)status('Connected · click the screen to use your Mac');
  else if(gotFrame)status('Connected through Codespaces relay · click the screen to use your Mac');
}
async function offer(msg){
  const current=generation;
  closeRTC();
  const peer=new RTCPeerConnection({iceServers:msg.iceServers||[]});pc=peer;
  peer.ondatachannel=e=>{channel=e.channel;channel.onmessage=e=>{try{receive(JSON.parse(e.data));}catch{}};};
  peer.ontrack=e=>{$('video').srcObject=new MediaStream([e.track]);$('video').play().catch(()=>{});};
  peer.onconnectionstatechange=()=>{if(peer===pc)chooseMode();};
  try{
    await peer.setRemoteDescription({type:'offer',sdp:msg.sdp});
    await peer.setLocalDescription(await peer.createAnswer());
    if(peer.iceGatheringState!=='complete')await new Promise(resolve=>{
      const timer=setTimeout(resolve,7000);
      peer.addEventListener('icegatheringstatechange',()=>{if(peer.iceGatheringState==='complete'){clearTimeout(timer);resolve();}});
    });
    if(generation===current && pc===peer)signal({type:'answer',sdp:peer.localDescription.sdp});
  }catch{if(generation===current)status('Direct connection unavailable. Using compatibility relay.');}
}
function receive(msg){
  if(msg.type==='authenticated'){status('Waiting for your Mac…');$('connection').textContent='Connected to Codespaces';}
  if(msg.type==='host-ready'){status('Mac found. Connecting…');}
  if(msg.type==='offer')offer(msg);
  if(msg.type==='status')status(msg.text);
  if(msg.type==='pong')$('latency').textContent=`${Math.max(0,Math.round(performance.now()-msg.at))} ms control round trip`;
  if(msg.type==='peer-left'){
    release();closeRTC();generation++;gotFrame=false;
    $('frame').hidden=true;$('placeholder').hidden=false;$('mode-label').textContent='Mac offline';
    $('latency').textContent='';status('Mac disconnected. Reopen the Mac host to reconnect.');
  }
}
$('video').addEventListener('loadeddata',chooseMode);
$('relay').addEventListener('change',()=>{release();chooseMode();});
$('connect-form').addEventListener('submit',event=>{
  event.preventDefault();if(ws)return;
  const key=$('key').value.trim();if(!key)return;
  ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);
  ++generation;
  const socket=ws;
  ws.onopen=()=>{signal({type:'auth',role:'viewer',key});$('key').value='';};
  ws.onmessage=async event=>{
    if(typeof event.data==='string'){try{receive(JSON.parse(event.data));}catch{}return;}
    if(socket!==ws)return;
    const next=URL.createObjectURL(event.data);
    const previous=frameURL;frameURL=next;
    $('frame').onload=()=>{
      if(previous)URL.revokeObjectURL(previous);
      if(socket!==ws)return;
      if(!gotFrame&&!useRTC)status('Connected through Codespaces relay · trying direct video');
      gotFrame=true;$('frame').hidden=useRTC;$('placeholder').hidden=true;
      if(!useRTC)$('mode-label').textContent='Compatibility relay';
      signal({type:'frame-ack'});
    };
    $('frame').onerror=()=>{signal({type:'frame-ack'});};
    $('frame').src=next;
  };
  ws.onclose=event=>{
    const reason=event.reason||'Connection closed. Check that your Codespace is running.';
    cleanup();$('connection').textContent=reason;
  };
  ws.onerror=()=>{$('connection').textContent='Could not connect. Check port 3000 and try again.';};
  $('intro').hidden=true;$('login').hidden=true;$('notes').hidden=true;$('desktop').hidden=false;
  document.body.classList.add('connected');
  statsTimer=setInterval(()=>control({type:'ping',at:performance.now()}),2000);
});
function cleanup(){
  generation++;clearInterval(statsTimer);closeRTC();ws=null;held.clear();gotFrame=false;
  if(frameURL){URL.revokeObjectURL(frameURL);frameURL=null;}
  $('frame').removeAttribute('src');$('frame').hidden=true;$('placeholder').hidden=false;
  $('latency').textContent='';$('mode-label').textContent='Waiting for Mac';
  $('intro').hidden=false;$('login').hidden=false;$('notes').hidden=false;$('desktop').hidden=true;
  document.body.classList.remove('connected');
}
$('disconnect').onclick=()=>{release();ws?.close(1000,'Disconnected');};
$('fullscreen').onclick=()=>{$('screen').requestFullscreen().catch(()=>status('Full screen is unavailable in this browser.'));};
$('escape').onclick=()=>control({type:'input',action:'tap',code:'Escape'});
$('cmd-tab').onclick=()=>control({type:'input',action:'shortcut',code:'Tab'});
$('map-ctrl').onchange=release;
function position(e){
  const rect=$('screen').getBoundingClientRect();
  const media=useRTC?$('video'):$('frame');
  const width=media.videoWidth||media.naturalWidth, height=media.videoHeight||media.naturalHeight;
  if(!width||!height)return null;
  const scale=Math.min(rect.width/width,rect.height/height);
  const x=(e.clientX-rect.left-(rect.width-width*scale)/2)/(width*scale);
  const y=(e.clientY-rect.top-(rect.height-height*scale)/2)/(height*scale);
  return {x:Math.max(0,Math.min(1,x)),y:Math.max(0,Math.min(1,y))};
}
const screen=$('screen');
screen.oncontextmenu=e=>e.preventDefault();
screen.onpointerdown=e=>{const pos=position(e);if(!pos)return;e.preventDefault();screen.focus();screen.setPointerCapture(e.pointerId);control({type:'input',action:'down',button:e.button,...pos});};
screen.onpointerup=e=>{const pos=position(e);if(pos)control({type:'input',action:'up',button:e.button,...pos});if(screen.hasPointerCapture(e.pointerId))screen.releasePointerCapture(e.pointerId);};
screen.onpointercancel=release;
screen.onpointermove=e=>{if(performance.now()-lastMove<16)return;const pos=position(e);if(pos){lastMove=performance.now();control({type:'input',action:'move',...pos});}};
screen.addEventListener('wheel',e=>{e.preventDefault();control({type:'input',action:'scroll',dy:e.deltaY*(e.deltaMode===1?16:1),dx:e.deltaX*(e.deltaMode===1?16:1)});},{passive:false});
const mapped=code=>$('map-ctrl').checked&&code.startsWith('Control')?code.replace('Control','Meta'):code;
screen.onkeydown=e=>{if(e.code==='Escape'&&document.fullscreenElement)return;e.preventDefault();const code=mapped(e.code);held.add(code);control({type:'input',action:'key',code,down:true});};
screen.onkeyup=e=>{e.preventDefault();const code=mapped(e.code);held.delete(code);control({type:'input',action:'key',code,down:false});};
screen.onblur=release;window.addEventListener('blur',release);
document.addEventListener('visibilitychange',()=>{if(document.hidden)release();});
