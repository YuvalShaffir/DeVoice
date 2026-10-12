# backend/

FastAPI service that separates audio into vocals / no-vocals stems with Demucs. Listens on `127.0.0.1:8000`.

- `main.py` — entrypoint (`app`). Wires token, `separate`, cache dir, and extension origin (`EXTENSION_ID` env var).
- `server.py` — `create_app(...)`: token-gated, CORS-locked to the extension origin. `POST /separate` (WAV upload → SHA-256 id, cached stems), `GET /stem/{hash}/{stem}` (serves cached WAV). Docs endpoints disabled.
- `auth.py` — `load_token` creates/reads `backend/.auth_token` (mode 0600); `make_require_token` builds the `X-Auth-Token` check (constant-time compare, 403 on mismatch).
- `separation.py` — `separate(bytes)`: WAV → tensor → Demucs `htdemucs` (CUDA if available) → `vocals` + summed `no_vocals` WAV bytes. Loads the model at import.
- `stems.py` — stem name constants (`VOCALS`, `NO_VOCALS`, `STEMS`).

Runtime files (`.auth_token`, `cache/`) are generated, not committed.
