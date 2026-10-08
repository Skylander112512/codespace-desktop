"""No real clipboard reads/writes: subprocesses are intercepted or demo-only."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
sys.path.insert(0,str(Path(__file__).parents[1]/'mac'))
from text_clipboard import TextClipboard, MAX_BYTES
from host import Host

class ClipboardTests(unittest.TestCase):
    def test_native_commands_use_literal_utf8_stdin_without_shell(self):
        text='Hello\n世界 👋 $(not-a-command)'
        clipboard=TextClipboard()
        with patch('text_clipboard.subprocess.run',return_value=SimpleNamespace(stdout=text.encode())) as run:
            clipboard.transfer('write',text)
            self.assertEqual(run.call_args.args[0],['/usr/bin/pbcopy'])
            self.assertEqual(run.call_args.kwargs['input'],text.encode())
            self.assertNotIn('shell',run.call_args.kwargs)
            self.assertEqual(clipboard.transfer('read'),text)
            self.assertEqual(run.call_args.args[0],['/usr/bin/pbpaste','-Prefer','txt'])

    def test_empty_text_and_unicode_round_trip_in_demo(self):
        clipboard=TextClipboard(demo=True)
        for text in ['','line one\nline two','😀世界']:
            clipboard.transfer('write',text)
            self.assertEqual(clipboard.transfer('read'),text)

    def test_invalid_or_large_writes_never_touch_clipboard(self):
        clipboard=TextClipboard()
        with patch('text_clipboard.subprocess.run') as run:
            for action,text in [('write',None),('write','😀'*5000),('other','test')]:
                with self.assertRaises(ValueError):clipboard.transfer(action,text)
            run.assert_not_called()
        with patch('text_clipboard.subprocess.run',return_value=SimpleNamespace(stdout=b'x'*(MAX_BYTES+1))):
            with self.assertRaises(ValueError):clipboard.transfer('read')

class ClipboardProtocol(unittest.IsolatedAsyncioTestCase):
    async def test_request_requires_active_session_and_replies_with_matching_id(self):
        host=Host(demo=True);host.send=AsyncMock()
        await host.transfer_text({'action':'write','request':1,'text':'secret'})
        host.send.assert_not_called();self.assertEqual(host.clipboard.text,'')
        host.active=True
        await host.transfer_text({'action':'write','request':1,'text':'Hello 👋'})
        host.send.assert_awaited_with({'type':'clipboard-result','request':1,'ok':True})
        await host.transfer_text({'action':'read','request':2})
        host.send.assert_awaited_with({'type':'clipboard-result','request':2,'ok':True,'text':'Hello 👋'})
        await host.transfer_text({'action':'write','request':3,'text':None})
        self.assertFalse(host.send.call_args.args[0]['ok'])
        host.capture.close()

if __name__=='__main__':unittest.main()
