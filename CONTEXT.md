# Context

- **Stem** — one separated audio track. Two exist: `vocals` and `no_vocals` (sum of all non-vocal Demucs stems).
- **Chunk** — 6 s stereo slice of captured audio; unit of upload and playback. Silent chunks are dropped.
- **Session** — one capture run in `offscreen.js`; responses from a stopped session are discarded.
- **Auth token** — random hex in `backend/.auth_token`; sent as `X-Auth-Token`.
- **Offscreen document** — hidden extension page that owns audio capture and playback (service workers cannot).

## Decisions

- Backend is local-only and token-gated, origin-locked to the extension ID (`EXTENSION_ID` env).
- Results cached by content hash, so repeated audio is not re-separated.
- Extension scripts are plain browser scripts, no bundler.
