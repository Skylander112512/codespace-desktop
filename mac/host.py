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
from native_video import NativeVideoTrack, helper_path
from adaptive import AdaptiveQuality
from video_quality import select_quality
from host_settings import load_settings, save_settings
from PIL import Image, ImageDraw
from websockets.asyncio.client import connect
import certifi
from websockets.exceptions import ConnectionClosed, InvalidStatus

VERSION = '0.2.3'


class DirectConnect(connect):
    def process_redirect(self, exc):
        return exc  # Never follow a GitHub sign-in redirect or send the key elsewhere.


def log(message):
    print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)


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
        self.last_reliable_seq = 0
        self.last_motion_seq = 0
        self.mouse_presses = {}
        self.last_clicks = {}
        self.mouse_event_number = 0
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
        if action == 'move' and self.buttons:button=min(self.buttons)
        if action == 'down':
            now=time.monotonic()
            previous=self.last_clicks.get(button)
            count=1
            if previous and 0<=now-previous[0]<=.5 and math.dist(self.point,previous[1])<=5:
                count=min(3,previous[2]+1)
            self.last_clicks[button]=(now,self.point,count)
            self.mouse_event_number+=1
            self.mouse_presses[button]=(count,self.mouse_event_number)
            self.buttons.add(button)
        metadata=self.mouse_presses.get(button)
        if action == 'up':
            self.buttons.discard(button)
            self.mouse_presses.pop(button,None)
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
        # Quartz defaults a freshly-created mouse-up event to click count 0.
        # Pair press, drag and release explicitly so apps recognize clicks.
        if metadata:
            q.CGEventSetIntegerValueField(event,q.kCGMouseEventClickState,metadata[0])
            q.CGEventSetIntegerValueField(event,q.kCGMouseEventNumber,metadata[1])
        q.CGEventSetFlags(event,self.flags())
        q.CGEventPost(q.kCGHIDEventTap,event)

    def release(self):
        for code in list(self.keys): self.keyboard(code,False)
        for button in list(self.buttons): self.mouse('up',button)

    def handle(self, msg):
        action=msg.get('action')
        seq=msg.get('seq')
        if seq is not None:
            if type(seq) is not int or not 0 < seq <= 2**53-1: return
            if action == 'move':
                after=msg.get('after',0)
                if type(after) is not int or after > self.last_reliable_seq: return
                if seq <= max(self.last_reliable_seq,self.last_motion_seq): return
                self.last_motion_seq=seq
            else:
                if seq <= self.last_reliable_seq: return
                self.last_reliable_seq=seq
        self.last_input=time.monotonic()
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
        self.logged_first=False

    async def recv(self):
        await asyncio.sleep(max(0,self.next_frame-time.monotonic()))
        self.next_frame=max(self.next_frame+1/30,time.monotonic())
        frame=VideoFrame.from_image(await self.capture.image())
        if not self.logged_first:
            log(f'First WebRTC frame encoded from capture ({frame.width}×{frame.height}).')
            self.logged_first=True
        frame.pts=int((time.monotonic()-self.started)*90000)
        frame.time_base=Fraction(1,90000)
        return frame


class Host:
    def __init__(self,demo=False,native=None):
        self.capture=Capture(demo); self.controls=MacInput(demo)
        self.prefer_native=(not demo) if native is None else native
        self.native=None; self.quality=AdaptiveQuality(); self.on_authenticated=None
        self.pc=None; self.channel=None; self.motion=None; self.ws=None; self.active=False; self.rtc=False
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
        if self.native:await self.native.close(); self.native=None
        self.channel=None; self.motion=None; self.controls.release(); self.ack.set()
        self.controls.last_reliable_seq=0; self.controls.last_motion_seq=0

    async def start_session(self):
        await self.end_session(); self.active=True
        print('Viewer connected. Close this window or press Ctrl+C to stop access.',flush=True)
        await self.send({'type':'status','text':f'Mac host {VERSION} connected. Starting screen capture…'})
        self.quality=AdaptiveQuality()
        self.tasks={asyncio.create_task(self.relay()),asyncio.create_task(self.negotiate()),asyncio.create_task(self.telemetry())}

    async def negotiate(self):
        try:
            servers=[RTCIceServer(**server) for server in self.ice_servers]
            pc=RTCPeerConnection(RTCConfiguration(iceServers=servers)); self.pc=pc
            track=ScreenTrack(self.capture)
            if self.prefer_native and helper_path():
                native=NativeVideoTrack(demo=self.capture.demo)
                self.native=native
                try:
                    await native.start()
                    track=native
                    log('Apple hardware H.264 ready: up to 720p / 60 FPS.')
                except asyncio.CancelledError:raise
                except Exception as error:
                    await native.close(); self.native=None
                    log(f'Hardware capture unavailable ({error}); using software video.')
            sender=pc.addTrack(track); self.sender=sender
            if self.native:
                codecs=[codec for codec in sender.getCapabilities('video').codecs
                        if codec.mimeType.lower()=='video/h264' and codec.parameters.get('profile-level-id')=='42e01f']
                if not codecs:raise RuntimeError('Compatible H.264 codec unavailable')
                pc.getTransceivers()[0].setCodecPreferences(codecs)
                self.native.bind_sender(sender)
            log('Screen video track created; gathering direct connection candidates.')
            @pc.on('iceconnectionstatechange')
            def ice_state():log(f'ICE: {pc.iceConnectionState}')
            @pc.on('icegatheringstatechange')
            def ice_gathering():log(f'ICE gathering: {pc.iceGatheringState}')
            channel=pc.createDataChannel('control',ordered=True); self.channel=channel
            @channel.on('message')
            def data(message):
                if not self.active or not isinstance(message,str) or len(message)>8192:return
                try:
                    msg=json.loads(message)
                    if not isinstance(msg,dict):return
                    if msg.get('type')=='input':self.controls.handle(msg)
                    elif msg.get('type')=='ping':channel.send(json.dumps({'type':'pong','at':msg.get('at')}))
                    elif msg.get('type')=='feedback':self.feedback(msg)
                except (ValueError,TypeError,KeyError):pass
            @pc.on('connectionstatechange')
            async def connection_state():
                log(f'Direct video: {pc.connectionState}')
                if pc.connectionState in ('failed','disconnected','closed'):
                    self.rtc=False; self.controls.release()
            offer=await pc.createOffer()
            if self.native:
                # Advertise up to 1080p60 (level 4.2); honor the answer before sending.
                offer=RTCSessionDescription(sdp=offer.sdp.replace('profile-level-id=42e01f','profile-level-id=42e02a'),type='offer')
            await pc.setLocalDescription(offer)
            await self.send({'type':'offer','sdp':pc.localDescription.sdp,'iceServers':self.ice_servers})
        except asyncio.CancelledError:raise
        except ConnectionClosed:return
        except Exception as error:
            log(f'Direct connection unavailable: {type(error).__name__}: {error}. Relay remains available.')
            await self.send({'type':'status','text':'Direct connection unavailable. Using compatibility relay.'})

    def enable_motion_channel(self):
        if self.motion:return
        motion=self.pc.createDataChannel('motion',ordered=False,maxRetransmits=0); self.motion=motion
        @motion.on('message')
        def mouse_motion(message):
            if not self.active or not isinstance(message,str) or len(message)>1024:return
            try:
                msg=json.loads(message)
                if isinstance(msg,dict) and msg.get('type')=='input' and msg.get('action')=='move':
                    self.controls.handle(msg)
            except (ValueError,TypeError,KeyError):pass

    def feedback(self,msg):
        if self.native and not self.native.failure:
            settings=self.quality.update(msg)
            if settings:self.native.configure(*settings)

    async def telemetry(self):
        while self.active:
            await asyncio.sleep(1)
            native=self.native
            if native and native.failure:
                self.rtc=False
                await self.send({'type':'status','text':'Hardware video stopped. Using compatibility relay; reconnect to retry.'})
                await native.close(); self.native=None
            metrics=native.metrics if native and not native.failure else {}
            await self.send({'type':'performance','hardware':bool(metrics),
                'encode_ms':metrics.get('encode_ms'), 'target_fps':metrics.get('fps',30),
                'bitrate':metrics.get('bitrate'), 'dropped':metrics.get('dropped',0)})

    async def relay(self):
        try:
            first = True
            reported_wait = False
            while self.active:
                if self.rtc:
                    await asyncio.sleep(.15); continue
                try:await asyncio.wait_for(self.ack.wait(),timeout=3)
                except asyncio.TimeoutError:
                    if not reported_wait:
                        log('Waiting for browser to acknowledge the screen frame. Check its connection details.')
                        reported_wait = True
                    continue  # Wait, do not pile up old frames.
                reported_wait = False
                frame=await self.capture.jpeg()
                self.ack.clear()
                await self.ws.send(frame)
                if first:
                    log(f'First screen frame sent ({len(frame)} bytes).')
                    first = False
                await asyncio.sleep(1/15)
        except asyncio.CancelledError:raise
        except ConnectionClosed:return
        except Exception as error:
            log(f'Screen capture failed: {type(error).__name__}: {error}')
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
            # A private Codespaces port redirects to GitHub sign-in. A standalone
            # host cannot use the browser's login; report that instead of following it.
            async with DirectConnect(url,ssl=tls,max_size=256*1024,max_queue=8,compression=None,ping_interval=15,ping_timeout=30) as ws:
                self.ws=ws
                await self.send({'type':'auth','role':'host','key':key})
                async for raw in ws:
                    if not isinstance(raw,str):continue
                    msg=json.loads(raw)
                    kind=msg.get('type')
                    if kind=='authenticated':
                        if self.on_authenticated:self.on_authenticated()
                        self.ice_servers=msg.get('iceServers',[])
                        print('Connected to Codespaces. Waiting for your Chromebook.',flush=True)
                    elif kind=='viewer-ready':await self.start_session()
                    elif kind=='peer-left':
                        await self.end_session();print('Viewer disconnected. Waiting.',flush=True)
                    elif kind=='answer' and self.pc:
                        try:
                            if self.native:
                                mode=msg.get('quality','smooth')
                                quality=select_quality(msg['sdp'],mode)
                                original=self.native.original_keyframe_handler
                                await self.native.close(); self.native=None
                                self.sender._send_keyframe=original
                                native=NativeVideoTrack(demo=self.capture.demo,max_fps=quality.fps,height=quality.height,bitrate=quality.bitrate)
                                try:
                                    await native.start()
                                    self.native=native; self.sender.replaceTrack(native); native.bind_sender(self.sender)
                                    self.quality=AdaptiveQuality(max_fps=quality.fps,bitrate=quality.bitrate,max_bitrate=quality.max_bitrate)
                                    text=f'Hardware video: up to {quality.label}.'
                                    requested={'720p60':720,'1080p60':1080}.get(mode,0)
                                    if requested>quality.height:text+=' Your browser reported a lower receive limit; using a compatible size.'
                                    await self.send({'type':'status','text':text});log(text)
                                except Exception:
                                    await native.close(); self.sender.replaceTrack(ScreenTrack(self.capture))
                                    await self.send({'type':'status','text':'Hardware mode unavailable. Using software video.'})
                            await self.pc.setRemoteDescription(RTCSessionDescription(sdp=msg['sdp'],type='answer'))
                            # Old viewers assign every channel to their control
                            # variable. A second channel would swallow clicks.
                            if msg.get('inputProtocol')==2:self.enable_motion_channel()
                        except Exception:await self.send({'type':'status','text':'Using compatibility relay.'})
                    elif kind=='input' and self.active:
                        with contextlib.suppress(ValueError,TypeError,KeyError):self.controls.handle(msg)
                    elif kind=='quality' and self.active:await self.start_session()
                    elif kind=='feedback' and self.active:self.feedback(msg)
                    elif kind=='frame-ack':self.ack.set()
                    elif kind=='mode':self.rtc=bool(msg.get('rtc')) and self.pc is not None and self.pc.connectionState=='connected'
                    elif kind=='ping':await self.send({'type':'pong','at':msg.get('at')})
        except InvalidStatus as error:
            code=error.response.status_code
            if code in (301,302,303,307,308,401,403):
                raise RuntimeError(f'Codespaces blocked the Mac connection (HTTP {code}). In Codespaces → Ports, set port 3000 visibility to Public, then restart this host.') from None
            raise RuntimeError(f'Codespaces returned HTTP {code}. Run npm start and check port 3000.') from None
        except ConnectionClosed as error:
            close=error.rcvd or error.sent
            code=close.code if close else 1006
            reason=close.reason if close else 'Network connection lost'
            raise RuntimeError(f'Connection closed ({code}): {reason}. Check the Codespaces terminal and restart the host.') from None
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
    parser.add_argument('--setup',action='store_true',help='Change the saved Codespaces address and Mac host key')
    parser.add_argument('--software',action='store_true',help='Use the original software encoder')
    parser.add_argument('--native-demo',action='store_true',help='Test hardware encoding with a synthetic screen only')
    args=parser.parse_args()
    if args.native_demo:args.demo=True
    print(f'\nCodespace Desktop — Mac host {VERSION}\nKeep this window open while connected. Ctrl+C stops access.\n')
    if not args.demo:
        if sys.platform!='darwin':raise SystemExit('This host requires macOS. Use --demo only for synthetic testing.')
        import Quartz
        if not Quartz.CGPreflightScreenCaptureAccess():
            Quartz.CGRequestScreenCaptureAccess()
            print('Screen Recording permission is required. Enable this host / Terminal in System Settings → Privacy & Security → Screen & System Audio Recording, then restart it.')
            raise SystemExit(1)
        if hasattr(Quartz, 'CGPreflightPostEventAccess') and not Quartz.CGPreflightPostEventAccess():
            print('Keyboard/mouse permission is OFF. Video can still work. Enable this host / Terminal in System Settings → Privacy & Security → Accessibility, then restart the host.\n')
    saved=None if args.demo or args.setup else load_settings()
    if saved:
        address=saved['url'];key=saved['key']
        print(f'Reconnecting to {address}\nTo change the saved connection, start with --setup.',flush=True)
    else:
        print('One-time Mac setup. Future launches will connect automatically.' if not args.demo else 'Synthetic test connection.')
        address=input('Codespaces viewer URL: ').strip()
        key=getpass.getpass('Mac host key (hidden; saved only on this Mac): ').strip()
    url=websocket_url(address)
    if len(key)<32:raise SystemExit('Use the full Mac host key printed by npm start, not the Chromebook code.')
    print('\nStarting foreground remote access. No automatic startup is installed.\n',flush=True)
    agent=Host(args.demo,native=False if args.software else (True if args.native_demo else None))
    if not args.demo:
        def remember():
            try:save_settings(address,key)
            except OSError:log('Could not save this connection; setup will be needed next launch.')
        agent.on_authenticated=remember
    asyncio.run(agent.run(url,key))


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nAccess stopped.')
    except Exception as error:
        print(f'\nStopped: {type(error).__name__}: {error}\nCheck the Codespace is running and port 3000 is Public. Restart to reconnect. Use --setup if the address or host key changed.')
        sys.exit(1)
