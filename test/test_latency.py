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

    def test_adaptation_preserves_fps_through_brief_loss_then_recovers(self):
        quality=AdaptiveQuality()
        bad={'loss':.1,'decode_ms':3,'buffer_ms':90,'fps':60}
        self.assertEqual(quality.update(bad,now=10),(3_000_000,60))
        self.assertIsNone(quality.update(bad,now=11))
        quality.update(bad,now=12);quality.update(bad,now=14)
        self.assertEqual(quality.fps,60)
        bitrate=quality.bitrate
        good={'loss':0,'decode_ms':3,'buffer_ms':10,'fps':60}
        for now in (16,18):quality.update(good,now=now)
        self.assertEqual(quality.bitrate,bitrate)
        quality.update(good,now=20)
        self.assertGreater(quality.bitrate,bitrate)
        self.assertIsNone(quality.update({**good,'loss':float('nan')},now=30))
        self.assertIsNone(quality.update({**good,'fps':-1},now=30))

    def test_persistent_decoder_overload_reduces_fps_and_clean_samples_restore_it(self):
        quality=AdaptiveQuality()
        bad={'loss':0,'decode_ms':25,'buffer_ms':30,'fps':30}
        quality.update(bad,now=10);self.assertEqual(quality.fps,60)
        quality.update(bad,now=12);self.assertEqual(quality.fps,30)
        good={**bad,'decode_ms':4}
        for now in (14,16,18):quality.update(good,now=now)
        self.assertEqual(quality.fps,60)
        limited=AdaptiveQuality(max_fps=30)
        for now in (10,12,14):limited.update(good,now=now)
        self.assertEqual(limited.fps,30)

    def test_persistent_severe_loss_remains_bounded(self):
        quality=AdaptiveQuality()
        bad={'loss':.3,'decode_ms':3,'buffer_ms':200,'fps':0}
        for now in range(10,40,2):quality.update(bad,now=now)
        self.assertEqual((quality.bitrate,quality.fps),(750_000,30))

    def test_buffer_delay_alone_does_not_collapse_quality_or_fps(self):
        quality=AdaptiveQuality()
        delayed={'loss':0,'decode_ms':6,'buffer_ms':120,'fps':57}
        for now in range(10,70,2):quality.update(delayed,now=now)
        self.assertEqual((quality.bitrate,quality.fps),(1_687_500,60))
        # The cap only applies to buffer-only feedback: real loss still adapts.
        for now in range(70,100,2):quality.update({**delayed,'loss':.15},now=now)
        self.assertEqual((quality.bitrate,quality.fps),(750_000,30))

    def test_buffer_with_frame_starvation_still_reduces_load(self):
        quality=AdaptiveQuality()
        for now in range(10,40,2):
            quality.update({'loss':0,'decode_ms':6,'buffer_ms':200,'fps':5},now=now)
        self.assertEqual((quality.bitrate,quality.fps),(750_000,30))

    def test_clean_recovery_restores_budget_for_later_buffer_episode(self):
        quality=AdaptiveQuality()
        delayed={'loss':0,'decode_ms':6,'buffer_ms':120,'fps':57}
        for now in (10,12,14):quality.update(delayed,now=now)
        before=quality.bitrate
        for now in (16,18,20):quality.update({**delayed,'buffer_ms':20},now=now)
        self.assertGreater(quality.bitrate,before)
        restored=quality.bitrate
        quality.update(delayed,now=22)
        self.assertLess(quality.bitrate,restored)

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
