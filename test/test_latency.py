import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'mac'))
from adaptive import AdaptiveQuality
from host import MacInput
from host_settings import load_settings,save_settings

class LatencyTests(unittest.TestCase):
    def test_late_motion_cannot_recreate_drag_after_release(self):
        controls=MacInput(demo=True)
        controls.handle({'action':'down','button':0,'x':.5,'y':.5,'seq':1})
        controls.handle({'action':'release','seq':4})
        controls.handle({'action':'move','x':.8,'y':.8,'seq':3,'after':1})
        self.assertFalse(controls.buttons)
        self.assertEqual(controls.last_motion_seq,0)
        # Motion overtaking a key/button waits for a fresh motion after delivery.
        controls.handle({'action':'move','x':.8,'y':.8,'seq':6,'after':5})
        self.assertEqual(controls.last_motion_seq,0)
        controls.handle({'action':'down','button':0,'x':.5,'y':.5,'seq':5})
        controls.handle({'action':'move','x':.8,'y':.8,'seq':7,'after':5})
        self.assertEqual(controls.last_motion_seq,7)
        controls.handle({'action':'release','seq':8})
        controls.handle({'action':'key','code':'MetaLeft','down':True,'seq':2})
        self.assertFalse(controls.keys)
        self.assertFalse(controls.buttons)

    def test_adaptation_reduces_under_loss_and_recovers_gradually(self):
        quality=AdaptiveQuality()
        bad={'loss':.1,'decode_ms':3,'buffer_ms':90,'fps':60}
        self.assertEqual(quality.update(bad,now=10),(3_000_000,60))
        self.assertIsNone(quality.update(bad,now=11))
        quality.update(bad,now=12);quality.update(bad,now=14)
        self.assertEqual(quality.fps,30)
        bitrate=quality.bitrate
        good={'loss':0,'decode_ms':3,'buffer_ms':10,'fps':30}
        for now in (16,18,20):quality.update(good,now=now)
        self.assertEqual(quality.bitrate,bitrate)
        quality.update(good,now=22)
        self.assertEqual(quality.bitrate,bitrate+250_000)
        self.assertIsNone(quality.update({**good,'loss':float('nan')},now=30))
        self.assertIsNone(quality.update({**good,'fps':-1},now=30))

    def test_saved_settings_are_private_and_survive_next_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'private'/'connection.json'
            self.assertIsNone(load_settings(path))
            save_settings('https://synthetic.example','synthetic-host-key-'+'x'*32,path)
            self.assertEqual(os.stat(path).st_mode&0o777,0o600)
            self.assertEqual(load_settings(path)['url'],'https://synthetic.example')
            path.write_text('not json')
            self.assertIsNone(load_settings(path))

if __name__=='__main__':unittest.main()
