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

Published v0.2.4 (635324c) with Mac ZIP/checksum and installed Downloads/Codespace Desktop Mac 0.2.4. Packaged executable launches successfully; signatures validated. Pulled the update into the user's existing Codespace without restarting its server; git pull completed and preserved its two untracked ZIP files. User needs to close the old Mac host and open the 0.2.4 Start Mac Host.command. Its foreground waiting/reconnect behavior works with the existing Codespaces server as well. Test viewer/server were closed. No hosting migration, credentials change, automatic login item, or screen/input automation was performed.


## Game camera controls — v0.2.5
User reports Roblox mouse movement cannot turn the camera and requests a centered pointer. Explicit instruction: only update the project; do not run the Codespace. Added opt-in Game mouse button using browser Pointer Lock, accumulated relative motion over the existing low-latency channel, and centered Quartz events with explicit X/Y movement deltas. Right-button dragging, click metadata, keys, desktop pointer mode, video quality, and reconnect behavior are retained. Esc, blur, disconnect and mode changes release input. A host capability flag prevents using Game mouse with old Mac binaries; delayed browser lock acquisition after disconnect is rejected.

Verified 21 JavaScript tests, 6 native mouse-event tests (CGEventPost intercepted; no real input), 6 synthetic host integration tests for modern/legacy channels, and 3 latency/settings tests. Built and signature-verified the standalone Apple Silicon Mac package. Native video encoding is unchanged. Actual Roblox gameplay has not been tested and requires user confirmation. Local test server stopped. Publication and separate Downloads/Codespace Desktop Mac 0.2.5 installation are the next steps. User must update BOTH Mac host and Codespace viewer themselves; no Codespace was started or changed during this request.

Published v0.2.5 (00bcdc7) with Mac ZIP and SHA256SUMS; both uploads verified. Installed Downloads/Codespace Desktop Mac 0.2.5 separately and confirmed packaged executable launches via --help. Changes are on main and low-latency. User must close the old Mac host, open the new launcher, pull main in their own Codespace, refresh the browser viewer, and click Game mouse after focusing Roblox. Esc releases it. Actual Roblox confirmation remains pending. The real Codespace was not started or modified.


## Game mouse shortcut without stopping walking — v0.2.6
User requested a keybind and preserving character walking; explicitly do not open or run their Codespace. Added Backquote (the backtick key below Esc) while the remote screen has focus; swallowed down/up and ignored repeats. It toggles Pointer Lock both ways without clearing held keyboard keys. The Mac pointer-lock message now accepts preserveKeys:true, releases mouse buttons but retains W/A/S/D and other keys. This fixes the explicit release of keyboard input during activation in 0.2.5. Toolbar pointerdown also preserves screen focus. Esc, actual blur, hidden tab and disconnect retain full release behavior. Failed lock requests leave walking alone; late acquisition while unfocused is rejected. Both viewer and Mac host must update. Backtick is reserved for Game mouse instead of being forwarded to Roblox.

Validated 24 distinct JavaScript tests (full suite then changed client suite) and 7 native event tests with every CGEventPost intercepted. Tests cover walking through both toggles, eventual W keyup, repeat suppression, failed requests, blur and late lock. Built and ad-hoc signature-verified 0.2.6 Mac package. Actual Roblox remains user-tested; no Codespace or real desktop input was used. Publication and Downloads installation are next.

Published v0.2.6 (bd27eb0) with verified ZIP/checksum assets and installed a separate Downloads/Codespace Desktop Mac 0.2.6 folder. Main and low-latency branches updated. User must restart into the new Mac host and update their own Codespace viewer. Their Codespace was not opened, started, or modified. Actual Roblox confirmation remains pending.


## Optional blank-tab wrapper — website v0.2.7, Mac remains 0.2.6
User requested an initial Stay in this tab / Cloak choice like Interstellar and asked whether it hides from GoGuardian. Explicitly explained it does not reliably hide activity from monitoring; implementation and UI present it as tab appearance only. Researched Interstellar's official settings.js; independently implemented a synchronous user-click popup, same-origin viewer iframe in about:blank, Google Classroom title with local generic classroom icon, and original-tab redirect to classroom.google.com only after the viewer loads. Viewer codes/query/fragment are not copied. Pop-up block/failure/cancel preserve the current page; wrapper skips the launch screen. CSP now permits only same-origin framing and frame sources, not arbitrary third-party embedding. No Mac changes or new Mac package needed.

30 Node tests passed, including six launch tests plus existing input regressions. Local browser verified Stay reveals login and Cloak loads the embedded viewer before redirecting the original tab to Classroom. The IAB tool does not list the new popup as a controllable tab, so live remote input/fullscreen inside that popup was not tested. Screenshot outputs/tab-choice.jpg records the start screen. The real Codespace was not opened or started. Publication and cleanup next.

Published website-only v0.2.7 (e320a49), main and low-latency updated. Release links the unchanged v0.2.6 Mac download. Local test server and test page closed. User needs to pull/restart their own Codespace and refresh; no Mac upgrade. No GoGuardian bypass is claimed.


## HTTPS tunnel origin and explicit text transfer — v0.2.8
User pasted an Upgrade rejected log with an HTTPS localhost origin; reproduced the 403 before changing validation. The tunnel exception now accepts HTTP or HTTPS localhost only with the existing configured Codespaces port, loopback peer, Host, and forwarded public hostname checks. Wrong hosts, ports, schemes, missing proxy config, and literal Markdown-formatted origins remain rejected.

User also requested an easy text copy/paste box. Added Text transfer panel with Send to Mac (pbcopy), Get from Mac (pbpaste), and Copy text (browser API with manual selection fallback). Requests travel through the authenticated WebSocket; host and viewer message directions are restricted. Only explicit actions read/write clipboard, no background sync, no contents in logs/storage, UTF-8 plain text capped at 16 KB. Demo uses an in-memory clipboard; native subprocesses use fixed absolute commands with stdin and a 3-second timeout, never a shell. Old hosts keep transfer buttons disabled; host advertises textTransfer capability. Blank wrapper permits clipboard-write for its same-origin viewer. Input/video behavior unchanged.

34 JS tests and 4 Python clipboard tests passed. Native clipboard commands were mocked, so the user's actual clipboard was not read/written. Local browser + synthetic host sent and retrieved an emoji/multiline sample successfully; screenshot outputs/text-transfer-preview.jpg. Local test server/host/tab stopped. Built and signature-verified Mac 0.2.8. Both viewer and Mac must update for text transfer. Real Codespace not opened/started/modified. Publication and Downloads install next.

Published v0.2.8 (b805305) with verified Mac ZIP and SHA256SUMS; installed a separate Downloads/Codespace Desktop Mac 0.2.8 folder. Main and low-latency updated. User must start the new Mac launcher and pull/restart their Codespace themselves, then refresh and use Text transfer. No actual Codespace or real Mac clipboard was accessed during testing.


## Optional Mac system sound — v0.2.9
User requested sound, possibly BlackHole. Added a separate native ScreenCaptureKit SystemAudio helper and WebRTC Opus track: stereo 48 kHz, 20 ms frames, bounded 60 ms PCM queue, opt-in Sound button. No BlackHole, microphone capture, audio routing change, or automatic startup. Audio capture starts only on explicit Sound activation and stops on mute, disconnect, failure, quality renegotiation or host exit. Video encoder is unchanged. Viewer capability detection keeps sound disabled for older hosts or JPEG-only connections. Both viewer and Mac must update.

36 Node tests, four native audio tests (including generated tone through Opus), six host integration tests and native video pacing passed. Packaged 0.2.9 browser check used synthetic video and generated tones only: Sound on/unmuted/playing, Sound off/muted/paused verified; live UI showed about 60 FPS at 720p while audio was on. Screenshot outputs/system-audio-preview.jpg. Actual ScreenCaptureKit system-audio callbacks and Mac app/game sound remain user-tested, not verified in this session. No actual desktop, microphone, clipboard or input was captured/injected. Test server, packaged host and browser tab stopped.

Built and signature-verified Mac package, verified ZIP integrity, wrote checksum, installed separate Downloads/Codespace Desktop Mac 0.2.9 folder. Low disk space required removal only of disposable prior build caches: work/mac-build/build, work/mac-build/dist, work/mac-build-fix/build and work/mac-build-fix/dist. Prior Downloads folders and pairing settings preserved. Real Codespace was not opened, started or changed. Publication next.

Published v0.2.9 (b828f29) with verified Mac ZIP/checksum upload responses. Main and low-latency updated. Separate Downloads/Codespace Desktop Mac 0.2.9 installed and signatures rechecked. User must restart into that launcher, pull/restart their own Codespace, refresh the viewer and turn Sound on. Actual Mac app/game sound confirmation remains pending.


## Direct video recovery and smoother adaptation — v0.2.10
User reports intermittent black direct video and variable lag; requests updating existing Codespace files without starting/restarting its server. Follow-up: do not close the current Mac host unless replacing it with the new running host. Current real Mac host has been left untouched.

Added decoded-frame gating (two healthy interval samples before switching off relay), keyframe requests on decode stalls, bounded automatic negotiation recovery (two attempts, 30-second cooldown, reset after a healthy minute), and explicit Retry video. Recovery respects manual relay and hidden tabs. Receiver loss feedback continues when packets arrive but frames cannot decode. Set zero target buffer on audio as well as video to reduce avoidable synchronized playout buffering where supported. Healthy sessions do not auto-restart. Sustained reconnects release input and reset audio to off.

Adaptation now lowers bitrate before cutting FPS during network trouble, requires persistent overload before reducing FPS, and recovers selected FPS/bitrate more quickly after consecutive clean reports. Initial encoder presets and capture remain unchanged. No guarantee of fixing the user's particular black screen without their next real-network test.

40 Node tests, 5 latency/settings tests, 7 host integration/unit tests, and 6 native video tests pass. Synthetic hardware: about 58 FPS at 720p and 57 at 1080p. Built signed package and verified ZIP integrity. Local browser test and publication in progress. Existing Codespace is accessible but VS Code Trust Folder & Continue prompt requires approval; asked through async tool. Do not approve until answered. No server command or remote file update yet.

Local browser fault injection passed: paused only the synthetic ScreenEncoder process; viewer fell back to relay, automatically renegotiated, and resumed 720p at approximately 60 FPS. Screenshot outputs/stability-preview.jpg. Test host/server/tab stopped. Separate Downloads/Codespace Desktop Mac 0.2.10 installed without closing the existing real host; actual pairing unchanged. Publication next.

Published v0.2.10 (ad926e7) with ZIP/checksum uploads verified. Packaged executable --help passed, all test processes stopped. Real Mac host processes 41973/41974 were still running and were not closed/replaced. Separate 0.2.10 Downloads folder is ready. Existing Codespace tab remains at Trust Folder & Continue; async approval remains pending. No remote file update, npm start, server restart, key changes, or user-host interruption performed. User can run git pull --ff-only in a new Codespace terminal and refresh the port; already-running server supports new viewer messages. Resume Codespace update once trust approval arrives; preserve tracked changes and existing server process.


## Video-only host and optional diagnostics — v0.2.12
User testing found a large latency improvement when the audio track was removed entirely, even compared with Sound off. The comparison also had better network RTT, so it does not isolate sound as the only cause. Removed audio negotiation and SystemAudio from the new Mac package. The viewer retains sound compatibility with the previous published v0.2.10; README and release notes link that rollback. Version 0.2.11 was an unpublished diagnostic build.

Added opt-in local numerical diagnostics and a separate launcher, with bounded private files and no screen/input/clipboard/credentials. Frame arrival, encode timing, keyframe size, queue drops and receiver metrics help distinguish source cadence from browser buffering. Ordinary launches do not collect fine frame timing or write diagnostics. Capture/encoder settings and adaptive quality are unchanged.

The user reported brief pauses about once a second. Recent video-only measurements showed low browser buffering but irregular encoded frame arrivals and occasional slower encoding. This does not prove a specific cause or a stutter fix. The user ultimately said the connection is good; preserve the current settings and do not restart it for further experiments. A source 0.2.12 diagnostic host replaced the old host with authorization and remains running. The existing Codespace server was not restarted. Its Trust Folder prompt still requires the previously requested response before any remote edit. Publication requested by user; include the sound-removal reason and previous sound-enabled release.

Follow-up measurements: network RTT and browser buffering rose again, and existing adaptation reduced output to 30 FPS. User closed RustDesk; CPU activity fell, but delay did not immediately recover. No new encoder, buffer or adaptation tuning was applied. Suggested one viewer Retry video; no automated reconnect was performed. Validation: 40 JavaScript and 13 Python tests passed. Built in an isolated source copy to preserve the running native helper; signatures, ZIP integrity, absence of SystemAudio and packaged --help passed.

Network tracing with tiny simultaneous router/internet pings found closely correlated spikes already on the Mac Wi-Fi hop (router peak about 403 ms). This points to local Wi-Fi/router delay as one contributor; probes cannot identify the exact radio/router cause or rule out other hops. Paused the release asset upload during measurement; GitHub source commit 94a99de is pushed, v0.2.12 release remains a draft with an incomplete ZIP upload.

User authorized replacing the current host with the improved version. Added a bounded buffer-only response: at most three bitrate cuts before clean recovery, and no FPS drop from buffer-only feedback when decode speed and incoming FPS remain healthy. Packet loss, severe frame starvation and slow decode retain full adaptation. Eight latency tests plus six diagnostic/queue tests pass. New source host launched successfully before stopping the old source host; verify new host connected before completing the turn. Final package and draft release must be rebuilt/updated with this additional fix.

Replacement source host connected successfully at 720p60 with diagnostics; old source host stopped only after replacement was ready. First roughly one-minute post-change window retained a 60 FPS target throughout, about 54 FPS median delivered, ~75 ms median browser buffer and ~134 ms median RTCP RTT. This is encouraging for avoiding the quality collapse, not a controlled proof of end-to-end latency improvement. A second router/internet probe again showed local-hop spikes (~364/~375 ms); the network issue remains. Keep this updated source host running. Final validations total 40 JavaScript and 21 distinct Python tests.

Published v0.2.12 at https://github.com/Skylander112512/codespace-desktop/releases/tag/v0.2.12 targeting a3b8e6f. Final ZIP and SHA256SUMS upload sizes/states verified. Release notes include removal of sound, rollback link to v0.2.10, optional local diagnostics, buffer-only adaptation guard and the unresolved network/stutter limitations. New Mac package is installed separately in Downloads/Codespace Desktop Mac 0.2.12. The updated source host remains running and connected; no further restart is needed. Codespace files/server were not modified remotely; git pull --ff-only and viewer refresh load the newer viewer when the user is ready. No additional live tuning or automated monitoring was installed.


## Automatic saved Codespace failover — v0.2.13 (in progress)
User clarified the desired fallback: save two Codespaces from different accounts, try sequentially while offline, stop looking once one connects. No shared discovery service is needed for explicitly saved addresses. Never open/start/restart the user's Codespace editor/server. User supplied a backup URL and host key privately; keep the key outside the repository and all release artifacts. User authorizes replacing a Mac host only with an immediately started replacement.

Added legacy-compatible saved pairings, viewer/editor address normalization, Add Codespace.command (can save an offline backup without changing the active session), Choose Codespace.command, and serial failover. Only one host run is awaited at a time; no probes/watchers/encoders for other saved servers while connected. Connection attempts have an eight-second open timeout and ten-second authentication deadline; failed complete rounds back off to 60 seconds. Invalid keys are skipped until changed/restart. Tests use temporary credentials/local servers only. Current work still requires packaging, private backup setup, replacement verification and publication.

Validation complete: 41 JavaScript tests and 37 distinct Python tests passed (including eight failover cases). Built and signature-verified the isolated-source 0.2.13 Mac package, checked ZIP integrity and packaged --help, and installed Downloads/Codespace Desktop Mac 0.2.13 separately. Real private setup retained the original pairing and added the user-supplied backup locally. The new packaged host tried the original (HTTP 404), authenticated successfully to the backup, and stopped searching. Only then was the old 0.2.12 host stopped. The new host remains running, waiting for the viewer. No Codespace editor was opened, and no remote server was started, stopped, or restarted. Publication next.
