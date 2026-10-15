"""Opt-in, bounded, local performance numbers. Never log message bodies or input."""
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

PATH=Path.home()/'Library'/'Application Support'/'Codespace Desktop'/'diagnostics.jsonl'
FIELDS={'fps','loss','decode_ms','buffer_ms','network_rtt_ms','jitter_ms','receive_mbps',
        'processing_ms','frames_dropped','freezes','feedback_age_ms','encode_ms',
        'target_fps','bitrate','native_dropped','send_mbps','rtcp_rtt_ms','queue_frames','capture_fps','frame_gap_max_ms','frame_gap_p95_ms',
        'encode_max_ms','keyframe_encode_max_ms','keyframe_bytes_max','keyframes','capture_skipped'}

def numbers(values):
    return {k:round(v,3) for k,v in values.items() if k in FIELDS and type(v) in (int,float) and math.isfinite(v) and 0<=v<=1e12}

class Diagnostics:
    def __init__(self,path=PATH,max_bytes=512_000):
        self.path=Path(path);self.max_bytes=max_bytes;self.last=-float('inf')
        self.failed=False

    def sample(self,values,rtc=False,audio=False,now=None):
        now=time.monotonic() if now is None else now
        if self.failed or now-self.last<2:return
        self.last=now
        record={'at':datetime.now(timezone.utc).isoformat(), 'direct':rtc is True,'sound':audio is True,**numbers(values)}
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if self.path.exists() and self.path.stat().st_size>=self.max_bytes:
                os.replace(self.path,self.path.with_suffix('.previous.jsonl'))
            fd=os.open(self.path,os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
            with os.fdopen(fd,'a') as stream:
                os.fchmod(stream.fileno(),0o600)
                stream.write(json.dumps(record,allow_nan=False)+'\n')
        except OSError:
            self.failed=True # Diagnostics must never interrupt streaming or spam retries.
