# Resume checkpoint — v0.2.0

User requested latency improvements and asked to resume where work stopped when they say “continue”. They also requested saved Mac connection details and a private numeric Chromebook code. Their personal code is deliberately absent from this public file. Other users choose their own code. User explicitly requested **no incorrect-code attempt lockout**.

## Implemented
- Native ScreenCaptureKit / VideoToolbox hardware H.264 helper, real-time encoding, no B frames, bounded pending work. Main-display capture; synthetic mode for tests.
- aiortc packet passthrough avoids software re-encoding. Native keyframe requests connect to the pinned aiortc 1.15 PLI/FIR handler. Queue overflow waits for a fresh keyframe.
- Smooth mode: up to 720p60 on level-3.2 peers, or 854×480/60 on level-3.1 peers. Sharper mode on level-3.1 peers: up to 720p30. Software and JPEG fallback retained.
- Adaptive bitrate/FPS, minimal browser buffer hints, FPS/resolution/codec/route/encode/decode/buffer statistics. Decoded frames detect frozen video.
- Disposable unordered mouse motion, reliable buttons/keys, sequence guards, release on transport changes/disconnect.
- `npm run set-code` stores a salted hash in ignored `.secrets.json`. Long viewer key remains a recovery credential. No failed-code lockout. Existing connection/message resource bounds remain.
- Mac remembers successful connection URL + host key in its private Application Support folder. Next launch connects automatically. `Change Connection.command` repeats setup. No login item or unattended startup.
- Reproducible Apple Silicon package script and user instructions.

## Verified
- 13 Node tests pass, including code login, no lockout after repeated wrong codes, role separation, tunnel-origin checks, stalled video, and motion delivery.
- 5 original host integration tests pass (synthetic WebRTC, relay, reconnect and key release).
- 3 latency/settings tests pass.
- 5 native tests pass: H.264 decode/pacing, PLI, queue recovery, compact level-3.1 profile.
- Hardware synthetic benchmark: ~58 FPS at 720p, ~6.3 ms mean encode.
- Built standalone Mac executable + helper; tested packaged `--native-demo` in real Chromium browser. Observed **60 FPS at 854×480**, ~5 ms encode, ~1 ms decode, ~7 ms video buffering on localhost. This is not an internet or input-to-display latency measurement.
- Browser compatibility relay works. Live switch to Sharper verified: 1280×720 / 30 FPS, hardware encoding retained.

## Remaining before completion
- Final code review: added a twice-per-second refresh of the latest captured image so an idle ScreenCaptureKit display stays healthy. Rebuilt package; all five native regression tests pass.
- Published v0.2.0 release with Mac ZIP and SHA256SUMS. Implementation commit 00d809a is on main and low-latency. Installed a separate “Codespace Desktop Mac 0.2.0” folder in Downloads; old folder preserved. Previous Mac connection details migrated into private Application Support settings. Service was offline, so current connection validity still needs verification.
- Configure the user's actual private code in their existing Codespace and migrate Mac settings privately. Never place personal credentials in Git or release assets. Git credentials work for repo/releases; Codespaces API returned 403. User signed in and existing Codespace opened. VS Code shows “Trust Folder & Continue” before allowing a terminal. Asked for approval; pending. Do not click until approved. Next: inspect git status, preserve local changes, pull main, prepare npm run set-code. Browser safety rules require user entry/submission of the new credential; do not enter it for them through UI. Then start server, verify public port and login. Do not claim their private code is configured until it is.
- Continue from the pending Codespace trust approval; local demo/test processes are stopped. Browser tab for the real Codespace is retained. New Mac launcher already exists in Downloads.
- No TURN service provisioned; existing ICE_SERVERS_JSON configuration remains supported. No paid provider/budget selected.

## Local development commands
Use the existing checkout and Python environment recorded in the chat's workspace context; do not rebuild the project elsewhere.

```
npm test
node test/run-test-server.mjs
python test/test_host.py -v
python test/test_latency.py -v
mac/native/build.sh
python test/test_native_video.py -v
```

Test server binds localhost only and uses public synthetic fixture credentials. Never forward it publicly. Native Terminal UI is unavailable to computer-use tools; do not bypass a blocked tool. Tests use synthetic frames and simulated input rather than the real desktop.


## Click repair — v0.2.1
User confirmed excellent FPS but the pointer moves without clicks working. Terminal Accessibility is enabled (checked in System Settings). Reproduced a concrete native event bug: freshly-created mouse-up has click count 0, and the old host never sets matching click counts/event numbers. Added explicit press metadata for down, drag, and up; nearby rapid clicks increment the count. Three regression tests failed before the repair and pass afterward, using real Quartz event objects with CGEventPost intercepted (no real desktop input).

13 Node tests, 5 host integration tests (now including button press/release over the control data channel), 3 latency/settings tests, and 3 native mouse-event tests pass. Native video encoding is unchanged. Built and ad-hoc verified v0.2.1 Mac package; installed a separate Downloads/Codespace Desktop Mac 0.2.1 folder. Running v0.2.0 host has not been interrupted. User must restart into the new host for actual click confirmation. This host fix works with the existing v0.2.0 Codespaces server; no server restart is required for clicks. Published and verified v0.2.1 with Mac ZIP and checksum; implementation commit 90b3c36 is on main and low-latency. Actual user click confirmation is still pending restart into the new Downloads folder.


## Confirmed version-mismatch cause — v0.2.2
The user reported v0.2.1 still failed to click. Confirmed the running Mac really is v0.2.1 and its macOS TCC preflight grants PostEvent access. An actual browser synthetic test delivered down/up/key through the new viewer normally. Fetching the user's public Codespaces client.js revealed it was still **v0.1.2** code: its ondatachannel overwrites the control variable for every arriving channel, so the new host's motion-only channel silently discarded clicks/keys while allowing movement.

Updated the actual existing Codespace using git pull --ff-only in a NEW web terminal, leaving the running server and Mac host connected. Two untracked ZIP files were preserved; tracked tree was clean. Verified live client.js SHA256 matches the updated viewer exactly. Asked user to refresh the Chromebook page, reconnect, and confirm clicks; response pending. No Mac restart is needed for this immediate fix. Earlier “no Codespaces update needed” advice was incorrect for their v0.1.2 viewer.

Added explicit inputProtocol=2 capability negotiation. Host creates only reliable control initially; the optional motion channel is created after a supporting viewer's answer. Old viewers keep clicks/keys on the reliable channel. Regression reproduced unexpected motion channel on old host; six host tests pass after repair for both legacy and modern viewers, including button states. Preparing v0.2.2 release to prevent recurrence. Do not change the user's private code as part of this click fix; older PIN setup remains separately unverified.

Published v0.2.2 (12c7585) with Mac ZIP and SHA256SUMS; both assets verified in the release response. User completed the hidden private code prompt in the actual Codespace. Updated its source to v0.2.2 and restarted the previously observed port-3000 server; public health reports 0.2.2. Verified the user's chosen code authenticates successfully and immediately closed the test viewer without sending input. Server startup output filters long private keys. Mac host needs reopening after this server restart; actual user click confirmation is still pending. Do not put the private code in this repository.

## Optional HD modes — v0.2.3
User confirmed clicks now work. Requested optional 720p60 and 1080p60, preserving Smooth as default, plus fork / different-account / different-Wi-Fi instructions. Added the two choices, WebRTC MediaCapabilities checks and RFC 6184 max-recv-level signaling, receiver-limited native capture selection, 1080p ScreenCaptureKit/VideoToolbox helper mode, and per-preset adaptive bitrate budgets. Browser results with synthetic animated pixels: 1080p 60 FPS (1920x1080, ~8 ms encode), 720p ~60 FPS (1280x720, ~4 ms encode); default remains 854x480/60 for a level-3.1 answer. Higher modes fall back explicitly if the browser cannot declare support. No real desktop/input was used for these tests.

15 Node tests and 20 Python tests pass, including real hardware encoding/decoding, H.264 packet transport, legacy/current control channels, and receiver capability fallback. Built v0.2.3 with valid ad-hoc signatures. Public docs explain a fork needs its own private code, new viewer URL and Mac host key; no personal credentials are included. Packaged browser check and deployment are next.

Completed packaged-host browser check: actual bundled v0.2.3 produced 1920x1080 / 60 FPS (~8 ms hardware encode) using synthetic input. Published GitHub release v0.2.3 with Mac ZIP and checksum, installed Downloads/Codespace Desktop Mac 0.2.3 without replacing old folders, and updated/restarted the existing Codespace. Public /health now returns 0.2.3; the live video-quality module hash matches the tested file. Mac pairing and private viewer code were preserved. User must close the old Mac host, open the 0.2.3 launcher, refresh the Chromebook viewer, and select an optional HD mode. Test host/server and temporary browser tab were stopped/closed. Actual Chromebook/network 1080p performance remains user-dependent; no fixed FPS guarantee.

## Keep waiting for Codespaces — v0.2.4
User confirmed 720p60 is excellent. Clarified request: keep existing Codespaces architecture; leave Mac command running before departure while Codespaces is stopped, then connect when user starts the same Codespace later. No external hosting or Mac web-server migration is wanted. No Render/Cloudflare deployment was performed; exploratory uncommitted hosting files were removed.

Added foreground Mac reconnect supervisor with 2/4/8/16/32/60-second capped backoff, fresh cleaned-up Host per attempt, reset after a healthy minute, and cancellation via Ctrl+C. Offline HTTP responses (including 404 and sign-in redirects) retry without following redirects. Invalid host credentials and certificate failures still require attention. Capture/encoding are inactive without a viewer. The browser similarly retries temporary disconnections using only an in-memory code and cancels/clears it on Disconnect. All video encoding and 720p60 settings are unchanged.

17 JS tests, 4 reconnect tests (including actual HTTP 404 -> 302 -> authenticated -> server close -> authenticated), and existing host integration checks passed. Browser UI was tested by stopping/restarting a synthetic local server: it retried and authenticated automatically without re-entering the code. Built and ad-hoc verified Mac 0.2.4. Packaging/publication/installation next. A stopped Codespace still must be opened by the user and npm start run, with port 3000 Public; the Mac cannot wake Codespaces or use a different Codespace's keys automatically.
