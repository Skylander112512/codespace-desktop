"""On-demand system audio with a bounded 60 ms PCM queue and WebRTC Opus."""
import asyncio
import json
import time
from fractions import Fraction

from av import AudioFrame
from aiortc import AudioStreamTrack
from aiortc.mediastreams import MediaStreamError
from native_video import helper_path

SAMPLES=960
BYTES=SAMPLES*2*2

def audio_helper_path():
    video=helper_path()
    path=video.with_name('SystemAudio') if video else None
    return path if path and path.is_file() else None

class NativeAudioTrack(AudioStreamTrack):
    def __init__(self,demo=False,path=None):
        super().__init__()
        self.demo=demo;self.path=path or audio_helper_path()
        self.process=None;self.tasks=[];self.enabled=False;self.failure=None
        self.ready=asyncio.Event();self.queue=asyncio.Queue(maxsize=3)
        self.pending=bytearray();self.pts=0;self.started=None;self.dropped=0
        self.lock=asyncio.Lock()

    async def enable(self):
        async with self.lock:await self._enable()

    async def _enable(self):
        if self.readyState!='live':raise RuntimeError('Audio session ended. Reconnect the viewer.')
        if self.enabled:return
        if not self.path:raise RuntimeError('SystemAudio helper is missing. Install the complete Mac package.')
        self.failure=None;self.ready.clear();self.enabled=True
        try:
            self.process=await asyncio.create_subprocess_exec(str(self.path),*(['--demo'] if self.demo else []),
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            self.tasks=[asyncio.create_task(self._read()),asyncio.create_task(self._diagnostics())]
            await asyncio.wait_for(self.ready.wait(),15)
            if self.failure:raise RuntimeError(self.failure)
        except BaseException:
            await self._disable();raise

    def _fail(self,message):
        self.failure=message;self.enabled=False;self.ready.set();self._clear()

    def _clear(self):
        self.pending.clear()
        while not self.queue.empty():self.queue.get_nowait()

    def _accept(self,payload):
        self.pending.extend(payload)
        while len(self.pending)>=BYTES:
            chunk=bytes(self.pending[:BYTES]);del self.pending[:BYTES]
            if self.queue.full():self.queue.get_nowait();self.dropped+=1
            self.queue.put_nowait(chunk)

    async def _read(self):
        try:
            while line:=await self.process.stdout.readline():
                header=json.loads(line);size=header.get('bytes')
                if header.get('type')!='audio' or header.get('rate')!=48000 or header.get('channels')!=2 or type(size) is not int or not 0<size<=32768 or size%4:
                    raise ValueError('Invalid system audio frame')
                payload=await self.process.stdout.readexactly(size)
                if self.enabled:self._accept(payload)
            if self.enabled:self._fail('System audio capture stopped. Toggle Sound to retry.')
        except asyncio.CancelledError:raise
        except Exception:self._fail('System audio stream failed. Toggle Sound to retry.')

    async def _diagnostics(self):
        try:
            while line:=await self.process.stderr.readline():
                try:msg=json.loads(line)
                except (ValueError,UnicodeError):continue
                if msg.get('type')=='ready':self.ready.set()
                elif msg.get('type')=='error':self._fail(str(msg.get('message','System audio unavailable')))
        except asyncio.CancelledError:raise
        except Exception:self._fail('System audio capture unavailable.')

    async def recv(self):
        if self.readyState!='live':raise MediaStreamError
        now=time.monotonic()
        if self.started is None:self.started=now
        due=self.started+self.pts/48000
        if now-due>.06:self.started=now-self.pts/48000;due=now
        await asyncio.sleep(max(0,due-now))
        if self.readyState!='live':raise MediaStreamError
        payload=self.queue.get_nowait() if self.enabled and not self.queue.empty() else bytes(BYTES)
        frame=AudioFrame(format='s16',layout='stereo',samples=SAMPLES)
        frame.planes[0].update(payload);frame.sample_rate=48000
        frame.pts=self.pts;frame.time_base=Fraction(1,48000);self.pts+=SAMPLES
        return frame

    async def disable(self):
        async with self.lock:await self._disable()

    async def _disable(self):
        self.enabled=False
        process=self.process
        if process and process.returncode is None:
            if process.stdin:process.stdin.close()
            try:await asyncio.wait_for(process.wait(),2)
            except asyncio.TimeoutError:process.kill();await process.wait()
        for task in self.tasks:task.cancel()
        await asyncio.gather(*self.tasks,return_exceptions=True)
        self.tasks=[];self.process=None;self.failure=None;self._clear()

    async def close(self):
        self.stop();await self.disable()
