"""Foreground-only Mac host. No listening ports, shell execution, or startup service."""
import argparse
import asyncio
import contextlib
import getpass
import io
import json
import math
import ssl
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from urllib.parse import urlsplit

from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer, VideoStreamTrack
from av import VideoFrame
from PIL import Image, ImageDraw
from websockets.asyncio.client import connect
import certifi


KEYS = dict(zip(
    'KeyA KeyS KeyD KeyF KeyH KeyG KeyZ KeyX KeyC KeyV IntlBackslash KeyB KeyQ KeyW KeyE KeyR KeyY KeyT Digit1 Digit2 Digit3 Digit4 Digit6 Digit5 Equal Digit9 Digit7 Minus Digit8 Digit0 BracketRight KeyO KeyU BracketLeft KeyI KeyP Enter KeyL KeyJ Quote KeyK Semicolon Backslash Comma Slash KeyN KeyM Period Tab Space Backquote Backspace'.split(),
    range(52)))
KEYS.update({'Escape':53,'MetaLeft':55,'MetaRight':54,'ShiftLeft':56,'ShiftRight':60,'CapsLock':57,
             'AltLeft':58,'AltRight':61,'ControlLeft':59,'ControlRight':62,'Delete':117,
             'Home':115,'End':119,'PageUp':116,'PageDown':121,'ArrowLeft':123,'ArrowRight':124,
             'ArrowDown':125,'ArrowUp':126,'F1':122,'F2':120,'F3':99,'F4':118,'F5':96,'F6':97,
             'F7':98,'F8':100,'F9':101,'F10':109,'F11':103,'F12':111})


class MacInput:
    def __init__(self, demo=False):
        self.demo = demo
        self.keys = set()
        self.buttons = set()
        self.last_input = time.monotonic()
        self.point = (0, 0)
        if not demo:
            import Quartz
            self.q = Quartz
            self.bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())

    def flags(self):
        q = self.q
        flags = 0
        for prefix, flag in [('Shift',q.kCGEventFlagMaskShift),('Control',q.kCGEventFlagMaskControl),
                             ('Alt',q.kCGEventFlagMaskAlternate),('Meta',q.kCGEventFlagMaskCommand)]:
            if any(key.startswith(prefix) for key in self.keys): flags |= flag
        return flags

    def keyboard(self, code, down):
        if code not in KEYS: return
        if down: self.keys.add(code)
        else: self.keys.discard(code)
        if self.demo: return
        q = self.q
        event = q.CGEventCreateKeyboardEvent(None, KEYS[code], down)
        q.CGEventSetFlags(event, self.flags())
        q.CGEventPost(q.kCGHIDEventTap, event)

    def mouse(self, action, button=0):
        if button not in (0,1,2): return
        if action == 'down': self.buttons.add(button)
        if action == 'up': self.buttons.discard(button)
        if self.demo: return
        q = self.q
        mapped = {0:q.kCGMouseButtonLeft,1:q.kCGMouseButtonCenter,2:q.kCGMouseButtonRight}[button]
        kinds = {'down':{0:q.kCGEventLeftMouseDown,1:q.kCGEventOtherMouseDown,2:q.kCGEventRightMouseDown},
                 'up':{0:q.kCGEventLeftMouseUp,1:q.kCGEventOtherMouseUp,2:q.kCGEventRightMouseUp}}
        if action == 'move':
            if self.buttons:
                button = min(self.buttons)
                mapped = {0:q.kCGMouseButtonLeft,1:q.kCGMouseButtonCenter,2:q.kCGMouseButtonRight}[button]
                kind = {0:q.kCGEventLeftMouseDragged,1:q.kCGEventOtherMouseDragged,2:q.kCGEventRightMouseDragged}[button]
            else: kind=q.kCGEventMouseMoved
        else: kind=kinds[action][button]
        event=q.CGEventCreateMouseEvent(None,kind,self.point,mapped)
        q.CGEventSetFlags(event,self.flags())
        q.CGEventPost(q.kCGHIDEventTap,event)

    def release(self):
        for code in list(self.keys): self.keyboard(code,False)
        for button in list(self.buttons): self.mouse('up',button)

    def handle(self, msg):
        self.last_input=time.monotonic()
        action=msg.get('action')
        if action=='release': self.release()
        elif action=='key' and isinstance(msg.get('down'),bool): self.keyboard(msg.get('code'),msg['down'])
        elif action=='tap':
            self.keyboard(msg.get('code'),True); self.keyboard(msg.get('code'),False)
        elif action=='shortcut' and msg.get('code')=='Tab':
            self.keyboard('MetaLeft',True); self.keyboard('Tab',True)
            self.keyboard('Tab',False); self.keyboard('MetaLeft',False)
        elif action in ('move','down','up'):
            x,y=msg.get('x'),msg.get('y')
            if not all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in (x,y)): return
            if not self.demo:
                b=self.bounds
                self.point=(b.origin.x+x*(b.size.width-1),b.origin.y+y*(b.size.height-1))
            self.mouse(action,msg.get('button',0))
        elif action=='scroll':
            dx,dy=msg.get('dx',0),msg.get('dy',0)
            if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (dx,dy)): return
            if not self.demo:
                q=self.q
                event=q.CGEventCreateScrollWheelEvent(None,q.kCGScrollEventUnitPixel,2,
                    -int(max(-1000,min(1000,dy))),-int(max(-1000,min(1000,dx))))
                q.CGEventSetFlags(event,self.flags()); q.CGEventPost(q.kCGHIDEventTap,event)


class Capture:
    def __init__(self,demo=False):
        self.demo=demo
        self.pool=ThreadPoolExecutor(max_workers=1)
        self.sct=None
        self.cached=None
        self.cached_at=0

    def grab(self):
        now=time.monotonic()
        if self.cached is not None and now-self.cached_at<1/30: return self.cached
        if self.demo:
            img=Image.new('RGB',(1280,720),'#172b40')
            draw=ImageDraw.Draw(img)
            draw.text((70,70),'Codespace Desktop • synthetic test screen',fill='white',font_size=36)
            draw.text((70,140),f'Time: {now:.2f}',fill='#b7f5c8',font_size=28)
            x=int(now*140)%1100
            draw.rectangle((x,260,x+120,380),fill='#b7f5c8')
        else:
            if self.sct is None:
                import mss
                self.sct=mss.mss()
            shot=self.sct.grab(self.sct.monitors[1])
            img=Image.frombytes('RGB',shot.size,shot.bgra,'raw','BGRX')
            img.thumbnail((1280,720),Image.Resampling.BILINEAR)
            # Video encoders require even dimensions.
            img=img.crop((0,0,img.width-img.width%2,img.height-img.height%2))
        self.cached=img; self.cached_at=now
        return img

    async def image(self):
        return await asyncio.get_running_loop().run_in_executor(self.pool,self.grab)

    async def jpeg(self):
        def encode():
            out=io.BytesIO(); self.grab().save(out,format='JPEG',quality=55)
            return out.getvalue()
        return await asyncio.get_running_loop().run_in_executor(self.pool,encode)

    def close(self):
        if self.sct:self.pool.submit(self.sct.close).result()
        self.pool.shutdown(wait=True)


class ScreenTrack(VideoStreamTrack):
    def __init__(self,capture):
        super().__init__(); self.capture=capture; self.started=time.monotonic()
        self.next_frame=self.started

    async def recv(self):
        await asyncio.sleep(max(0,self.next_frame-time.monotonic()))
        self.next_frame=max(self.next_frame+1/30,time.monotonic())
        frame=VideoFrame.from_image(await self.capture.image())
        frame.pts=int((time.monotonic()-self.started)*90000)
        frame.time_base=Fraction(1,90000)
        return frame


class Host:
    def __init__(self,demo=False):
        self.capture=Capture(demo); self.controls=MacInput(demo)
        self.pc=None; self.channel=None; self.ws=None; self.active=False; self.rtc=False
        self.tasks=set(); self.ice_servers=[]; self.ack=asyncio.Event()
        self.ack.set()

    async def send(self,msg):
        if self.ws: await self.ws.send(json.dumps(msg))

    async def end_session(self):
        self.active=False; self.rtc=False
        for task in self.tasks:task.cancel()
        for task in self.tasks:
            with contextlib.suppress(asyncio.CancelledError,Exception): await task
        self.tasks.clear()
        if self.pc:await self.pc.close(); self.pc=None
        self.channel=None; self.controls.release(); self.ack.set()

    async def start_session(self):
        await self.end_session(); self.active=True
        print('Viewer connected. Close this window or press Ctrl+C to stop access.',flush=True)
        self.tasks={asyncio.create_task(self.relay()),asyncio.create_task(self.negotiate())}

    async def negotiate(self):
        try:
            servers=[RTCIceServer(**server) for server in self.ice_servers]
            pc=RTCPeerConnection(RTCConfiguration(iceServers=servers)); self.pc=pc
            pc.addTrack(ScreenTrack(self.capture))
            channel=pc.createDataChannel('control',ordered=True); self.channel=channel
            @channel.on('message')
            def data(message):
                if not self.active or not isinstance(message,str) or len(message)>8192:return
                try:
                    msg=json.loads(message)
                    if not isinstance(msg,dict):return
                    if msg.get('type')=='input':self.controls.handle(msg)
                    elif msg.get('type')=='ping':channel.send(json.dumps({'type':'pong','at':msg.get('at')}))
                except (ValueError,TypeError,KeyError):pass
            @pc.on('connectionstatechange')
            async def connection_state():
                if pc.connectionState in ('failed','disconnected','closed'):
                    self.rtc=False; self.controls.release()
            await pc.setLocalDescription(await pc.createOffer())
            await self.send({'type':'offer','sdp':pc.localDescription.sdp,'iceServers':self.ice_servers})
        except asyncio.CancelledError:raise
        except Exception as error:
            print(f'Direct connection unavailable: {type(error).__name__}. Relay remains available.',flush=True)
            await self.send({'type':'status','text':'Direct connection unavailable. Using compatibility relay.'})

    async def relay(self):
        try:
            while self.active:
                if self.rtc:
                    await asyncio.sleep(.15); continue
                try:await asyncio.wait_for(self.ack.wait(),timeout=3)
                except asyncio.TimeoutError:continue  # Wait, do not pile up old frames.
                frame=await self.capture.jpeg()
                self.ack.clear()
                await self.ws.send(frame)
                await asyncio.sleep(1/15)
        except asyncio.CancelledError:raise
        except Exception as error:
            print(f'Screen capture failed: {type(error).__name__}',flush=True)
            await self.send({'type':'status','text':'Mac screen capture failed. Check Screen Recording permission and restart the host.'})

    async def watchdog(self):
        while True:
            await asyncio.sleep(1)
            # Release held buttons/keys after a dead connection, including a lost browser focus event.
            if time.monotonic()-self.controls.last_input>10:self.controls.release()

    async def run(self,url,key):
        watchdog=asyncio.create_task(self.watchdog())
        try:
            tls=ssl.create_default_context(cafile=certifi.where()) if url.startswith('wss:') else None
            async with connect(url,ssl=tls,max_size=256*1024,max_queue=8,compression=None,ping_interval=15,ping_timeout=15) as ws:
                self.ws=ws
                await self.send({'type':'auth','role':'host','key':key})
                async for raw in ws:
                    if not isinstance(raw,str):continue
                    msg=json.loads(raw)
                    kind=msg.get('type')
                    if kind=='authenticated':
                        self.ice_servers=msg.get('iceServers',[])
                        print('Connected to Codespaces. Waiting for your Chromebook.',flush=True)
                    elif kind=='viewer-ready':await self.start_session()
                    elif kind=='peer-left':
                        await self.end_session();print('Viewer disconnected. Waiting.',flush=True)
                    elif kind=='answer' and self.pc:
                        try:await self.pc.setRemoteDescription(RTCSessionDescription(sdp=msg['sdp'],type='answer'))
                        except Exception:await self.send({'type':'status','text':'Using compatibility relay.'})
                    elif kind=='input' and self.active:
                        with contextlib.suppress(ValueError,TypeError,KeyError):self.controls.handle(msg)
                    elif kind=='frame-ack':self.ack.set()
                    elif kind=='mode':self.rtc=bool(msg.get('rtc')) and self.pc is not None and self.pc.connectionState=='connected'
                    elif kind=='ping':await self.send({'type':'pong','at':msg.get('at')})
        finally:
            watchdog.cancel()
            with contextlib.suppress(asyncio.CancelledError):await watchdog
            await self.end_session();self.capture.close();self.ws=None


def websocket_url(value):
    parsed=urlsplit(value.strip())
    local=parsed.hostname in ('localhost','127.0.0.1','::1')
    if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Enter an https:// Codespaces viewer address.')
    if parsed.scheme=='http' and not local:raise ValueError('Remote connections require HTTPS.')
    if parsed.path not in ('','/') or parsed.query or parsed.fragment:raise ValueError('Use the viewer address without extra paths or parameters.')
    return ('wss' if parsed.scheme=='https' else 'ws')+'://'+parsed.netloc+'/ws'


def main():
    parser=argparse.ArgumentParser(description='Codespace Desktop Mac host')
    parser.add_argument('--demo',action='store_true',help='Synthetic test screen; never reads or controls the real desktop')
    args=parser.parse_args()
    print('\nCodespace Desktop — Mac host\nKeep this window open while connected. Ctrl+C stops access.\n')
    if not args.demo:
        if sys.platform!='darwin':raise SystemExit('This host requires macOS. Use --demo only for synthetic testing.')
        import Quartz
        if not Quartz.CGPreflightScreenCaptureAccess():
            Quartz.CGRequestScreenCaptureAccess()
            print('Screen Recording permission is required. Enable this host / Terminal in System Settings → Privacy & Security → Screen & System Audio Recording, then restart it.')
            raise SystemExit(1)
        url=websocket_url(input('Codespaces viewer URL: '))
    key=getpass.getpass('Mac host key (hidden while typing): ').strip()
    if len(key)<32:raise SystemExit('Use the full Mac host key printed by npm start, not a GitHub token.')
    print('\nStarting foreground remote access with your host key. No automatic startup is installed.\n',flush=True)
    asyncio.run(Host(args.demo).run(url,key))


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nAccess stopped.')
    except Exception as error:
        print(f'\nStopped: {type(error).__name__}: {error}\nCheck the Codespace is running and port 3000 is Public. Restart to reconnect.')
        sys.exit(1)
