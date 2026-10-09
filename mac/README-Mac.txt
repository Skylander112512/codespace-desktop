Codespace Desktop 0.2.9 — Apple Silicon Mac / macOS 14+

Keep these files together. Open Start Mac Host.command.

First launch only: enter the Codespaces viewer URL and the Mac host key from
npm start. After a successful connection, the Mac remembers both privately.
Future launches connect automatically. Leave the window open before leaving.
If Codespaces is off, this host waits and retries (up to once per minute).
Later, start the same Codespace and npm start; keep port 3000 Public.
The Mac connects on its next retry. It cannot start Codespaces for you.
No screen video is captured while waiting for a viewer. Ctrl+C stops retries.
Open Change Connection.command if your Codespace address or host key changes.

On the Chromebook, open the Codespaces viewer and enter your chosen code.
Set your own code once by running npm run set-code in Codespaces.
The public download contains no personal code or host credentials.

Screen Recording and Accessibility must be enabled for the launching host /
Terminal in System Settings > Privacy & Security. Restart after granting them.
The native ScreenEncoder helper shares only your main display; it records no
microphone. System sound is captured only while Sound is on in the viewer. Closing the host ends access. There is no startup service.

Video defaults to Smooth (up to 60 FPS). Some browsers require reduced
resolution for 60 FPS; select Sharper for up to 720p at 30 FPS on those browsers.
Optional 720p / 60 FPS and 1080p / 60 FPS choices are in the Video menu.
They require the updated host and a supported browser; Smooth stays default.
For game camera movement, update/refresh the viewer and press backtick (`),
the key below Esc, with the remote screen focused. It toggles Game mouse
without releasing walking keys. The toolbar button also works.
Both the viewer and Mac host must be 0.2.6 or newer for this behavior.
Esc releases the pointer. Use the game's first-person/Shift Lock or right-drag
camera controls as usual. Game mouse does not change the game's camera rules.
Connection details shows measured FPS and encoding/decoding/buffering time.
Internet delay and browser/network limits still apply. A compatibility relay
is retained when peer video cannot connect.

Source and instructions:
https://github.com/Skylander112512/codespace-desktop

Text transfer (viewer and host 0.2.8+):
Open Text transfer in the viewer. Send to Mac replaces the Mac clipboard;
paste into your Mac app with Cmd+V. Get from Mac reads its clipboard into
the box, then Copy text copies it on the Chromebook. Plain text only, up to
16 KB per request. There is no automatic clipboard synchronization.

Mac sound (viewer and host 0.2.9+):
Keep SystemAudio next to the Mac host executable. Connect and click Sound
in the viewer to enable system audio. No BlackHole installation or audio
device changes are needed. No microphone is captured. Sound requires WebRTC
and starts off again after reconnecting or changing video quality.
If permission is denied, enable Screen & System Audio Recording for this
host/Terminal in macOS Privacy & Security, then restart the host.
