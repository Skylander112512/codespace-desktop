Codespace Desktop 0.2.12 — Apple Silicon Mac / macOS 14+

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
microphone. This version sends no sound. Closing the host ends access. There is no startup service.

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

Sound removed in 0.2.12 to address lag:
This host is video-only and does not send an audio track, including silence.
If you want sound, go back to the previous published v0.2.10 Mac host:
https://github.com/Skylander112512/codespace-desktop/releases/tag/v0.2.10
Close this host before opening that version. Older sound behavior may bring
back the lag. The current viewer remains compatible with its Sound button.

Video stability (viewer and host 0.2.12+):
The viewer keeps the relay picture until direct frames are decoding, requests
a fresh frame after a stall, and automatically retries sustained freezes.
Retry video provides a manual retry. A video reconnect releases input. Wi-Fi recovery now prioritizes retaining/restoring your
selected FPS while adjusting picture bitrate first.


Performance diagnostics (0.2.12):
Close the ordinary host and open Start Diagnostics.command to record local
performance numbers once every two seconds. The ordinary launcher leaves
diagnostics off. Logs contain FPS, packet loss, encode/decode/buffer times,
video bitrate, network RTT where available, and direct/sound status. They
never contain screen images, keystrokes, clipboard text, access keys or URLs.
Files stay in ~/Library/Application Support/Codespace Desktop/diagnostics.jsonl
and diagnostics.previous.jsonl, each bounded to approximately 512 KB.
Stop the diagnostic host to stop logging; use the ordinary launcher next
time. Current viewers provide basic metrics; 0.2.12 viewers provide extra
receive bitrate, jitter, dropped-frame and processing-time metrics.
These measurements locate likely bottlenecks but are not a measurement of
complete click-to-photon latency. Logs are not uploaded automatically.
