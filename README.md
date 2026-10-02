# Codespace Desktop

Control your Mac from a Chromebook browser using a GitHub Codespaces project. No Chromebook app, extension, Linux environment, or local installation is needed. The server runs **inside Codespaces**, and you open its forwarded browser page to control your Mac.

This is a working prototype, not a signed commercial remote-desktop product. It includes a Mac host, browser viewer, authenticated signaling server, and a compatibility video relay. It must still be tested on your actual Mac/Chromebook networks.

## 1. Put the project in GitHub

Create a **public** repository named `codespace-desktop`. Upload this folder's contents, including `.devcontainer` and `.gitignore`. Do this from your Mac so the Chromebook does not need to download files. Never upload `.secrets.json`, `.venv`, or `node_modules`.

On the Chromebook, open the repository on GitHub. Select **Code → Codespaces → Create codespace on main**. Wait for it to finish starting.

If you uploaded only the visible files, the default Codespace works too; run `npm ci` manually before the next step.

## 2. Start the server in Codespaces

In the Codespaces terminal:

```sh
npm ci
npm start
```

The terminal displays a viewer address, a **viewer key**, and a separate **Mac host key**. These are this project's access keys, not GitHub tokens. Keep them private.

In the **Ports** panel, find port **3000**, right-click it, and select **Port Visibility → Public**. Keep the application protocol at the default HTTP; GitHub supplies the public **HTTPS** address. Open that forwarded HTTPS address in a full browser tab (not the embedded Simple Browser). This is still your Codespaces-hosted application.

The page itself is publicly reachable so your Mac can connect from another network. Desktop access requires the keys. Your GitHub account or organization must allow public forwarded ports; if it does not, this version cannot connect the Mac without changes.

## 3. Start the Mac host

For the supplied **Apple Silicon Mac download (macOS 14 or newer)**, extract the ZIP, keep its files together, and open **Start Mac Host.command**. The bundled executable contains Python and its dependencies; you do not need to install them separately. The executable is ad-hoc signed, not notarized by Apple. If macOS blocks it, review the source before deciding whether to allow it in **System Settings → Privacy & Security**.

When the host prompts for permissions, enable it or its launching Terminal under:

- **Privacy & Security → Screen & System Audio Recording** (may be called Screen Recording).
- **Privacy & Security → Accessibility** (for keyboard and mouse).

Restart the host after granting permissions. Paste the **Codespaces viewer URL**, then the **Mac host key**. The key is hidden while you type. Leave this window running. Your Mac must remain awake and connected to the internet; keep a laptop plugged in with its lid open.

For an Intel Mac or if using the source instead, install Python 3.12+ from [python.org](https://www.python.org/downloads/macos/), then run `mac/Start Mac Host.command` from the project. That launcher creates an isolated Python environment and installs the dependencies. The Intel route has not been tested here.

## 4. Connect from the Chromebook

Paste the **viewer key** into the Codespaces viewer page and select **Connect to Mac**. Click the desktop to focus it. Mouse, dragging, scrolling, keyboard input, and a Command-Tab button are provided. `Ctrl → ⌘` maps Chromebook Control shortcuts to Mac Command shortcuts; turn it off for actual Control keys. Some browser/ChromeOS shortcuts are reserved by the Chromebook.

**Disconnect** ends the viewer session. Stopping the Mac host with **Ctrl+C**, closing its Terminal window, or stopping Codespaces ends access. No background service or login item is installed. The host does not reconnect automatically after losing its server connection; restart it.

## Latency and network behavior

- The host attempts **WebRTC video at up to 30 fps, scaled to fit 1280 × 720**, with keyboard/mouse events over a data channel. When direct connectivity works, screen traffic does not travel through Codespaces.
- When direct connectivity fails, HTTPS/WebSocket relay video runs through Codespaces, at up to 15 fps with compressed JPEG frames. Only one frame is in flight at a time; old frames do not accumulate. On long-distance or slow networks this will feel less smooth.
- The displayed milliseconds measure **control round-trip time**, not complete screen latency. No particular latency or frame rate is guaranteed. The prototype uses software video encoding and does not include audio, clipboard sync, file transfer, monitor selection, or unattended login-screen access.
- Use **compatibility relay** to force fallback. Reconnect to retry direct WebRTC. Both computers initiate outbound connections; no router port forwarding is required. Network policies may still block the service.
- The Mac host sends its first display, mapped to the main display's input coordinates. Keep the main display first in a multiple-monitor setup; other arrangements are not tested.
- Codespaces must stay running. It has idle/lifetime limits and usage quotas. This is intended for interactive sessions, not an always-on host.

For a better chance of smooth video on networks that require a relay, configure your own nearby **TURN** service before starting the server. Set `ICE_SERVERS_JSON` to a JSON array of WebRTC ICE server definitions, for example a STUN entry and a TURN entry with `urls`, `username`, and `credential`. The same list is delivered only to authenticated peers. Store it in a Codespaces secret; do not commit relay credentials. TURN service is not included or provisioned by this project. Codespaces' TCP port forwarding is not itself a TURN service.

## Access and privacy

Keys are generated randomly on first launch and stored in `.secrets.json` with owner-only file permissions. The file is git-ignored. The host and viewer require separate keys; one connection of each role is allowed. A second connection cannot displace an existing one. Keys are sent in WebSocket messages, not URLs or browser storage. WebRTC transport is encrypted. In fallback mode, TLS protects each hop, but the Codespaces relay handles the screen frames in memory; it is not end-to-end encrypted through that relay. No session recording is implemented.

Only give the keys to yourself. Anyone with the viewer key can control the running host. To revoke keys: stop the server, delete `.secrets.json`, restart the server, and enter the new keys on both devices. The source repository can be public. Never commit `.secrets.json` or TURN credentials; enable account protection on GitHub.

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

These tests verify WebRTC video, data-channel messages, relay JPEG delivery, input release on disconnect, and viewer reconnection. The synthetic server uses fixed public test keys and listens only on localhost. **Do not deploy the synthetic server or forward its port publicly.** Deploy `npm start` only.

## References

- [GitHub Codespaces port forwarding](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace)
- [Codespaces lifecycle](https://docs.github.com/en/codespaces/about-codespaces/understanding-the-codespace-lifecycle)
- [WebRTC and TURN](https://webrtc.org/getting-started/turn-server)
- [aiortc API](https://aiortc.readthedocs.io/en/latest/api.html)
