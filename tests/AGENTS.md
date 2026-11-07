# tests/

- `test_auth.py` — token load/generation and `X-Auth-Token` / CORS enforcement on the API (fake `separate`).
- `test_guard.py` — `RequestGuard` via `create_app`: Host, token, `Content-Length` and streamed-size checks; raw ASGI calls prove rejected requests never read the body.
- `test_upload.py` — `POST /separate` accepts only a raw `audio/wav` body (415 otherwise); upload + stem round trip under disk-write traps (tempfile factories, write-mode `open`) proves audio stays in RAM.
- `test_limits.py` — queue (one run at a time, 429 when full, 504 keeps the slot until the thread returns, slot freed after a crash) via `httpx.AsyncClient`, and result expiry with a fake clock.
- `test_wav.py` — `validate_wav` accept/reject cases, the 400 path, and seeded fuzzing (bit flips, truncation, header overrides, random bytes): anything but `InvalidWav` fails.
- `wav_factory.py` — `make_wav(...)` / `chunk(...)` build WAVs field by field, including headers `wave` won't write. Uploads must be valid WAVs (`api_client.VALID_WAV`).
- `test_startup.py` — extension ID from a manifest key (fake-key vector, repo manifest well-formed), clear errors for bad manifests, root/Administrator refusal, `EXTENSION_ID` gone from code and docs.
- `test_logging.py` — round trip and 400/403/413/500 paths log no token, header value or audio; 500 body is generic.
- `test_separation.py` — `backend/separation.py` unit tests with Demucs `Separator` faked.
- `test_separation_integration.py` — real Demucs on a synthetic clip; marked `slow`.
- `test_manifest.py` — static checks on `extension/manifest.json`.
- `test_capture_pipeline.py` — static checks that extension files and references line up (worklet path, permissions).
- `js/` — JS behavior tests for the extension; see `js/AGENTS.md`.

Shared API test setup: `conftest.py` (`make_app(separate=..., **limits)`, `app`, `client`, `separated` fixtures) and `api_client.py` (`TOKEN`, a random-ID `ORIGIN`, `VALID_WAV`, `auth_headers`, `upload`, `fetch_stem`). Take paths and header names from `backend/api.py`, never as literals. `TestClient` must use `BASE_URL` (`http://127.0.0.1`); the default `Host: testserver` is rejected.

Run Python tests with `uv run pytest`. JS tests: `npm test` (see root `AGENTS.md`).
