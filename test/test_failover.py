"""Automatic selection tests never use user servers or the real desktop."""
import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'mac'))
from reconnect import keep_available,ConnectionProblem
from host_settings import load_connections,load_settings,save_settings,save_backup
from host import Host
from websockets.asyncio.server import serve
from websockets.http11 import Response
from websockets.datastructures import Headers

A={'url':'https://first.example','key':'a'*43}
B={'url':'https://second.example','key':'b'*43}

class FailoverTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_connection_stops_searching_and_cancellation_cleans_up(self):
        tried=[];closed=[];ready=asyncio.Event();reads=[]
        class Agent:
            def __init__(self,entry):self.entry=entry
            async def run(self,url,key):
                tried.append(url)
                try:
                    if self.entry==A:raise ConnectionProblem('offline')
                    ready.set();await asyncio.Future()
                finally:closed.append(url)
        def entries():reads.append(1);return [A,B]
        task=asyncio.create_task(keep_available(Agent,entries,log=lambda _:None))
        await asyncio.wait_for(ready.wait(),1)
        for _ in range(10):await asyncio.sleep(0)
        self.assertEqual(tried,['wss://first.example/ws','wss://second.example/ws'])
        self.assertEqual(closed,['wss://first.example/ws']);self.assertEqual(len(reads),1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(closed,tried)

    async def test_all_offline_scan_backoff_is_bounded_and_serial(self):
        tried=[];delays=[];active=0
        class Agent:
            def __init__(self,entry):self.entry=entry
            async def run(self,url,key):
                nonlocal active
                active+=1;self_test.assertEqual(active,1);tried.append(self.entry)
                try:raise OSError('offline')
                finally:active-=1
        self_test=self
        async def sleep(delay):
            delays.append(delay)
            if len(delays)==8:raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await keep_available(Agent,lambda:[A,B],log=lambda _:None,sleep=sleep,clock=lambda:0)
        self.assertEqual(delays,[2,4,8,16,32,60,60,60]);self.assertEqual(tried,[A,B]*8)

    async def test_bad_key_does_not_block_backup_and_corrected_key_is_retried(self):
        tried=[];rounds=0;corrected={**A,'key':'c'*43}
        class Agent:
            def __init__(self,entry):self.entry=entry
            async def run(self,url,key):
                tried.append(self.entry)
                if self.entry==A:raise ConnectionProblem('bad key',retryable=False)
                raise ConnectionProblem('offline')
        async def sleep(delay):
            nonlocal rounds
            rounds+=1
            if rounds==3:raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await keep_available(Agent,lambda:[corrected if rounds>=2 else A,B],log=lambda _:None,sleep=sleep)
        self.assertEqual(tried,[A,B,B,corrected,B])

    async def test_real_disconnect_moves_to_next_saved_server_without_capture(self):
        readyA=asyncio.Event();readyB=asyncio.Event();disconnect=asyncio.Event();agents=[]
        async def first(ws):
            self.assertEqual(json.loads(await ws.recv())['key'],A['key'])
            await ws.send(json.dumps({'type':'authenticated','iceServers':[]}))
            readyA.set();await disconnect.wait();await ws.close(1001,'offline')
        async def second(ws):
            self.assertEqual(json.loads(await ws.recv())['key'],B['key'])
            await ws.send(json.dumps({'type':'authenticated','iceServers':[]}))
            readyB.set();await ws.wait_closed()
        async with serve(first,'127.0.0.1',0) as a,serve(second,'127.0.0.1',0) as b:
            entries=[{**entry,'url':f'http://127.0.0.1:{srv.sockets[0].getsockname()[1]}'} for entry,srv in ((A,a),(B,b))]
            def factory(entry):
                agent=Host(demo=True);agents.append(agent);return agent
            task=asyncio.create_task(keep_available(factory,lambda:entries,log=lambda _:None))
            try:
                await asyncio.wait_for(readyA.wait(),2)
                self.assertFalse(readyB.is_set());disconnect.set()
                await asyncio.wait_for(readyB.wait(),2)
                self.assertIsNone(agents[0].ws)
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):await task
            self.assertTrue(all(agent.native is None and agent.capture.cached is None and agent.ws is None for agent in agents))

    async def test_server_that_never_authenticates_cannot_block_the_backup(self):
        ready=asyncio.Event()
        async def silent(ws):await ws.recv();await ws.wait_closed()
        async def healthy(ws):
            await ws.recv();await ws.send(json.dumps({'type':'authenticated','iceServers':[]}))
            ready.set();await ws.wait_closed()
        async with serve(silent,'127.0.0.1',0) as a,serve(healthy,'127.0.0.1',0) as b:
            entries=[{**entry,'url':f'http://127.0.0.1:{srv.sockets[0].getsockname()[1]}'} for entry,srv in ((A,a),(B,b))]
            with patch('host.AUTH_TIMEOUT',.03):
                task=asyncio.create_task(keep_available(lambda _:Host(demo=True),lambda:entries,log=lambda _:None))
                try:await asyncio.wait_for(ready.wait(),2)
                finally:
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):await task

    async def test_saved_new_backup_is_loaded_on_next_round(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'connection.json';save_settings(**{'url':A['url'],'key':A['key'],'path':path})
            attempted=[];rounds=0
            class Agent:
                def __init__(self,entry):self.entry=entry
                async def run(self,url,key):attempted.append(self.entry);raise ConnectionProblem('offline')
            async def sleep(delay):
                nonlocal rounds
                rounds+=1
                if rounds==1:save_backup(B['url'],B['key'],path)
                else:raise asyncio.CancelledError()
            with self.assertRaises(asyncio.CancelledError):
                await keep_available(Agent,lambda:load_connections(path),log=lambda _:None,sleep=sleep)
            self.assertEqual(attempted,[A,A,B]);self.assertEqual(load_settings(path),A)

class BackupTests(unittest.TestCase):
    def test_offline_backup_does_not_replace_active_and_survives_next_auth(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'connection.json';save_settings(A['url'],A['key'],path)
            save_backup(B['url'],B['key'],path)
            self.assertEqual(load_settings(path),A);self.assertEqual(load_connections(path),[A,B])
            save_settings(A['url'],A['key'],path)
            self.assertEqual(load_connections(path),[A,B])
            save_settings(B['url'],B['key'],path)
            self.assertEqual(load_connections(path),[B,A]);self.assertEqual(load_settings(path),B)
    def test_updating_active_key_does_not_get_shadowed_by_legacy_field(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'connection.json';save_settings(A['url'],A['key'],path)
            save_backup(A['url'],B['key'],path)
            self.assertEqual(load_connections(path),[{**A,'key':B['key']}])

if __name__=='__main__':unittest.main()
