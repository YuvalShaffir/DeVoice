# extension/

Chrome MV3 extension. Captures tab audio, sends 6 s chunks to the backend, plays back the mix with vocals muted. Plain browser scripts, no bundler.

- `manifest.json` — permissions (`tabCapture`, `offscreen`, `tabs`, `storage`), host access to `http://127.0.0.1:8000`, service worker, options page.
- `background.js` — service worker. On toolbar click: checks token, skips silent tabs, gets tab-capture stream id, creates offscreen doc, sends `stream-id` + token. Shows error badges on `backend-error` messages.
- `offscreen.html` / `offscreen.js` — offscreen document. Starts capture, loads the worklet, uploads chunks to `/separate`, fetches stems, plays them through per-stem gain nodes (`vocals` 0, `no_vocals` 1) in chunk order. Handles auth/unreachable errors and stale sessions.
- `capture-processor.js` — AudioWorklet. Buffers input, emits a stereo chunk every 6 s; drops silent chunks.
- `popup.html` — toolbar popup markup.
- `options.html` / `options.js` — page to paste and store the backend auth token in `chrome.storage.local`.
