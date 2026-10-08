import asyncio
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'mac'))
from reconnect import keep_connected,ConnectionProblem
from host import Host
from websockets.asyncio.server import serve
from websockets.http11 import Response
from websockets.datastructures import Headers

class ReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_outage_backs_off_without_parallel_attempts(self):
        delays=[];attempts=[]
        class Host:
            async def run(self,url,key):
                attempts.append(self)
                raise ConnectionProblem('offline')
        async def sleep(delay):
            delays.append(delay)
            if len(delays)==8:raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await keep_connected(Host,'wss://test','key',log=lambda _:None,sleep=sleep,clock=lambda:0)
        self.assertEqual(delays,[2,4,8,16,32,60,60,60])
        self.assertEqual(len({id(host) for host in attempts}),8)
    async def test_invalid_key_stops_and_cancellation_is_not_retried(self):
        class Host:
            async def run(self,url,key):raise ConnectionProblem('invalid key',retryable=False)
        with self.assertRaisesRegex(ConnectionProblem,'invalid key'):
            await keep_connected(Host,'wss://test','key',sleep=lambda _:self.fail('must not retry'))
    async def test_healthy_session_resets_retry_delay(self):
        times=iter([0,0,1,1,2,70]);delays=[]
        class Host:
            async def run(self,url,key):pass
        async def sleep(delay):
            delays.append(delay)
            if len(delays)==3:raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await keep_connected(Host,'wss://test','key',log=lambda _:None,sleep=sleep,clock=lambda:next(times))
        self.assertEqual(delays,[2,4,2])
    async def test_closed_codespace_redirect_then_live_server_then_disconnect(self):
        requests=0;authenticated=0;ready=asyncio.Event();delays=[];instances=[]
        def gate(connection,request):
            nonlocal requests
            requests+=1
            if requests==1:return Response(404,'Not Found',Headers(),b'Codespace stopped')
            if requests==2:return Response(302,'Found',Headers({'Location':'https://github.dev/pf-signin'}),b'')
        async def server_peer(ws):
            nonlocal authenticated
            auth=json.loads(await ws.recv());self.assertEqual(auth['role'],'host')
            await ws.send(json.dumps({'type':'authenticated','iceServers':[]}))
            authenticated+=1
            if authenticated==1:await ws.close(1001,'Restarting server')
            else:ready.set();await ws.wait_closed()
        def factory():
            instance=Host(demo=True)
            instances.append(instance)
            return instance
        async def quick_sleep(delay):delays.append(delay);await asyncio.sleep(.01)
        async with serve(server_peer,'127.0.0.1',0,process_request=gate) as server:
            port=server.sockets[0].getsockname()[1]
            task=asyncio.create_task(keep_connected(factory,f'ws://127.0.0.1:{port}/ws','x'*43,log=lambda _:None,sleep=quick_sleep))
            try:await asyncio.wait_for(ready.wait(),5)
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(delays,[2,4,8])
        self.assertEqual(authenticated,2)
        self.assertTrue(all(not instance.active and instance.native is None and instance.ws is None for instance in instances))
        self.assertTrue(all(instance.capture.cached is None for instance in instances),'Waiting must not capture any screen')

if __name__=='__main__':unittest.main()

