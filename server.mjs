import http from 'node:http';
import {verifyViewerCode} from './viewer-code.mjs';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { WebSocketServer, WebSocket } from 'ws';

const root = new URL('./', import.meta.url);
const equal = (a, b) => typeof a === 'string' && Buffer.byteLength(a) === Buffer.byteLength(b) && timingSafeEqual(Buffer.from(a), Buffer.from(b));
const send = (ws, msg) => { if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg)); };

export function createDesktopServer({hostKey, viewerKey, viewerCode, iceServers = [{urls:'stun:stun.l.google.com:19302'}], publicOrigin, codespacesPort, log = () => {}} = {}) {
  if (!hostKey || !viewerKey || hostKey === viewerKey) throw new Error('Distinct host and viewer keys are required.');
  const assets = new Map([
    ['/', ['public/index.html','text/html; charset=utf-8']],
    ['/client.js', ['public/client.js','text/javascript; charset=utf-8']],
    ['/launch.js', ['public/launch.js','text/javascript; charset=utf-8']],
    ['/cloak.css', ['public/cloak.css','text/css; charset=utf-8']],
    ['/cloak-icon.svg', ['public/cloak-icon.svg','image/svg+xml']],
    ['/video-quality.js', ['public/video-quality.js','text/javascript; charset=utf-8']],
    ['/style.css', ['public/style.css','text/css; charset=utf-8']],
  ]);
  const server = http.createServer((req, res) => {
    const headers = {'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer',
      'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'"};
    const asset = assets.get(req.url);
    if (req.method === 'GET' && req.url === '/health') {
      res.writeHead(200, {...headers, 'Content-Type':'application/json'});
      res.end(JSON.stringify({app:'codespace-desktop',version:'0.2.8'})); return;
    }
    if (req.method !== 'GET' || !asset) { res.writeHead(404, headers); res.end('Not found'); return; }
    res.writeHead(200, {...headers, 'Content-Type':asset[1]});
    res.end(readFileSync(new URL(asset[0],root)));
  });
  const wss = new WebSocketServer({noServer:true, maxPayload:2*1024*1024, perMessageDeflate:false});
  const peers = {host:null, viewer:null};
  server.on('upgrade', (req, socket, head) => {
    let valid = req.url === '/ws' && wss.clients.size < 32;
    if (req.headers.origin) {
      // Browser connections must originate from this viewer, never another site.
      try {
        const origin = new URL(req.headers.origin);
        const expected = publicOrigin ? new URL(publicOrigin) : null;
        const direct = expected ? origin.origin === expected.origin : origin.host === req.headers.host;
        // Codespaces can rewrite Origin to either http or https localhost.
        // Only trust that rewrite from the local tunnel, for this exact port,
        // with the configured public hostname in X-Forwarded-Host.
        const loopback = ['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress);
        const localHost = `localhost:${codespacesPort}`;
        const tunnel = Number.isInteger(codespacesPort) && expected && loopback &&
          req.headers.host === localHost &&
          (origin.origin === `http://${localHost}` || origin.origin === `https://${localHost}`) &&
          req.headers['x-forwarded-host'] === expected.host;
        valid &&= direct || tunnel;
      } catch { valid = false; }
    }
    if (!valid) {
      log(`Upgrade rejected: ${JSON.stringify({origin:req.headers.origin,host:req.headers.host,forwardedHost:req.headers['x-forwarded-host'],remote:req.socket.remoteAddress})}`);
      socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n'); return;
    }
    wss.handleUpgrade(req, socket, head, ws => wss.emit('connection', ws));
  });
  wss.on('connection', ws => {
    let role;
    let authenticating=false;
    let alive = true;
    let count = 0;
    let period = Date.now();
    const deadline = setTimeout(() => ws.close(4001,'Authentication required'), 5000);
    ws.on('pong', () => { alive = true; });
    const heartbeat = setInterval(() => { if (!alive) return ws.terminate(); alive = false; ws.ping(); },15000);
    ws.on('error', error => log(`Socket error (${role || 'unauthenticated'}): ${error.code || error.name}`));
    ws.on('message', async (data, binary) => {
      if (Date.now()-period > 1000) { period=Date.now(); count=0; }
      if (++count > 400) { ws.close(4008,'Too many messages'); return; }
      if (binary) {
        if (role !== 'host') { ws.close(4003,'Not allowed'); return; }
        const viewer=peers.viewer;
        if (viewer?.readyState === WebSocket.OPEN && viewer.bufferedAmount < 256*1024) viewer.send(data,{binary:true});
        else send(ws,{type:'frame-ack'}); // Never grow a video queue.
        return;
      }
      if (data.length > 128*1024) { ws.close(4009,'Message too large'); return; }
      let msg;
      try { msg = JSON.parse(data); } catch { ws.close(4002,'Invalid JSON'); return; }
      if (!msg || typeof msg !== 'object') { ws.close(4002,'Invalid message'); return; }
      if (!role) {
        const candidate=msg.role;
        if(authenticating)return;
        authenticating=true;
        let accepted=msg.type==='auth' && ['host','viewer'].includes(candidate) && equal(msg.key,candidate==='host'?hostKey:viewerKey);
        if(!accepted && msg.type==='auth' && candidate==='viewer' && viewerCode){
          try{accepted=await verifyViewerCode(msg.key,viewerCode);}catch{accepted=false;}
        }
        if(ws.readyState!==WebSocket.OPEN)return;
        if(!accepted){ws.close(4003,'Invalid access code or key');return;}
        if (peers[candidate]) { ws.close(4009,`${candidate} already connected`); return; }
        clearTimeout(deadline); role=candidate; peers[role]=ws;
        log(`${role} authenticated`);
        send(ws,{type:'authenticated',role,iceServers,version:'0.2.8'});
        if (peers.host && peers.viewer) {
          send(peers.viewer,{type:'host-ready'});
          send(peers.host,{type:'viewer-ready'});
        } else send(ws,{type:'waiting'});
        return;
      }
      const allow=role==='host'?['offer','status','pong','performance','clipboard-result']:['answer','input','frame-ack','ping','mode','feedback','quality','clipboard'];
      if (!allow.includes(msg.type)) return;
      const other=peers[role==='host'?'viewer':'host'];
      // A single valid JPEG can exceed 256 KiB. Do not disconnect the viewer
      // when a pong or SDP follows that frame on a slower network.
      if (other?.bufferedAmount > 4*1024*1024) { other.close(4008,'Connection stalled; reconnect'); return; }
      send(other,msg);
    });
    ws.on('close', (code) => {
      log(`${role || 'Unauthenticated socket'} disconnected (code ${code})`);
      clearTimeout(deadline); clearInterval(heartbeat);
      if (role && peers[role]===ws) {
        peers[role]=null;
        send(peers[role==='host'?'viewer':'host'],{type:'peer-left'});
      }
    });
  });
  return {server, close:async () => {
    for (const ws of wss.clients) ws.terminate();
    await new Promise(resolve => wss.close(resolve));
    if (server.listening) await new Promise(resolve => server.close(resolve));
  }};
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const secretFile = new URL('.secrets.json', root);
  if (!existsSync(secretFile)) writeFileSync(secretFile,JSON.stringify({hostKey:randomBytes(32).toString('base64url'), viewerKey:randomBytes(32).toString('base64url')}),{mode:0o600,flag:'wx'});
  const keys=JSON.parse(readFileSync(secretFile,'utf8'));
  const port=Number(process.env.PORT || 3000);
  const origin=process.env.PUBLIC_URL || (process.env.CODESPACE_NAME ? `https://${process.env.CODESPACE_NAME}-${port}.${process.env.GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN || 'app.github.dev'}` : `http://localhost:${port}`);
  const iceServers=process.env.ICE_SERVERS_JSON ? JSON.parse(process.env.ICE_SERVERS_JSON) : undefined;
  const app=createDesktopServer({...keys,iceServers,publicOrigin:origin,codespacesPort:process.env.CODESPACE_NAME ? port : undefined,log:message=>console.log(new Date().toISOString(),message)});
  app.server.listen(port,'0.0.0.0',() => {
    console.log(`\nCodespace Desktop\nViewer: ${origin}\n\n${keys.viewerCode?'Chromebook: enter your saved code.':'Viewer key: '+keys.viewerKey}\nMac host key: ${keys.hostKey}\n\nKeep your code and keys private. They are NOT GitHub tokens.\nIn Codespaces: Ports → 3000 → Port Visibility → Public.\nThe public viewer page requires its access key; the Mac uses a separate key.\nStop with Ctrl+C.\n`);
  });
  for (const signal of ['SIGINT','SIGTERM']) process.on(signal, async () => { await app.close(); process.exit(0); });
}
