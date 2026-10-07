import test from 'node:test';
import assert from 'node:assert/strict';
import {receiveQuality} from '../public/video-quality.js';
const sdp='m=video 9 UDP/TLS/RTP/SAVPF 99\r\na=rtpmap:99 H264/90000\r\na=fmtp:99 level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42e01f\r\n';
test('HD receive level is advertised only after a successful decoder capability check',async()=>{
  let config;
  const supported={decodingInfo:async c=>{config=c;return {supported:true};}};
  const answer=await receiveQuality(sdp,'1080p60',supported);
  assert.match(answer,/max-recv-level=e02a\r\n/);
  assert.equal(config.video.width,1920);assert.equal(config.video.framerate,60);
  assert.match(await receiveQuality(sdp,'720p60',supported),/max-recv-level=e020/);
  assert.equal(await receiveQuality(sdp,'1080p60',{decodingInfo:async()=>({supported:false})}),sdp);
  assert.equal(await receiveQuality(sdp,'1080p60',{decodingInfo:async()=>{throw Error();}}),sdp);
});
test('default Smooth does not probe or increase the receive limit',async()=>{
  assert.equal(await receiveQuality(sdp,'smooth',{decodingInfo:()=>{throw Error('Must not query');}}),sdp);
});
