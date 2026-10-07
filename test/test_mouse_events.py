"""Inspect real Quartz event objects, but intercept every post: no desktop input."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'mac'))
import Quartz as q
from host import MacInput

class MouseEvents(unittest.TestCase):
    def setUp(self):
        self.controls=MacInput(demo=True)
        self.controls.demo=False
        self.controls.q=q
        self.controls.point=(100,100)
        self.posted=[]
        self.post=patch.object(q,'CGEventPost',side_effect=lambda tap,event:self.posted.append(event))
        self.post.start();self.addCleanup(self.post.stop)

    def test_click_has_matching_count_and_event_number_on_release(self):
        self.controls.mouse('down',0);self.controls.mouse('up',0)
        down,up=self.posted
        self.assertEqual(q.CGEventGetIntegerValueField(down,q.kCGMouseEventClickState),1)
        self.assertEqual(q.CGEventGetIntegerValueField(up,q.kCGMouseEventClickState),1)
        self.assertEqual(q.CGEventGetIntegerValueField(down,q.kCGMouseEventNumber),q.CGEventGetIntegerValueField(up,q.kCGMouseEventNumber))

    def test_second_click_and_drag_keep_press_metadata(self):
        with patch('host.time.monotonic',return_value=100):
            self.controls.mouse('down',0);self.controls.mouse('up',0)
        with patch('host.time.monotonic',return_value=100.1):
            self.controls.mouse('down',0);self.controls.mouse('move');self.controls.mouse('up',0)
        self.assertEqual([q.CGEventGetIntegerValueField(e,q.kCGMouseEventClickState) for e in self.posted],[1,1,2,2,2])
        self.assertEqual(q.CGEventGetType(self.posted[3]),q.kCGEventLeftMouseDragged)
        self.assertFalse(self.controls.buttons)

    def test_release_uses_the_original_press_even_after_pointer_moves(self):
        self.controls.mouse('down',2)
        self.controls.point=(500,400)
        self.controls.release()
        self.assertEqual(q.CGEventGetType(self.posted[-1]),q.kCGEventRightMouseUp)
        self.assertEqual(q.CGEventGetIntegerValueField(self.posted[-1],q.kCGMouseEventClickState),1)
        self.assertFalse(self.controls.buttons)

if __name__=='__main__':unittest.main()
