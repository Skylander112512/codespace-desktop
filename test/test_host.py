"""Synthetic tests: never capture or send input to the real Mac desktop."""
import asyncio
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from websockets.asyncio.server import serve
from websockets.http11 import Response
from websockets.datastructures import Headers
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration
from websockets.asyncio.client import connect

spec=importlib.util.spec_from_file_location('host',Path(__file__).parents[1]/'mac/host.py')
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)

class UnitTests(unittest.TestCase):
    def test_reject_insecure_remote_and_credentials(self):
        for url in ['http://remote.example','https://a:b@remote.example','https://remote.example/path','https://remote.example/?token=abc']:
            with self.assertRaises(ValueError):host.websocket_url(url)
        self.assertEqual(host.websocket_url('https://sample-3000.app.github.dev'),'wss://sample-3000.app.github.dev/ws')

    def test_demo_cli_prompts_for_url_without_mac_permissions(self):
        async def fake_run(agent, url, key):
            self.assertEqual(url, 'ws://localhost:3000/ws')
            self.assertTrue(agent.capture.demo)
            agent.capture.close()
        with patch.object(host.sys, 'argv', ['host.py', '--demo']), patch('builtins.input', return_value='http://localhost:3000'), patch.object(host.getpass, 'getpass', return_value='x'*43), patch.object(host.Host, 'run', fake_run):
            host.main()

    def test_release_all_inputs_and_validate_coordinates(self):
        controls=host.MacInput(demo=True)
        controls.handle({'action':'key','code':'MetaLeft','down':True})
        controls.handle({'action':'down','button':0,'x':.3,'y':.4})
        self.assertEqual(controls.keys,{'MetaLeft'});self.assertEqual(controls.buttons,{0})
        controls.handle({'action':'release'})
        self.assertFalse(controls.keys);self.assertFalse(controls.buttons)
        controls.handle({'action':'down','x':float('nan'),'y':.5})
        self.assertFalse(controls.buttons)

class Integration(unittest.IsolatedAsyncioTestCase):
    async def test_private_port_redirect_has_actionable_error(self):
        def reject(connection, request):
            return Response(302, 'Found', Headers({'Location':'https://github.dev/pf-signin'}), b'')
        async with serve(lambda ws: None, '127.0.0.1', 0, process_request=reject) as server:
            port=server.sockets[0].getsockname()[1]
            with self.assertRaisesRegex(RuntimeError, r'HTTP 302.*Public'):
                await host.Host(demo=True).run(f'ws://127.0.0.1:{port}/ws','x'*43)

    async def test_webrtc_relay_and_session_reconnect(self):
        agent=host.Host(demo=True)
        task=asyncio.create_task(agent.run('ws://127.0.0.1:3000/ws','synthetic-host-key-00000000000000000000'))
        peer=RTCPeerConnection(RTCConfiguration(iceServers=[]))
        video_received=asyncio.Event();control_received=asyncio.Event()
        @peer.on('track')
        def track(track):
            async def receive():
                frame=await track.recv()
                if frame.width==1280:video_received.set()
            asyncio.create_task(receive())
        @peer.on('datachannel')
        def datachannel(channel):
            @channel.on('open')
            def opened():channel.send(json.dumps({'type':'ping','at':123}))
            @channel.on('message')
            def message(raw):
                if json.loads(raw).get('at')==123:control_received.set()
            # aiortc may deliver the channel after it has already opened.
            if channel.readyState=='open':opened()
        try:
            async with connect('ws://127.0.0.1:3000/ws') as ws:
                await ws.send(json.dumps({'type':'auth','role':'viewer','key':'synthetic-viewer-key-000000000000000000'}))
                jpeg=False;answered=False
                async with asyncio.timeout(20):
                    while not (jpeg and answered):
                        raw=await ws.recv()
                        if isinstance(raw,bytes):
                            self.assertTrue(raw.startswith(b'\xff\xd8'));jpeg=True
                            await ws.send(json.dumps({'type':'frame-ack'}))
                        else:
                            msg=json.loads(raw)
                            if msg.get('type')=='offer':
                                await peer.setRemoteDescription(RTCSessionDescription(sdp=msg['sdp'],type='offer'))
                                await peer.setLocalDescription(await peer.createAnswer())
                                await ws.send(json.dumps({'type':'answer','sdp':peer.localDescription.sdp}));answered=True
                    await video_received.wait();await control_received.wait()
                await ws.send(json.dumps({'type':'input','action':'key','code':'MetaLeft','down':True}))
                await asyncio.sleep(.1);self.assertIn('MetaLeft',agent.controls.keys)
            await asyncio.sleep(.2);self.assertFalse(agent.controls.keys);self.assertFalse(agent.active)
            # Fresh viewer must be able to reconnect to the still-running host.
            async with connect('ws://127.0.0.1:3000/ws') as ws:
                await ws.send(json.dumps({'type':'auth','role':'viewer','key':'synthetic-viewer-key-000000000000000000'}))
                async with asyncio.timeout(5):
                    while not isinstance(await ws.recv(),bytes):pass
        finally:
            await peer.close();task.cancel()
            try:await task
            except asyncio.CancelledError:pass

if __name__=='__main__':unittest.main()
