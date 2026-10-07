"""Hardware encode/WebRTC tests use generated pixels, never the real desktop."""
import asyncio
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parents[1] / 'mac'))
import av
from aiortc import RTCPeerConnection, RTCConfiguration, RTCRtpSender
from native_video import NativeVideoTrack, helper_path


class QueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_overflow_discards_dependent_frames_until_keyframe(self):
        track = NativeVideoTrack()
        track.request_keyframe = Mock()
        nal = b'\x00\x00\x00\x01\x65\x01'
        track._accept({'pts': 1, 'keyframe': True}, nal)
        track._accept({'pts': 2, 'keyframe': False}, nal)
        track._accept({'pts': 3, 'keyframe': False}, nal)
        self.assertTrue(track.queue.empty())
        self.assertTrue(track.waiting_keyframe)
        track.request_keyframe.assert_called_once()
        track._accept({'pts': 4, 'keyframe': True}, nal)
        self.assertEqual((await track.recv()).pts, 4)
        await track.close()

    async def test_invalid_or_reversed_native_frames_are_rejected(self):
        track = NativeVideoTrack()
        with self.assertRaises(ValueError): track._accept({'pts': 1}, b'invalid')
        track._accept({'pts': 2, 'keyframe': True}, b'\x00\x00\x00\x01\x65')
        with self.assertRaises(ValueError): track._accept({'pts': 1}, b'\x00\x00\x00\x01\x65')
        await track.close()


@unittest.skipUnless(sys.platform == 'darwin' and helper_path(), 'Build the Mac native helper first')
class HardwareTests(unittest.IsolatedAsyncioTestCase):
    async def test_hardware_decode_pacing_reconfigure_and_keyframe(self):
        track = await NativeVideoTrack(demo=True).start()
        try:
            decoder = av.CodecContext.create('h264', 'r')
            frames = []
            timings = []
            started = time.monotonic()
            async with asyncio.timeout(10):
                for _ in range(90):
                    packet = await track.recv()
                    frames.extend(decoder.decode(packet))
                    timings.append(track.metrics['encode_ms'])
            elapsed = time.monotonic() - started
            self.assertEqual(len(frames), 90)
            self.assertEqual((frames[-1].width, frames[-1].height), (1280, 720))
            self.assertLess(elapsed, 4.0, 'Synthetic hardware capture should sustain more than 22 FPS')
            track.configure(1_500_000, 30)
            track.request_keyframe()
            async with asyncio.timeout(2):
                while not (await track.recv()).is_keyframe: pass
            self.assertEqual(track.settings, {'bitrate': 1_500_000, 'fps': 30})
            print(f'Hardware: {90/elapsed:.1f} frames/s; mean encode {sum(timings)/len(timings):.2f} ms')
        finally:
            await track.close()
        self.assertIsNotNone(track.process.returncode)

    async def test_fullhd_60fps_hardware_frames(self):
        track=await NativeVideoTrack(demo=True,height=1080,bitrate=10_000_000).start()
        try:
            decoder=av.CodecContext.create('h264','r')
            started=time.monotonic(); count=0
            async with asyncio.timeout(8):
                for _ in range(90):
                    packet=await track.recv()
                    for frame in decoder.decode(packet):
                        self.assertEqual((frame.width,frame.height),(1920,1080));count+=1
            elapsed=time.monotonic()-started
            self.assertEqual(count,90)
            self.assertEqual(track.settings['fps'],60)
            self.assertLess(elapsed,3.0)
            print(f'1080p hardware: {count/elapsed:.1f} frames/s')
        finally:await track.close()

    async def test_compact_60fps_stays_within_browser_level31(self):
        track=await NativeVideoTrack(demo=True,compact=True).start()
        try:
            packet=await asyncio.wait_for(track.recv(),2)
            payload=bytes(packet)
            self.assertEqual(payload[4]&31,7) # First NAL is SPS.
            self.assertLessEqual(payload[7],31)
            frame=av.CodecContext.create('h264','r').decode(packet)[0]
            self.assertEqual((frame.width,frame.height),(854,480))
            self.assertEqual(track.settings['fps'],60)
        finally:await track.close()

    async def test_h264_packets_travel_over_webrtc_and_pli_reaches_encoder(self):
        track = await NativeVideoTrack(demo=True).start()
        sender_peer = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        receiver_peer = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        got_frames = asyncio.Future()
        receiver_tasks = []
        @receiver_peer.on('track')
        def receive(video):
            async def consume():
                try:
                    count = 0
                    for _ in range(60):
                        frame = await video.recv()
                        self.assertEqual(frame.width, 1280)
                        count += 1
                    if not got_frames.done(): got_frames.set_result(count)
                except Exception as error:
                    if not got_frames.done(): got_frames.set_exception(error)
            receiver_tasks.append(asyncio.create_task(consume()))
        try:
            sender = sender_peer.addTrack(track)
            track.bind_sender(sender)
            sender_peer.getTransceivers()[0].setCodecPreferences([
                codec for codec in RTCRtpSender.getCapabilities('video').codecs
                if codec.mimeType.lower() == 'video/h264' and codec.parameters.get('profile-level-id') == '42e01f'])
            await sender_peer.setLocalDescription(await sender_peer.createOffer())
            await receiver_peer.setRemoteDescription(sender_peer.localDescription)
            await receiver_peer.setLocalDescription(await receiver_peer.createAnswer())
            await sender_peer.setRemoteDescription(receiver_peer.localDescription)
            self.assertEqual(await asyncio.wait_for(got_frames, 15), 60)
            # Exercise aiortc's RTCP PLI path, not just a direct helper call.
            from aiortc.rtp import RtcpPsfbPacket, RTCP_PSFB_PLI
            track.last_keyframe_request = 0
            await sender._handle_rtcp_packet(RtcpPsfbPacket(fmt=RTCP_PSFB_PLI, ssrc=1, media_ssrc=sender._ssrc, fci=b''))
            self.assertGreater(track.last_keyframe_request, 0)
        finally:
            await sender_peer.close(); await receiver_peer.close(); await track.close()
            for task in receiver_tasks: task.cancel()
            await asyncio.gather(*receiver_tasks, return_exceptions=True)

if __name__ == '__main__': unittest.main()
