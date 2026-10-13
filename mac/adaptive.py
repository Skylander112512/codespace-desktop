"""Conservative quality changes using interval (not lifetime) receiver statistics."""
import math
import time


class AdaptiveQuality:
    def __init__(self,max_fps=60,bitrate=4_000_000,max_bitrate=6_000_000):
        self.bitrate = bitrate
        self.max_bitrate = max_bitrate
        self.max_fps=max_fps
        self.fps = max_fps
        self.good = 0
        self.bad = 0
        self.updated = 0

    def update(self, report, now=None):
        now = time.monotonic() if now is None else now
        values = [report.get(key) for key in ('loss', 'decode_ms', 'buffer_ms', 'fps')]
        if not all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values):
            return None
        loss, decode, buffer, received = values
        if loss > 1 or decode > 10000 or buffer > 10000 or received > 240 or now-self.updated < 2:
            return None
        self.updated = now
        congested = loss > .03 or buffer > 80
        slow_decoder = decode > 20
        if congested or slow_decoder:
            self.good = 0
            self.bad += 1
            self.bitrate = max(750_000, int(self.bitrate * .75))
            # Lower picture bitrate first. A brief Wi-Fi dip must not lock a
            # healthy 60 FPS decoder to 30 FPS for the next minute.
            if self.bad >= 2 and slow_decoder:
                self.fps = min(self.max_fps, 30)
            elif self.bad >= 3 and self.bitrate < 1_000_000:
                self.fps = min(self.max_fps, 30)
        elif loss < .01 and buffer < 40 and decode < 12 and received >= self.fps * .7:
            self.bad = 0
            self.good += 1
            if self.good >= 3:
                self.good = 0
                self.bitrate = min(self.max_bitrate, self.bitrate + max(250_000, int(self.bitrate * .15)))
                if self.bitrate >= 1_250_000: self.fps = self.max_fps
        else:
            self.good = 0
            self.bad = 0
        return self.bitrate, self.fps
