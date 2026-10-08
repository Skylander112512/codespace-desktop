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
        self.controls.bounds=q.CGRectMake(0,0,1920,1080)
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

    def test_relative_turn_has_nonzero_deltas_and_stays_at_center(self):
        self.controls.handle({'action':'pointer-lock','enabled':True,'seq':1})
        self.controls.handle({'action':'look','dx':12,'dy':-7,'seq':2,'after':1})
        self.controls.handle({'action':'look','dx':10,'dy':5,'seq':3,'after':1})
        for event,delta in zip(self.posted[-2:],[(12,-7),(10,5)]):
            self.assertEqual(q.CGEventGetIntegerValueField(event,q.kCGMouseEventDeltaX),delta[0])
            self.assertEqual(q.CGEventGetIntegerValueField(event,q.kCGMouseEventDeltaY),delta[1])
            point=q.CGEventGetLocation(event)
            self.assertEqual((point.x,point.y),(960,540))

    def test_relative_right_drag_and_release_keep_clicks_paired(self):
        self.controls.handle({'action':'pointer-lock','enabled':True,'seq':1})
        self.controls.handle({'action':'down','relative':True,'button':2,'seq':2})
        self.controls.handle({'action':'look','dx':5,'dy':3,'seq':3,'after':2})
        self.assertEqual(q.CGEventGetType(self.posted[-1]),q.kCGEventRightMouseDragged)
        self.controls.handle({'action':'release','seq':4})
        self.assertFalse(self.controls.relative_mouse)
        self.assertEqual(q.CGEventGetType(self.posted[-1]),q.kCGEventRightMouseUp)
        count=len(self.posted)
        self.controls.handle({'action':'look','dx':99,'dy':99,'seq':3,'after':2})
        self.controls.handle({'action':'look','dx':99,'dy':99,'seq':5,'after':4})
        self.assertEqual(len(self.posted),count)

    def test_relative_validation_fractional_motion_and_idle_release(self):
        self.controls.set_relative_mouse(True)
        count=len(self.posted)
        for value in (float('nan'),float('inf'),5000,True,None):self.controls.look(value,1)
        self.assertEqual(len(self.posted),count)
        self.controls.look(.6,-.6);self.controls.look(.6,-.6)
        self.assertEqual(q.CGEventGetIntegerValueField(self.posted[-1],q.kCGMouseEventDeltaX),1)
        self.controls.release(keep_relative=True)
        self.assertTrue(self.controls.relative_mouse)
        self.controls.look(5,0)
        self.assertEqual(q.CGEventGetIntegerValueField(self.posted[-1],q.kCGMouseEventDeltaX),5)

if __name__=='__main__':unittest.main()
