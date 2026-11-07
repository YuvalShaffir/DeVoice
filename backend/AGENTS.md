# backend/

FastAPI service that separates audio into vocals / no-vocals stems with Demucs. Listens on `127.0.0.1:8000`.

- `main.py` — entrypoint (`app`). Wires token, `separate`, and extension origin (`EXTENSION_ID` env var).
- `server.py` — `create_app(...)`: wraps routes in `RequestGuard`, CORS-locked to the extension origin (CORS outermost, so preflights pass and guard errors carry CORS headers). `POST /separate` (raw `audio/wav` body, else 415 → SHA-256 id, stems held in memory; no multipart, which spools to disk), `GET /stem/{hash}/{stem}` (serves each stem once, then drops it). Docs endpoints disabled.
- `guard.py` — `RequestGuard` ASGI middleware, checks run before any body byte is read: `Host` must be `127.0.0.1` (any port) → else 400; `X-Auth-Token` constant-time compare → else 403; `POST /separate` needs `Content-Length` (411 missing, 400 invalid, 413 over `MAX_BODY` = 2 MB); bodies streamed past 2 MB → 413. `OPTIONS` passes through to CORS / router. It is middleware because FastAPI dependencies run only after the body is parsed.
- `api.py` — HTTP contract constants shared by server, guard and tests: route paths, `TOKEN_HEADER`, `WAV_MEDIA_TYPE`, `extension_origin(id)`.
- `auth.py` — `load_token` creates/reads `backend/.auth_token` (mode 0600).
- `separation.py` — `separate(bytes)`: WAV → tensor → Demucs `htdemucs` (CUDA if available) → `vocals` + summed `no_vocals` WAV bytes. Loads the model at import.
- `stems.py` — stem name constants (`VOCALS`, `NO_VOCALS`, `STEMS`).

Runtime file `.auth_token` is generated, not committed.
