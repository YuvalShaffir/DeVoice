# tests/

- `test_auth.py` — token load/generation and `X-Auth-Token` / CORS enforcement on the API (fake `separate`).
- `test_separation.py` — `backend/separation.py` unit tests with Demucs `Separator` faked.
- `test_separation_integration.py` — real Demucs on a synthetic clip; marked `slow`.
- `test_manifest.py` — static checks on `extension/manifest.json`.
- `test_capture_pipeline.py` — static checks that extension files and references line up (worklet path, permissions).
- `js/` — JS behavior tests for the extension; see `js/AGENTS.md`.

Run Python tests with `uv run pytest`. JS tests: `npm test` (see root `AGENTS.md`).
