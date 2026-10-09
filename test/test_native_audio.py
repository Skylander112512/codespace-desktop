"""Generated tones only: never capture real system audio or microphone."""
import asyncio
import math
import struct
import sys
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'mac'))
from native_audio import NativeAudioTrack, audio_helper_path, BYTES
from aiortc import RTCPeerConnection, RTCConfiguration

def rms(frame):
    size=frame.samples*len(frame.layout.channels)*2
    data=bytes(frame.planes[0])[:size]
    values=struct.unpack('<'+'h'*(len(data)//2),data)
    return math.sqrt(sum(v*v for v in values)/len(values))

class AudioQueue(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_sends_silence_without_starting_capture(self):
        track=NativeAudioTrack(demo=True)
        try:
            first=await track.recv();second=await track.recv()
            self.assertEqual(first.sample_rate,48000);self.assertEqual(second.pts-first.pts,960)
            self.assertEqual(first.layout.name,'stereo');self.assertEqual(rms(first),0)
            self.assertIsNone(track.process)
        finally:await track.close()

    async def test_partial_pcm_and_overflow_stay_bounded_and_mute_clears_audio(self):
        track=NativeAudioTrack(demo=True);track.enabled=True
        track._accept(bytes(BYTES-1));self.assertTrue(track.queue.empty())
        track._accept(bytes(1));self.assertEqual(track.queue.qsize(),1)
        for i in range(10):track._accept(struct.pack('<h',i)*1920)
        self.assertEqual(track.queue.qsize(),3);self.assertGreater(track.dropped,0)
        self.assertLess(len(track.pending),BYTES)
        await track.disable();self.assertEqual(rms(await track.recv()),0)
        self.assertTrue(track.queue.empty());await track.close()

@unittest.skipUnless(audio_helper_path(),'Build SystemAudio helper first')
class AudioHardware(unittest.IsolatedAsyncioTestCase):
    async def test_native_generated_tones_enable_mute_and_reenable(self):
        track=NativeAudioTrack(demo=True)
        try:
            for _ in range(2):
                await track.enable();process=track.process
                peak=0;started=time.monotonic()
                for _ in range(25):peak=max(peak,rms(await track.recv()))
                self.assertGreater(peak,1000);self.assertLess(time.monotonic()-started,1.5)
                await track.disable()
                self.assertIsNotNone(process.returncode);self.assertEqual(rms(await track.recv()),0)
                self.assertIsNone(track.failure)
        finally:await track.close()

    async def test_opus_audio_arrives_over_webrtc(self):
        track=NativeAudioTrack(demo=True)
        sender=RTCPeerConnection(RTCConfiguration(iceServers=[]))
        receiver=RTCPeerConnection(RTCConfiguration(iceServers=[]))
        arrived=asyncio.Future();tasks=[]
        @receiver.on('track')
        def incoming(audio):
            async def consume():
                try:
                    for _ in range(100):
                        frame=await audio.recv()
                        if rms(frame)>100:
                            if not arrived.done():arrived.set_result(frame.sample_rate)
                            return
                except Exception as error:
                    if not arrived.done():arrived.set_exception(error)
            tasks.append(asyncio.create_task(consume()))
        try:
            await track.enable();sender.addTrack(track)
            await sender.setLocalDescription(await sender.createOffer())
            await receiver.setRemoteDescription(sender.localDescription)
            await receiver.setLocalDescription(await receiver.createAnswer())
            await sender.setRemoteDescription(receiver.localDescription)
            self.assertEqual(await asyncio.wait_for(arrived,10),48000)
            self.assertIn('opus/48000',sender.localDescription.sdp.lower())
        finally:
            await sender.close();await receiver.close();await track.close()
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)

if __name__=='__main__':unittest.main()
