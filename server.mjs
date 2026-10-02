import http from 'node:http';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { WebSocketServer, WebSocket } from 'ws';

const root = new URL('./', import.meta.url);
const equal = (a, b) => typeof a === 'string' && Buffer.byteLength(a) === Buffer.byteLength(b) && timingSafeEqual(Buffer.from(a), Buffer.from(b));
const send = (ws, msg) => { if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg)); };

export function createDesktopServer({hostKey, viewerKey, iceServers = [{urls:'stun:stun.l.google.com:19302'}], publicOrigin} = {}) {
  if (!hostKey || !viewerKey || hostKey === viewerKey) throw new Error('Distinct host and viewer keys are required.');
  const assets = new Map([
    ['/', ['public/index.html','text/html; charset=utf-8']],
    ['/client.js', ['public/client.js','text/javascript; charset=utf-8']],
    ['/style.css', ['public/style.css','text/css; charset=utf-8']],
  ]);
  const server = http.createServer((req, res) => {
    const headers = {'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer',
      'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"};
    const asset = assets.get(req.url);
    if (req.method !== 'GET' || !asset) { res.writeHead(404, headers); res.end('Not found'); return; }
    res.writeHead(200, {...headers, 'Content-Type':asset[1]});
    res.end(readFileSync(new URL(asset[0],root)));
  });
  const wss = new WebSocketServer({noServer:true, maxPayload:2*1024*1024, perMessageDeflate:false});
  const peers = {host:null, viewer:null};
  let failures = 0;
  const resetFailures = setInterval(() => { failures = 0; }, 60000);
  resetFailures.unref();
  server.on('upgrade', (req, socket, head) => {
    let valid = req.url === '/ws' && wss.clients.size < 32 && failures < 60;
    if (req.headers.origin) {
      // Browser connections must originate from this viewer, never another site.
      try {
        const expected = publicOrigin ? new URL(publicOrigin).host : req.headers.host;
        valid &&= new URL(req.headers.origin).host === expected;
      } catch { valid = false; }
    }
    if (!valid) { socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n'); return; }
    wss.handleUpgrade(req, socket, head, ws => wss.emit('connection', ws));
  });
  wss.on('connection', ws => {
    let role;
    let alive = true;
    let count = 0;
    let period = Date.now();
    const deadline = setTimeout(() => ws.close(4001,'Authentication required'), 5000);
    ws.on('pong', () => { alive = true; });
    const heartbeat = setInterval(() => { if (!alive) return ws.terminate(); alive = false; ws.ping(); },15000);
    ws.on('error', () => {});
    ws.on('message', (data, binary) => {
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
        if (msg.type !== 'auth' || !['host','viewer'].includes(candidate) || !equal(msg.key, candidate==='host'?hostKey:viewerKey)) {
          failures++; ws.close(4003,'Invalid access key'); return;
        }
        if (peers[candidate]) { ws.close(4009,`${candidate} already connected`); return; }
        clearTimeout(deadline); role=candidate; peers[role]=ws;
        send(ws,{type:'authenticated',role,iceServers});
        if (peers.host && peers.viewer) {
          send(peers.viewer,{type:'host-ready'});
          send(peers.host,{type:'viewer-ready'});
        } else send(ws,{type:'waiting'});
        return;
      }
      const allow=role==='host'?['offer','status','pong']:['answer','input','frame-ack','ping','mode'];
      if (!allow.includes(msg.type)) return;
      const other=peers[role==='host'?'viewer':'host'];
      if (other?.bufferedAmount > 256*1024) { other.close(4008,'Connection too slow; reconnect'); return; }
      send(other,msg);
    });
    ws.on('close', () => {
      clearTimeout(deadline); clearInterval(heartbeat);
      if (role && peers[role]===ws) {
        peers[role]=null;
        send(peers[role==='host'?'viewer':'host'],{type:'peer-left'});
      }
    });
  });
  return {server, close:async () => {
    clearInterval(resetFailures);
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
  const app=createDesktopServer({...keys,iceServers,publicOrigin:origin});
  app.server.listen(port,'0.0.0.0',() => {
    console.log(`\nCodespace Desktop\nViewer: ${origin}\n\nViewer key: ${keys.viewerKey}\nMac host key: ${keys.hostKey}\n\nKeep these keys private. They are NOT GitHub tokens.\nIn Codespaces: Ports → 3000 → Port Visibility → Public.\nThe public viewer page requires its access key; the Mac uses a separate key.\nStop with Ctrl+C.\n`);
  });
  for (const signal of ['SIGINT','SIGTERM']) process.on(signal, async () => { await app.close(); process.exit(0); });
}
