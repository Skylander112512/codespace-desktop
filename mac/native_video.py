"""Bounded H.264 passthrough from the signed, local ScreenEncoder helper."""
import asyncio
import contextlib
import json
import sys
import time
from fractions import Fraction
from pathlib import Path

import av
from aiortc import VideoStreamTrack
from aiortc.mediastreams import MediaStreamError


def helper_path():
    roots = [Path(sys.executable).parent, Path(__file__).parent]
    if getattr(sys, 'frozen', False):
        roots.insert(0, Path(sys._MEIPASS))
    for root in roots:
        for path in (root / 'ScreenEncoder', root / 'bin' / 'ScreenEncoder'):
            if path.is_file():
                return path
    return None


class NativeVideoTrack(VideoStreamTrack):
    def __init__(self, demo=False, path=None, max_fps=60, compact=False):
        super().__init__()
        self.demo = demo
        self.max_fps = max_fps
        self.compact = compact
        self.path = path or helper_path()
        self.process = None
        self.queue = asyncio.Queue(maxsize=2)
        self.tasks = []
        self.ready = asyncio.Event()
        self.failure = None
        self.waiting_keyframe = True
        self.last_keyframe_request = 0
        self.last_pts = -1
        self.metrics = {}
        self.settings = {'bitrate': 4_000_000, 'fps': max_fps}
        self.dropped = 0

    async def start(self):
        if not self.path:
            raise RuntimeError('Native ScreenEncoder helper is not installed')
        args = [str(self.path)] + (['--demo'] if self.demo else []) + (['--fps30'] if self.max_fps==30 else []) + (['--compact'] if self.compact else [])
        self.process = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        self.tasks = [asyncio.create_task(self._frames()), asyncio.create_task(self._diagnostics())]
        try:
            await asyncio.wait_for(self.ready.wait(), 15)
            if self.failure:
                raise RuntimeError(self.failure)
        except BaseException:
            await self.close()
            raise
        return self

    def _command(self, command):
        process = self.process
        if process and process.returncode is None and process.stdin and not process.stdin.is_closing():
            # Commands are tiny and bounded in frequency; never enqueue screen data here.
            if process.stdin.transport.get_write_buffer_size() < 4096:
                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    process.stdin.write(json.dumps(command).encode() + b'\n')

    def request_keyframe(self):
        now = time.monotonic()
        if now - self.last_keyframe_request >= .25:
            self._command({'type': 'keyframe'})
            self.last_keyframe_request = now

    def configure(self, bitrate, fps):
        settings = {'bitrate': max(500_000, min(8_000_000, int(bitrate))), 'fps': max(15, min(self.max_fps, int(fps)))}
        if settings != self.settings:
            self.settings = settings
            self._command({'type': 'configure', **settings})

    def bind_sender(self, sender):
        # aiortc 1.15's Packet path bypasses encode(force_keyframe=...). Connect
        # its PLI/FIR hook to VideoToolbox so packet loss can recover promptly.
        # The pinned-version integration test verifies this private API bridge.
        self.original_keyframe_handler = sender._send_keyframe
        sender._send_keyframe = self.request_keyframe

    def _fail(self, message):
        if not self.failure:
            self.failure = message
        self.ready.set()
        while not self.queue.empty():
            self.queue.get_nowait()
        self.queue.put_nowait(None)

    def _accept(self, header, payload):
        pts = header.get('pts')
        if not isinstance(pts, int) or pts <= self.last_pts:
            raise ValueError('Native timestamps must increase')
        if not payload.startswith(b'\x00\x00\x00\x01'):
            raise ValueError('Native frame is not Annex B H.264')
        self.last_pts = pts
        if self.queue.full():
            self.dropped += self.queue.qsize()
            while not self.queue.empty():
                self.queue.get_nowait()
            self.waiting_keyframe = True
        if self.waiting_keyframe and not header.get('keyframe'):
            self.dropped += 1
            self.request_keyframe()
            return
        self.waiting_keyframe = False
        packet = av.Packet(payload)
        packet.pts = packet.dts = pts
        packet.time_base = Fraction(1, 90000)
        packet.is_keyframe = bool(header.get('keyframe'))
        self.metrics = {**header, 'dropped': self.dropped, **self.settings}
        self.queue.put_nowait(packet)

    async def _frames(self):
        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    await self.process.wait()
                    self._fail(f'Native encoder stopped (exit {self.process.returncode})')
                    return
                header = json.loads(line)
                size = header.get('bytes')
                if header.get('type') != 'frame' or not isinstance(size, int) or not 0 < size < 4_000_000:
                    raise ValueError('Invalid native frame size')
                payload = await self.process.stdout.readexactly(size)
                self._accept(header, payload)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._fail(f'Native video failed: {error}')

    async def _diagnostics(self):
        try:
            while line := await self.process.stderr.readline():
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeError):
                    continue  # Apple frameworks may emit their own diagnostic lines.
                if not isinstance(message, dict): continue
                if message.get('type') == 'ready':
                    if message.get('hardware') is not True:
                        raise ValueError('Helper did not confirm hardware encoding')
                    self.metrics.update(message)
                    self.ready.set()
                elif message.get('type') == 'error':
                    self._fail(str(message.get('message', 'Native encoder error')))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._fail(f'Native encoder diagnostics failed: {error}')

    async def recv(self):
        if self.readyState != 'live' or self.failure:
            raise MediaStreamError
        packet = await self.queue.get()
        if packet is None:
            raise MediaStreamError
        return packet

    async def close(self):
        super().stop()
        process = self.process
        if process and process.returncode is None:
            if process.stdin:
                process.stdin.close()
            try:
                await asyncio.wait_for(process.wait(), 2)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self._fail(self.failure or 'Native encoder closed')
