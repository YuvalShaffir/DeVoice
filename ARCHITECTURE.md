# Architecture

DeVoice removes vocals from Chrome tab audio in near real time.

## Components

- `extension/` — Chrome MV3 extension. `background.js` (service worker) starts tab capture on toolbar click and hands the stream id to `offscreen.js`. An AudioWorklet (`capture-processor.js`) cuts 6 s stereo chunks. `offscreen.js` uploads chunks to the backend, fetches stems, and plays them through per-stem gain nodes.
- `backend/` — FastAPI app on `127.0.0.1:8000`. `server.py` exposes `POST /separate` and `GET /stem/{hash}/{stem}`; `separation.py` runs Demucs (`htdemucs`); `auth.py` gates every route by `X-Auth-Token`; stems are held in memory by SHA-256 of the upload and dropped once fetched.
- `tests/` — pytest for backend and static extension checks; `tests/js/` for extension behavior.
- `scripts/` — repo tooling (pre-commit hooks).

## Flow

tab audio → worklet chunk (6 s WAV) → `POST /separate` → `{id, stems}` → `GET /stem/{id}/{stem}` per stem → gain-mixed playback (vocals 0, no_vocals 1), chunks played in order.

## Trust

Backend accepts only the extension origin (CORS) and a shared token generated at `backend/.auth_token`, pasted into the extension's options page.
