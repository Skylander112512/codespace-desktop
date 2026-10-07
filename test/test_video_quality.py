import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'mac'))
from video_quality import select_quality

def answer(level='1f',receive=''):
    return f'm=video 9 UDP/TLS/RTP/SAVPF 99\r\na=rtpmap:99 H264/90000\r\na=fmtp:99 profile-level-id=42e0{level};packetization-mode=1{receive}\r\n'
class QualityTests(unittest.TestCase):
    def test_explicit_hd_and_default_selection(self):
        hd=answer(receive=';max-recv-level=e02a')
        self.assertEqual((select_quality(hd,'1080p60').height,select_quality(hd,'1080p60').fps),(1080,60))
        self.assertEqual(select_quality(hd,'720p60').height,720)
        self.assertEqual(select_quality(hd).height,720)
        self.assertEqual(select_quality(answer()).height,480)
        self.assertEqual(select_quality(answer(),'sharp').fps,30)
    def test_receiver_limits_and_unrelated_payloads(self):
        self.assertEqual(select_quality(answer(),'1080p60').height,480)
        self.assertEqual(select_quality(answer('20'),'1080p60').height,720)
        extra='a=fmtp:100 profile-level-id=42e02a\r\n'
        self.assertEqual(select_quality(answer()+extra,'1080p60').height,480)
        self.assertEqual(select_quality(answer('2a').replace('video 9','video 0'),'1080p60').height,480)
if __name__=='__main__':unittest.main()
