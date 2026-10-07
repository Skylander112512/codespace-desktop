Codespace Desktop 0.2.3 — Apple Silicon Mac / macOS 14+

Keep these files together. Open Start Mac Host.command.

First launch only: enter the Codespaces viewer URL and the Mac host key from
npm start. After a successful connection, the Mac remembers both privately.
Future launches connect automatically. Leave the window open while using it.
Open Change Connection.command if your Codespace address or host key changes.

On the Chromebook, open the Codespaces viewer and enter your chosen code.
Set your own code once by running npm run set-code in Codespaces.
The public download contains no personal code or host credentials.

Screen Recording and Accessibility must be enabled for the launching host /
Terminal in System Settings > Privacy & Security. Restart after granting them.
The native ScreenEncoder helper shares only your main display; it records no
microphone or audio. Closing the host ends access. There is no startup service.

Video defaults to Smooth (up to 60 FPS). Some browsers require reduced
resolution for 60 FPS; select Sharper for up to 720p at 30 FPS on those browsers.
Optional 720p / 60 FPS and 1080p / 60 FPS choices are in the Video menu.
They require the updated host and a supported browser; Smooth stays default.
Connection details shows measured FPS and encoding/decoding/buffering time.
Internet delay and browser/network limits still apply. A compatibility relay
is retained when peer video cannot connect.

Source and instructions:
https://github.com/Skylander112512/codespace-desktop
