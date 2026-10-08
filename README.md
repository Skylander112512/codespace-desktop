# Codespace Desktop

Control your Mac from a Chromebook browser using a GitHub Codespaces project. No Chromebook app, extension, Linux environment, or local installation is needed. The server runs **inside Codespaces**, and you open its forwarded browser page to control your Mac.

This is a working prototype, not a signed commercial remote-desktop product. It includes a Mac host, browser viewer, authenticated signaling server, and a compatibility video relay. It must still be tested on your actual Mac/Chromebook networks.

## 1. Open the project

Open [Skylander112512/codespace-desktop](https://github.com/Skylander112512/codespace-desktop) on the Chromebook. Select **Code → Codespaces** and open your existing Codespace, or create one on `main`.

For an existing Codespace, stop `npm start` with Ctrl+C, then run `git pull --ff-only` before restarting it. Download the matching Mac host from the [latest release](https://github.com/Skylander112512/codespace-desktop/releases/latest). Version **0.2.8** adds a Text transfer box for sending/getting clipboard text and fixes rejected connections when Codespaces rewrites the viewer origin to `https://localhost:3000`. Update the viewer and Mac host to 0.2.8 to use text transfer. Version **0.2.7** adds a start-page choice: stay in this tab or open an about:blank wrapper (Mac host 0.2.6 is unchanged). Version **0.2.6** adds the **backtick (`) shortcut** to toggle Game mouse while keeping movement keys held (update both ends). Version **0.2.5** adds **Game mouse** for relative camera movement (Esc releases the pointer); update both the viewer and Mac host. Version **0.2.4** keeps the Mac host waiting and reconnecting while Codespaces is stopped or the network is offline. Open it before leaving; when you start the same Codespace and `npm start` later, it reconnects automatically. The browser also retries while its tab remains open. Version **0.2.3** adds optional **720p · 60 FPS** and **1080p · 60 FPS** modes; Smooth remains the default. Install the matching Mac host to use the new modes. Version **0.2.2** also keeps clicks and keys working with older viewers by enabling the separate motion channel only when the viewer supports it. Refresh the viewer after updating Codespaces. Version **0.2.1** fixes Mac clicks by preserving matching click counts and event numbers on mouse press, drag, and release. Version **0.2.0** added Apple hardware video encoding, adaptive quality, faster mouse delivery, a private Chromebook code, and saved Mac connection details. Replace the old Mac folder, including its bundled executable; replacing only the launcher does not update the host.

### Forking or using another GitHub account

A fork contains the application, not your private code or Mac pairing. Create a Codespace from the fork and follow the server setup below to choose a code and make port 3000 Public. On the Mac, open **Change Connection.command**, enter that new Codespace's viewer URL and its Mac host key once, then connect from the Chromebook with the code chosen in that Codespace. Even if you choose the same code, the address and Mac key must match the new Codespace. Each Codespace has its own settings. To keep using the existing running Codespace, simply open its public viewer URL; the viewer itself does not require the same GitHub login.

The devices can be on different Wi-Fi networks. Keep the Mac awake, the host running, and the Codespace running. Restrictive networks may require TURN or use the slower compatibility relay described below.

## 2. Start the server in Codespaces

In the Codespaces terminal:

```sh
npm ci
npm run set-code
npm start
```

Choose your own 5–12 digit code when prompted; it is hidden and stored as a salted hash only in your ignored `.secrets.json`. Other people using this public repository choose their own code in their own Codespace. No shared code is included in GitHub. Skip `npm run set-code` if you prefer the generated long viewer key.

`npm start` displays your viewer address and separate **Mac host key** for one-time Mac setup. These are project access keys, not GitHub tokens. Keep them private. Run `npm run set-code` again and restart the server to change your Chromebook code.

In the **Ports** panel, find port **3000**, right-click it, and select **Port Visibility → Public**. Keep the application protocol at the default HTTP; GitHub supplies the public **HTTPS** address. Open that forwarded HTTPS address in a full browser tab (not the embedded Simple Browser). This is still your Codespaces-hosted application.

The page itself is publicly reachable so your Mac can connect from another network. Desktop access requires the keys. Your GitHub account or organization must allow public forwarded ports; if it does not, this version cannot connect the Mac without changes.

## 3. Start the Mac host

For the supplied **Apple Silicon Mac download (macOS 14 or newer)**, extract the ZIP, keep its files together, and open **Start Mac Host.command**. The bundled executable contains Python and its dependencies; you do not need to install them separately. The executable is ad-hoc signed, not notarized by Apple. If macOS blocks it, review the source before deciding whether to allow it in **System Settings → Privacy & Security**.

When the host prompts for permissions, enable it or its launching Terminal under:

- **Privacy & Security → Screen & System Audio Recording** (may be called Screen Recording).
- **Privacy & Security → Accessibility** (for keyboard and mouse).

Restart the host after granting permissions. On the first launch only, paste the **Codespaces viewer URL**, then the **Mac host key**. A successful connection is saved privately on this Mac. Future launches connect automatically and wait for the Chromebook code; no Mac code entry is needed. Leave this window running.

Saved settings are in `~/Library/Application Support/Codespace Desktop/connection.json`, readable only by your Mac account. To change them, run the host with `--setup`. Never upload that file. Your Mac must remain awake and connected to the internet; keep a laptop plugged in with its lid open.

For an Intel Mac or if using the source instead, install Python 3.12+ from [python.org](https://www.python.org/downloads/macos/), then run `mac/Start Mac Host.command` from the project. That launcher creates an isolated Python environment and installs the dependencies. The Intel route has not been tested here.

## 4. Connect from the Chromebook

Enter your **chosen code** (or the long viewer key if you skipped code setup) into the Codespaces viewer page and select **Connect to Mac**. Click the desktop to focus it. Mouse, dragging, scrolling, keyboard input, and a Command-Tab button are provided. `Ctrl → ⌘` maps Chromebook Control shortcuts to Mac Command shortcuts; turn it off for actual Control keys. Some browser/ChromeOS shortcuts are reserved by the Chromebook.

**Disconnect** ends the viewer session. Stopping the Mac host with **Ctrl+C**, closing its Terminal window, or stopping Codespaces ends access. No background service or login item is installed. The Mac host automatically reconnects after temporary outages. It retries after 2, 4, 8, 16, 32, then 60 seconds, and keeps trying until stopped. Start the same Codespace, run `npm start`, and keep port 3000 Public when you are ready. It cannot start a stopped Codespace for you. No screen capture runs while no viewer is connected. Incorrect host keys still stop with a setup message.

## Game camera controls (Roblox and similar games)

Update your Codespace files with `git pull --ff-only`, refresh the viewer, and use Mac host **0.2.6 or newer**. Open/focus the game on the Mac, then press the **backtick (`) key below Esc** while the remote screen is focused, or click **Game mouse** in the viewer toolbar. Press backtick again to toggle it off without releasing your held walking keys. This key is reserved for Game mouse while connected; it is not sent to Roblox. The browser locks/hides the pointer and sends relative turning movements; the Mac posts centered mouse events with explicit horizontal/vertical deltas. **Esc** unlocks the pointer and releases all held input for ordinary desktop use. If Game mouse is disabled, the connected Mac host has not announced support; update/restart it first.

Use the game's normal camera mode: first person or Shift Lock where supported, or hold the right mouse button to orbit in a third-person camera. Game mouse supplies relative input; it does not change the game's own camera rules. Press Esc before using menus or moving the pointer freely. Losing focus, changing video mode, or disconnecting releases the lock and held input; click Game mouse again afterward. Short idle periods do not disable turning.

Relative events are summed over each short send interval and use the same bounded low-latency motion transport as desktop movement. Native event tests intercept posts and verify nonzero deltas, centered positions, right-drag metadata, release, and stale-event rejection; automated tests do not control Roblox. Actual game acceptance still needs testing on your Mac—games using different input paths may need further adjustment. Video quality/FPS and the foreground reconnect feature are unchanged.

## Confirmed Codespaces fix in 0.1.2

The Codespaces tunnel rewrites browser WebSocket `Origin` and `Host` headers to `http://localhost:3000` / `localhost:3000`. The original server rejected those requests with HTTP 403, causing the viewer to immediately return to login. The server now accepts that exact rewrite only from the loopback tunnel, on the configured port, with the expected public `X-Forwarded-Host`. Other origins still fail, and both roles still require their separate keys.

## If the connection fails

The viewer stays on the key form until the server accepts the key. A failed connection leaves a readable error and close code. **Connection details** records authentication, the first displayed frame, direct-video state, and disconnects without storing keys.

- **HTTP 302 / GitHub sign-in on the Mac:** the Codespace may be stopped or port 3000 private. The host keeps waiting. In Codespaces → Ports, set it to **Public**. Recheck after restarting the Codespace. Browser sign-in does not sign in the standalone Mac host.
- **4003:** use your code in the browser. If the saved Mac key changed, run the Mac host with `--setup`.
- **4009 / already connected:** close the other host or viewer first.
- **1006 / Codespace offline:** leave the new Mac host open; it retries automatically. Start the Codespace and `npm start` when ready. The next retry may take up to a minute, plus connection time. Reload the viewer after updating its files.
- **Screen capture failed:** enable Screen Recording for the launching host/Terminal and restart it.
- **Video works but input does not:** enable Accessibility for the host/Terminal and restart it. The host reports when that permission is off.

The Mac window now stays open on errors. Its timestamped messages show capture, first-frame delivery, ICE, and direct-video states. The Codespaces terminal records socket close codes. The browser connection details and Mac host banner show 0.2.8.

## Latency and network behavior

- The Apple Silicon download uses **ScreenCaptureKit + VideoToolbox hardware H.264**, fitting the main display into the selected video size at up to 60 FPS. **Smooth · 60 FPS** is the default: browsers negotiating H.264 level 3.1 receive up to 854 × 480 at 60 FPS to stay within their declared capability. Choose **Sharper · 720p** for up to 720p at 30 FPS on those browsers. The optional **720p · 60 FPS** and **1080p · 60 FPS** choices request up to 1280 × 720 and 1920 × 1080, respectively, with aspect ratio preserved. The browser checks its [WebRTC decoder capabilities](https://www.w3.org/TR/media-capabilities/) before declaring [higher receive limits](https://www.rfc-editor.org/rfc/rfc6184.html) (H.264 level 3.2 / 4.2). If it cannot confirm support, the host uses a compatible smaller size and explains this in Connection details. 1080p starts at 10 Mbps and 720p60 at 6 Mbps; both adapt to connection conditions. These choices are targets, not a fixed frame-rate guarantee. Actual FPS depends on the network and screen activity. Missing/unsupported hardware falls back to software video. When peer connectivity works, video avoids Codespaces.
- The native helper allows one encode/write in flight. The Python queue holds at most two encoded frames, discards stale dependent frames, and asks for a new keyframe on overflow or browser picture-loss requests.
- Receiver feedback gradually adjusts bitrate and frame rate under loss, decoding pressure, or video buffering. The browser requests minimal buffering where supported; browsers and networks still control actual delay.
- Mouse motion uses an unordered channel without retransmissions, while keys and clicks remain reliable. Sequence guards reject late movements and stale events after a release.
- **Connection details** shows received FPS, codec, peer/TURN route, hardware encode time, decode time, and video-buffer delay. These are separate measurements, not an end-to-end latency estimate.
- When direct connectivity fails, HTTPS/WebSocket relay video runs through Codespaces, at up to 15 fps with compressed JPEG frames. Only one frame is in flight at a time; old frames do not accumulate. On long-distance or slow networks this will feel less smooth.
- The displayed milliseconds measure **control round-trip time**, not complete screen latency. No particular latency or frame rate is guaranteed. The prototype does not include audio, clipboard sync, file transfer, monitor selection, or unattended login-screen access.
- Use **compatibility relay** to force fallback. Reconnect to retry direct WebRTC. Both computers initiate outbound connections; no router port forwarding is required. Network policies may still block the service.
- Native capture uses the main display. Software/compatibility capture uses the first display, mapped to main-display input coordinates; keep the main display first when using fallback. Other monitor arrangements are not tested.
- Codespaces must stay running. It has idle/lifetime limits and usage quotas. This is intended for interactive sessions, not an always-on host.

For a better chance of smooth video on networks that require a relay, configure your own nearby **TURN** service before starting the server. Set `ICE_SERVERS_JSON` to a JSON array of WebRTC ICE server definitions, for example a STUN entry and a TURN entry with `urls`, `username`, and `credential`. The same list is delivered only to authenticated peers. Store it in a Codespaces secret; do not commit relay credentials. TURN service is not included or provisioned by this project. Codespaces' TCP port forwarding is not itself a TURN service.

## Access and privacy

Keys are generated randomly on first launch and stored in `.secrets.json` with owner-only file permissions. The file is git-ignored. The viewer accepts your chosen code or its long recovery key; the Mac uses a separate saved host key; one connection of each role is allowed. A second connection cannot displace an existing one. Keys are sent in WebSocket messages, not URLs or browser storage. The viewer keeps its code only in tab memory to reconnect after an outage; Disconnect clears it. Refreshing or closing the tab requires entering the code again. WebRTC transport is encrypted. In fallback mode, TLS protects each hop, but the Codespaces relay handles the screen frames in memory; it is not end-to-end encrypted through that relay. No session recording is implemented.

Codes have **no incorrect-attempt lockout**. A short numeric code is easier to guess than the generated long viewer key; choose a longer code if this matters for your deployment. Connection-count and message-size limits bound server resources.

Only give the code and keys to yourself. Anyone with the viewer code or key can control the running host. To revoke keys: stop the server, delete `.secrets.json`, restart the server, and enter the new keys on both devices. The source repository can be public. Never commit `.secrets.json` or TURN credentials; enable account protection on GitHub.

## Verification and development

```sh
npm ci
npm test
```

The server tests cover authentication, role separation, duplicate-connection protection, cross-origin rejection, secret-file denial, message routing, and disconnect events.

The Python tests use an animated **synthetic screen** and simulated input. They never capture or control the real Mac:

```sh
node test/run-test-server.mjs
# In another terminal, after installing mac/requirements.txt in a venv:
python test/test_host.py -v
```

To test native hardware encoding on Apple Silicon without reading your desktop:

```sh
mac/native/build.sh
python test/test_native_video.py -v
python test/test_latency.py -v
```

The native test produces an animated synthetic frame, verifies real H.264 decoding, frame pacing, keyframe recovery, and WebRTC transport. The source launcher uses software unless the helper has been built. Use `--native-demo` for an interactive synthetic hardware session and `--software` to force the older encoder. The release build script is `scripts/build-mac.sh`; it requires the Python dependencies, PyInstaller, and Apple Command Line Tools.

These tests verify WebRTC video, data-channel messages, relay JPEG delivery, input release on disconnect, and viewer reconnection. The synthetic server uses fixed public test keys and listens only on localhost. **Do not deploy the synthetic server or forward its port publicly.** Deploy `npm start` only.

## References

- [GitHub Codespaces port forwarding](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace)
- [Codespaces lifecycle](https://docs.github.com/en/codespaces/about-codespaces/understanding-the-codespace-lifecycle)
- [WebRTC and TURN](https://webrtc.org/getting-started/turn-server)
- [aiortc API](https://aiortc.readthedocs.io/en/latest/api.html)


## Choose how to open the viewer
On arrival, choose **Stay in this tab** for the usual connection screen, or **Cloak** to open a new `about:blank` tab titled Google Classroom. Once the embedded viewer loads, the original tab goes to `https://classroom.google.com/`. Enter your existing connection code in the new tab; it is never copied into a URL or sent to Classroom. Pop-up blocking or loading failure leaves the original page available. If you select Stay while loading, the pending launch is canceled.

This is a tab-appearance feature, **not a way to hide from GoGuardian or other device/network monitoring**. The viewer still connects to its normal server. Browser-managed restrictions can still apply. The same-origin wrapper retains fullscreen and autoplay; no external site is allowed to embed the viewer. Blank-tab support first shipped as a website-only update in 0.2.7. The 0.2.8 text-transfer feature requires the updated Mac host too.

The about:blank/iframe pattern was researched in [Interstellar's settings](https://github.com/UseInterstellar/Interstellar/blob/main/static/assets/js/settings.js); this implementation is independent and does not include their proxy or scripts.


## Transfer clipboard text
Use viewer and Mac host **0.2.8 or newer**, connect, and click **Text transfer**. Paste or type in the box and choose **Send to Mac** to replace the Mac clipboard, then paste in the Mac app with ⌘V. To move text the other way, copy it on the Mac, choose **Get from Mac**, then **Copy text**. If browser clipboard permission is unavailable, the text is selected so you can press Ctrl+C (⌘C on a Mac).

Transfers happen only when requested, are plain text (up to 16 KB UTF-8), and use the authenticated connection. Clipboard contents are not added to connection logs or saved to browser storage. Opening the panel releases remote keys so typing stays in the box. This does not type or execute the transferred text on the Mac automatically. Old hosts leave Send/Get disabled until updated.
