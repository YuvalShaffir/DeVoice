# backend/

FastAPI service that separates audio into vocals / no-vocals stems with Demucs. Listens on `127.0.0.1:8000`.

- `main.py` — entrypoint (`app`). Refuses root/Administrator first, then wires token, `separate`, and the extension origin derived from `extension/manifest.json`.
- `startup.py` — `extension_id_from_manifest(path)` (SHA-256 of the manifest's `key`, hex mapped to a–p; clear `RuntimeError` for a missing/invalid manifest or key) and `refuse_elevated()` (euid 0 on POSIX, `IsUserAnAdmin` on Windows).
- `server.py` — `create_app(...)`: wraps routes in `RequestGuard`, CORS-locked to the extension origin (CORS outermost, so preflights pass and guard errors carry CORS headers). `POST /separate` (raw `audio/wav` body, else 415 → SHA-256 id, stems held in memory; no multipart, which spools to disk), `GET /stem/{hash}/{stem}` (serves each stem once, then drops it). Docs endpoints disabled.
- `guard.py` — `RequestGuard` ASGI middleware, checks run before any body byte is read: `Host` must be `127.0.0.1` (any port) → else 400; `X-Auth-Token` constant-time compare → else 403; `POST /separate` needs `Content-Length` (411 missing, 400 invalid, 413 over `MAX_BODY` = 2 MB); bodies streamed past 2 MB → 413. `OPTIONS` passes through to CORS / router. It is middleware because FastAPI dependencies run only after the body is parsed.
- `api.py` — HTTP contract constants shared by server, guard and tests: route paths, `TOKEN_HEADER`, `CONTENT_TYPE_HEADER`, `WAV_MEDIA_TYPE`, `INVALID_AUDIO`, `extension_origin(id)`.
- `limits.py` — `SeparationQueue`: 1 Demucs run at a time, up to 3 waiting (429 beyond), 20 s timeout (504) with the slot held until the thread returns; `Results`: stems by SHA-256, dropped 30 s after finishing, swept at the start of every request; a dedupe hit keeps the original expiry. `create_app` takes the limits and a clock as keyword arguments.
- `wav.py` — `validate_wav(bytes)` raises `InvalidWav` unless the upload is 16-bit PCM (plain or extensible), 1–2 channels, 8–48 kHz, 0 < frames ≤ 6 s, with data matching the declared length; `/separate` turns it into 400 `invalid audio` before separation. Any `wave` parse error maps to `InvalidWav`.
- `auth.py` — `load_token` creates/reads `backend/.auth_token` (mode 0600).
- `separation.py` — `separate(bytes)`: WAV → tensor → Demucs `htdemucs` (CUDA if available) → `vocals` + summed `no_vocals` WAV bytes. Loads the model at import.
- `stems.py` — stem name constants (`VOCALS`, `NO_VOCALS`, `STEMS`).

Runtime file `.auth_token` is generated, not committed. Never log audio, header values or tokens; 500 bodies stay generic (`Internal Server Error`).
