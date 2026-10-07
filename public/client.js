import {receiveQuality} from './video-quality.js';
const $ = id => document.getElementById(id);
let ws, pc, channel, motionChannel, frameURL, generation=0, gotFrame=false;
let useRTC=false, statsTimer, connectTimer;
let lastVideoAt=0, previousStats, polling=false, nativeStats={};
let inputSequence=0, lastReliable=0, pendingMotion=null, motionTimer;
const events=[];
function detail(text){
  events.push(`${new Date().toLocaleTimeString()} · ${text}`);
  if(events.length>30)events.shift();
  $('details-log').textContent=events.join('\n');
}
function connectionError(text){
  $('connection-error').textContent=text;
  $('connection-error').hidden=false;
  detail(text);
}
const held=new Set();
const status=text=>{$('status').textContent=text;};
const signal=msg=>{if(ws?.readyState===WebSocket.OPEN)ws.send(JSON.stringify(msg));};
function control(msg){
  if(msg.type==='input'){
    msg={...msg,seq:++inputSequence};
    if(msg.action==='move')msg.after=lastReliable;
    else {lastReliable=msg.seq;pendingMotion=null;clearTimeout(motionTimer);motionTimer=null;}
  }
  const data=JSON.stringify(msg);
  if(useRTC && channel?.readyState==='open'){
    if(msg.action==='move' && motionChannel?.readyState==='open'){
      if(motionChannel.bufferedAmount<2048)motionChannel.send(data);
      return; // Stale movement is disposable; clicks and keys remain reliable.
    }
    if(channel.bufferedAmount<128000){channel.send(data);return;}
    channel.close(); // Bound the queue; release keys before changing transport.
    if(msg.type==='input'){
      signal({type:'input',action:'release',seq:++inputSequence});lastReliable=inputSequence;
      return;
    }
  }
  if(msg.action==='move' && ws?.bufferedAmount>16000)return;
  signal(msg);
}
function release(){held.clear();control({type:'input',action:'release'});}
function closeRTC(){if(pc){pc.close();pc=null;}channel=null;motionChannel=null;useRTC=false;$('video').srcObject=null;$('video').hidden=true;lastVideoAt=0;previousStats=null;nativeStats={};$('performance').textContent='';}
async function sampleStats(){
  const peer=pc;
  if(!peer || polling)return;
  polling=true;
  try{
    const reports=await peer.getStats();
    if(peer!==pc)return;
    let inbound, pair;
    reports.forEach(report=>{
      if(report.type==='inbound-rtp' && report.kind==='video')inbound=report;
      if(report.type==='transport' && report.selectedCandidatePairId)pair=reports.get(report.selectedCandidatePairId);
    });
    if(!pair)reports.forEach(report=>{if(report.type==='candidate-pair' && report.state==='succeeded' && report.nominated)pair=report;});
    if(!inbound)return;
    const prior=previousStats;
    previousStats=inbound;
    if(!prior || prior.id!==inbound.id)return;
    const frames=inbound.framesDecoded-prior.framesDecoded;
    if(frames>0)lastVideoAt=performance.now();
    const elapsed=(inbound.timestamp-prior.timestamp)/1000;
    if(elapsed<=0 || frames<0)return;
    const delta=key=>Math.max(0,(inbound[key]||0)-(prior[key]||0));
    const packets=delta('packetsReceived'), lost=delta('packetsLost');
    const fps=frames/elapsed;
    const decode=frames?delta('totalDecodeTime')*1000/frames:0;
    const emitted=delta('jitterBufferEmittedCount');
    const buffer=emitted?delta('jitterBufferDelay')*1000/emitted:0;
    const route=pair && [reports.get(pair.localCandidateId),reports.get(pair.remoteCandidateId)].some(c=>c?.candidateType==='relay')?'TURN relay':'Peer connection';
    const codec=reports.get(inbound.codecId)?.mimeType?.split('/')[1]||'video';
    const encode=Number.isFinite(nativeStats.encode_ms)?` · ${Math.round(nativeStats.encode_ms)} ms encode`:'';
    $('performance').textContent=useRTC?`${Math.round(fps)} FPS · ${inbound.frameWidth||'?'}×${inbound.frameHeight||'?'} · ${codec} · ${route}${encode} · ${Math.round(decode)} ms decode · ${Math.round(buffer)} ms video buffer`:'Compatibility relay · up to 15 FPS';
    // Avoid interpreting an idle screen as a decoder/bandwidth problem.
    if(frames>0 && useRTC && !document.hidden)control({type:'feedback',fps,loss:lost/Math.max(1,packets+lost),decode_ms:decode,buffer_ms:buffer});
  }catch{ /* Stats are optional; video and input continue on older browsers. */ }
  finally{polling=false;}
}
function chooseMode(){
  const previous=useRTC;
  useRTC=Boolean(!$('relay').checked && pc?.connectionState==='connected' && $('video').readyState>=2 && performance.now()-lastVideoAt<2500);
  if(previous!==useRTC){release();detail(useRTC?'Direct video is playing.':'Using compatibility relay.');}
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
  peer.ondatachannel=e=>{
    if(e.channel.label==='motion'){motionChannel=e.channel;return;}
    if(e.channel.label!=='control')return;
    channel=e.channel;channel.onmessage=e=>{try{receive(JSON.parse(e.data));}catch{}};
  };
  peer.ontrack=e=>{
    try{if('jitterBufferTarget' in e.receiver)e.receiver.jitterBufferTarget=0;
      else if('playoutDelayHint' in e.receiver)e.receiver.playoutDelayHint=0;}catch{}
    $('video').srcObject=new MediaStream([e.track]);$('video').play().catch(()=>detail('Browser could not play direct video; relay remains available.'));};
  peer.onconnectionstatechange=()=>{if(peer===pc){detail(`Direct video: ${peer.connectionState}`);chooseMode();}};
  try{
    await peer.setRemoteDescription({type:'offer',sdp:msg.sdp});
    const quality=$('quality').value||'smooth';
    const answer=await peer.createAnswer();
    answer.sdp=await receiveQuality(answer.sdp,quality);
    if(generation!==current || pc!==peer)return;
    await peer.setLocalDescription(answer);
    if(peer.iceGatheringState!=='complete')await new Promise(resolve=>{
      const timer=setTimeout(resolve,7000);
      peer.addEventListener('icegatheringstatechange',()=>{if(peer.iceGatheringState==='complete'){clearTimeout(timer);resolve();}});
    });
    if(generation===current && pc===peer)signal({type:'answer',sdp:peer.localDescription.sdp,inputProtocol:2,quality});
  }catch(error){if(generation===current){detail(`Direct connection unavailable (${error.name}); using relay.`);status('Direct connection unavailable. Using compatibility relay.');}}
}
function receive(msg){
  if(msg.type==='authenticated'){
    clearTimeout(connectTimer);$('key').value='';
    $('intro').hidden=true;$('login').hidden=true;$('notes').hidden=true;$('desktop').hidden=false;
    document.body.classList.add('connected');
    status('Waiting for your Mac…');$('connection').textContent='Connected to Codespaces';
    detail(`Connection code accepted. Server ${msg.version||'0.1.0'}; waiting for Mac.`);
    statsTimer=setInterval(async()=>{
      await sampleStats();chooseMode();control({type:'ping',at:performance.now()});
    },1000);
  }
  if(msg.type==='host-ready'){status('Mac found. Connecting…');detail('Mac authenticated. Waiting for its first screen frame.');}
  if(msg.type==='offer')offer(msg);
  if(msg.type==='performance')nativeStats=msg;
  if(msg.type==='status'){status(msg.text);detail(msg.text);}
  if(msg.type==='pong')$('latency').textContent=`${Math.max(0,Math.round(performance.now()-msg.at))} ms control round trip`;
  if(msg.type==='peer-left'){
    detail('Mac disconnected; the viewer remains connected to Codespaces.');
    release();closeRTC();generation++;gotFrame=false;
    $('frame').hidden=true;$('placeholder').hidden=false;$('mode-label').textContent='Mac offline';
    $('latency').textContent='';status('Mac disconnected. Reopen the Mac host to reconnect.');
  }
}
$('video').addEventListener('loadeddata',()=>{lastVideoAt=performance.now();chooseMode();});
$('quality').addEventListener('change',()=>{release();signal({type:'quality'});});
$('relay').addEventListener('change',()=>{release();chooseMode();});
$('connect-form').addEventListener('submit',event=>{
  event.preventDefault();if(ws)return;
  const key=$('key').value.trim();if(!key)return;
  $('connection-error').hidden=true;$('connect-button').disabled=true;
  $('connection').textContent='Connecting…';detail('Opening secure connection to Codespaces…');
  ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);
  ++generation;
  const socket=ws;
  ws.onopen=()=>{if(socket!==ws)return;detail('Socket open. Checking connection code…');signal({type:'auth',role:'viewer',key});};
  connectTimer=setTimeout(()=>{if(socket===ws){connectionError('Connection timed out. Check npm start and port 3000 in Codespaces.');socket.close(4000,'Connection timed out');}},12000);
  ws.onmessage=async event=>{
    if(socket!==ws)return;
    if(typeof event.data==='string'){try{receive(JSON.parse(event.data));}catch{detail('Server sent an unreadable message.');}return;}
    const next=URL.createObjectURL(new Blob([event.data],{type:'image/jpeg'}));
    const previous=frameURL;frameURL=next;
    $('frame').onload=()=>{
      if(previous)URL.revokeObjectURL(previous);
      if(socket!==ws)return;
      if(!gotFrame){detail('First screen frame displayed.');if(!useRTC)status('Connected through Codespaces relay · trying direct video');}
      gotFrame=true;$('frame').hidden=useRTC;$('placeholder').hidden=true;
      if(!useRTC)$('mode-label').textContent='Compatibility relay';
      signal({type:'frame-ack'});
    };
    $('frame').onerror=()=>{if(previous)URL.revokeObjectURL(previous);if(socket!==ws)return;detail('A screen frame could not be displayed; requesting the next frame.');signal({type:'frame-ack'});};
    $('frame').src=next;
  };
  ws.onclose=event=>{
    if(socket!==ws)return;
    const reason=event.reason||'Network connection lost. Check npm start and that port 3000 is Public.';
    cleanup();$('connection').textContent='Disconnected';
    if(event.code===1000)detail('Disconnected.');
    else connectionError(`Disconnected (${event.code}): ${reason}`);
  };
  ws.onerror=()=>{if(socket===ws)connectionError('Could not reach the server. Check npm start, port 3000 → Public, and open its HTTPS address in a full browser tab.');};
});
function cleanup(){
  generation++;pendingMotion=null;clearTimeout(motionTimer);motionTimer=null;clearInterval(statsTimer);clearTimeout(connectTimer);$('connect-button').disabled=false;closeRTC();ws=null;held.clear();gotFrame=false;
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
screen.onpointermove=e=>{
  const pos=position(e);if(!pos)return;pendingMotion=pos;
  if(motionTimer)return;
  motionTimer=setTimeout(()=>{motionTimer=null;const latest=pendingMotion;pendingMotion=null;
    if(latest)control({type:'input',action:'move',...latest});},8);
};
screen.addEventListener('wheel',e=>{e.preventDefault();control({type:'input',action:'scroll',dy:e.deltaY*(e.deltaMode===1?16:1),dx:e.deltaX*(e.deltaMode===1?16:1)});},{passive:false});
const mapped=code=>$('map-ctrl').checked&&code.startsWith('Control')?code.replace('Control','Meta'):code;
screen.onkeydown=e=>{if(e.code==='Escape'&&document.fullscreenElement)return;e.preventDefault();const code=mapped(e.code);held.add(code);control({type:'input',action:'key',code,down:true});};
screen.onkeyup=e=>{e.preventDefault();const code=mapped(e.code);held.delete(code);control({type:'input',action:'key',code,down:false});};
screen.onblur=release;window.addEventListener('blur',release);
document.addEventListener('visibilitychange',()=>{if(document.hidden)release();});
