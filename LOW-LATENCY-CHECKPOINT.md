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
- Final code review: added a twice-per-second refresh of the latest captured image so an idle ScreenCaptureKit display stays healthy. Rebuilt package; native regression tests running.
- Commit/push, publish v0.2.0 package, install the new Mac folder without overwriting the working old folder.
- Configure the user's actual private code in their existing Codespace and migrate Mac settings privately. Never place personal credentials in Git or release assets. Git credentials work for repo/releases; Codespaces API returned 403. Browser Codespaces page is signed out. Asked the user to sign in; pending. Do not claim their private code is configured until it is.
- Update this file with publication and configuration status.
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
