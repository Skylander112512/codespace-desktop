import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).parents[1]/'mac'))
from diagnostics import Diagnostics
from host import Host

class DiagnosticTests(unittest.TestCase):
    def test_only_finite_allowlisted_numbers_are_written_privately_and_rate_limited(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'metrics.jsonl';log=Diagnostics(path)
            log.sample({'fps':60,'buffer_ms':120,'key':'never-log-this','text':'private','url':'private',
                        'loss':float('nan'),'decode_ms':-1},now=10,rtc=True)
            log.sample({'fps':20},now=11)
            rows=path.read_text().splitlines();self.assertEqual(len(rows),1)
            row=json.loads(rows[0]);self.assertEqual(row['fps'],60)
            self.assertEqual(set(row),{'at','direct','sound','fps','buffer_ms'})
            self.assertEqual(os.stat(path).st_mode&0o777,0o600)

    def test_rotation_is_bounded_and_disk_failure_is_nonfatal(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'metrics.jsonl';log=Diagnostics(path,max_bytes=1)
            for now in (10,12,14):log.sample({'fps':now},now=now)
            self.assertEqual(json.loads(path.read_text())['fps'],14)
            self.assertEqual(json.loads(path.with_suffix('.previous.jsonl').read_text())['fps'],12)
            broken=Diagnostics(path/'impossible');broken.sample({'fps':60},now=10)
            self.assertTrue(broken.failed)

class HostDiagnostics(unittest.IsolatedAsyncioTestCase):
    async def test_receiver_and_sender_metrics_are_combined_without_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'metrics.jsonl';log=Diagnostics(path)
            host=Host(demo=True,diagnostics=log)
            host.pc=SimpleNamespace(getStats=AsyncMock(return_value={
                'r':SimpleNamespace(type='remote-inbound-rtp',kind='video',roundTripTime=.08),
                's':SimpleNamespace(type='outbound-rtp',kind='video',bytesSent=20000)}))
            host.feedback({'fps':60,'buffer_ms':150,'text':'never-write'})
            await host.record_diagnostics({'encode_ms':4,'fps':60,'bitrate':4000000})
            row=json.loads(path.read_text());self.assertEqual(row['rtcp_rtt_ms'],80)
            self.assertEqual(row['buffer_ms'],150);self.assertEqual(row['encode_ms'],4)
            self.assertNotIn('never-write',path.read_text());host.capture.close()

if __name__=='__main__':unittest.main()
