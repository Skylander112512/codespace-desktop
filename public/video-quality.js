// Only explicitly selected HD modes ask the browser for a higher receive level.
// MediaCapabilities' WebRTC query checks the actual decoder configuration.
export async function receiveQuality(sdp, mode, capabilities=globalThis.navigator?.mediaCapabilities) {
  const preset = {'720p60': [1280,720,60,32,6_000_000], '1080p60': [1920,1080,60,42,10_000_000]}[mode];
  if (!preset || !capabilities?.decodingInfo) return sdp;
  const [width,height,framerate,level,bitrate] = preset;
  const hex=level.toString(16);
  try {
    const info=await capabilities.decodingInfo({type:'webrtc',video:{
      contentType:`video/H264;level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42e0${hex}`,
      width,height,bitrate,framerate}});
    if (!info.supported) return sdp;
    // RFC 6184: explicitly declare a receive limit above the default level.
    return sdp.replace(/^a=fmtp:\d+ .*$/gm,line=>{
      const profile=line.match(/profile-level-id=42[ce]0([0-9a-f]{2})/i);
      if (!profile || parseInt(profile[1],16)>=level) return line;
      return line.replace(/;?max-recv-level=[^;\s]+/ig,'').trimEnd()+`;max-recv-level=e0${hex}`+(line.endsWith('\r')?'\r':'');
    });
  } catch { return sdp; }
}
