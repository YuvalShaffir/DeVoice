# extension/

Chrome MV3 extension. Captures tab audio, sends 6 s chunks to the backend, plays back the mix with vocals muted by default; the popup's Vocals switch brings them back live. Plain browser scripts, no bundler.

- `manifest.json` — permissions (`tabCapture`, `offscreen`, `tabs`, `storage`), host access to `http://127.0.0.1:8000`, service worker, options page.
- `background.js` — service worker. Handles popup messages: `start-capture` (checks token, skips silent tabs, gets tab-capture stream id, creates offscreen doc, sends `stream-id` + token + tab id) and `get-status` (capturing tab id and Vocals state from offscreen + last error from `storage.session`). Shows error badges on `backend-error` messages.
- `offscreen.html` / `offscreen.js` — offscreen document. Starts capture, loads the worklet, uploads chunks to `/separate`, fetches stems, plays them through per-stem gain nodes (`vocals` 0, `no_vocals` 1) in chunk order. Handles auth/unreachable errors and stale sessions. Answers `capture-status` (tab id + `vocals`), `stop-capture` and `set-vocals` (fades the vocals gain to 1 or 0 over 50 ms; every Session starts with vocals removed).
- `capture-processor.js` — AudioWorklet. Buffers input, emits a stereo chunk every 6 s; drops silent chunks.
- `popup.html` / `popup.js` — toolbar popup: "DeVoice on this tab" switch (start/stop capture), Vocals switch (live, enabled only while capturing this tab), state text, last error, settings link. State is read live via `get-status`.
- `options.html` / `options.js` — page to paste and store the backend auth token in `chrome.storage.local`.
