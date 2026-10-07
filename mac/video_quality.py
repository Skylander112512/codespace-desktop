"""Select capture limits from the receiver's negotiated H.264 capabilities."""
import re
from dataclasses import dataclass

@dataclass(frozen=True)
class VideoQuality:
    height: int
    fps: int
    bitrate: int
    max_bitrate: int
    @property
    def label(self): return f'{self.height}p / {self.fps} FPS'

COMPACT=VideoQuality(480,60,4_000_000,6_000_000)
HD30=VideoQuality(720,30,4_000_000,6_000_000)
HD60=VideoQuality(720,60,6_000_000,8_000_000)
FULLHD60=VideoQuality(1080,60,10_000_000,16_000_000)

def select_quality(sdp, mode='smooth'):
    # Only inspect accepted H.264 payloads in the video section, not unrelated
    # audio fmtp, rejected media, or codecs that were not negotiated.
    levels=[]
    for section in re.split(r'(?m)^m=',sdp)[1:]:
        lines=section.splitlines()
        media=lines[0].split()
        if len(media)<4 or media[0]!='video' or media[1]=='0': continue
        accepted=set(media[3:])
        h264=set(re.findall(r'(?im)^a=rtpmap:(\d+) H264/90000',section)) & accepted
        for payload,params in re.findall(r'(?im)^a=fmtp:(\d+) (.+)',section):
            if payload not in h264:continue
            profile=re.search(r'profile-level-id=42[ce]0([0-9a-f]{2})',params,re.I)
            if not profile:continue
            level=int(profile[1],16)
            receive=re.search(r'max-recv-level=[0-9a-f]{2}([0-9a-f]{2})',params,re.I)
            if receive:level=max(level,int(receive[1],16))
            levels.append(level)
    level=max(levels,default=31)
    if mode=='1080p60' and level>=42:return FULLHD60
    if mode in ('720p60','1080p60') and level>=32:return HD60
    if mode=='sharp':return HD30 if level<32 else HD60
    # Preserve the original Smooth behavior and bitrate.
    if level>=32:return VideoQuality(720,60,4_000_000,6_000_000)
    return COMPACT
