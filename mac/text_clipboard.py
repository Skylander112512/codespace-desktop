"""User-requested plain text transfers only; no clipboard polling or shell."""
import subprocess

MAX_BYTES = 16 * 1024

class TextClipboard:
    def __init__(self, demo=False):
        self.demo=demo
        self.text=''

    def transfer(self, action, text=None):
        if action=='write':
            if not isinstance(text,str):raise ValueError('Enter text to send.')
            data=text.encode('utf-8')
            if len(data)>MAX_BYTES:raise ValueError('Text is too long. Send up to 16 KB at a time.')
            if self.demo:self.text=text
            else:subprocess.run(['/usr/bin/pbcopy'],input=data,check=True,timeout=3)
            return None
        if action!='read':raise ValueError('Unknown text transfer action.')
        if self.demo:text=self.text
        else:
            data=subprocess.run(['/usr/bin/pbpaste','-Prefer','txt'],capture_output=True,check=True,timeout=3).stdout
            if len(data)>MAX_BYTES:raise ValueError('Mac clipboard text is too long. Copy a smaller selection.')
            text=data.decode('utf-8')
        if len(text.encode('utf-8'))>MAX_BYTES:raise ValueError('Mac clipboard text is too long. Copy a smaller selection.')
        return text
