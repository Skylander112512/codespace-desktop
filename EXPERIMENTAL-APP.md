# Optional Chromebook app — v0.3.0-app.1

This prerelease adds an installable web app (PWA) to the existing Codespaces viewer. It opens in its own window from the Chromebook launcher. The normal browser viewer is still available. No Linux setup or extension is required. Stable v0.2.13 and its Mac download remain available; no Mac update is required for this experiment.

## Try it in your existing Codespace

When ready to briefly disconnect, use a **new Codespaces terminal** in the project folder:

```sh
git fetch https://github.com/Skylander112512/codespace-desktop.git tag v0.3.0-app.1
git switch --detach v0.3.0-app.1
npm ci
```

If Git reports local changes or an error, stop and keep your current server running. Do not force or reset your work. The detached checkout selects this exact experimental version without moving your existing branch.

In the terminal currently running the desktop server, press **Ctrl+C**, then run:

```sh
npm start
```

Restarting the server is necessary for the new manifest/icon routes. Keep port 3000 Public. The Mac host reconnects automatically. With multiple saved Codespaces, it may choose another available server during this restart; it stays on the server it successfully connects to. If that happens, use that server's viewer or choose the desired saved Codespace on the Mac when convenient.

Open your public **port 3000 viewer URL** in a full Chrome tab and refresh. Choose **Install app** when the button appears, or Chrome's menu → **Cast, save, and share → Install page as app**. Chrome may also show an install icon in the address bar. The browser controls whether/when to offer installation. Installation is not done from the Codespaces editor, an embedded Simple Browser, or the blank-tab wrapper.

Disconnect the browser viewer, then launch **Codespace Desktop Experimental** from the Chromebook launcher and enter your existing viewer code. One viewer can control the Mac at a time. Your current code and Mac host key are preserved; the app does not set or copy a code between servers.

## Same features and connection

- Uses the exact same viewer JavaScript: direct WebRTC video, relay fallback, 720p/60 and 1080p/60 choices, game mouse and its backtick shortcut, keyboard/mouse input, Ctrl-to-Command mapping, fullscreen, text transfer, diagnostics and reconnect.
- The app opens directly to login. Normal browser tabs retain their launch choices, including the existing blank-tab option.
- Saved Mac backup connections work as before. Each installed app belongs to one Codespace URL. Install the other Codespace's viewer separately if you want both in the launcher; installation does not discover or switch servers automatically.
- Both the Mac host and Codespace server must be running. An installed app cannot start a stopped Codespace or work around its quota.
- No new streaming pipeline or latency claim. Sound remains unavailable with the stable video-only Mac host; older sound-capable hosts retain their existing viewer controls.
- No service worker, offline page cache or stored connection code is added. Updates load from the server when you reopen/refresh; the app does not cache screen frames. Closing the app ends its viewer session. Installation alone grants no remote access.

## Go back

Disconnect the experimental app. In the Codespace project terminal:

```sh
git switch -
npm ci
```

This returns to the checkout you used before the experiment (if you have not switched elsewhere since). Stop the desktop server with Ctrl+C and run `npm start` again. Use the normal viewer page. You may uninstall the experimental app through Chrome's app settings. Your private pairing file is not removed by switching versions.

## Validation

Local automated coverage includes install acceptance, cancellation, failure and duplicate clicks; standalone login; manifest/icon serving; and the existing viewer/server regression tests. Actual Chromebook installation and game input still need a test on your device. No running user Codespace or Mac host is restarted by preparing/publishing this release.
