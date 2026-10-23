# AGENTS.md

## JS test plan (extension)

Scope: `extension/*.js` (`background.js`, `capture-processor.js`, `offscreen.js`, `options.js`). Python tests in `tests/*.py` cover backend and static extension checks (manifest, file references); JS behavior is tested here.

### Run

- `npm ci` once.
- `npm test` — run tests.
- `npm run coverage` — run with `c8`, writes `coverage/lcov.info` (read by SonarQube via `sonar.javascript.lcov.reportPaths`).
- CI: `ci.yml` runs `npm test`; `workflow.yml` runs `npm run coverage` before the Sonar scan.

### Approach

- Runner: Node built-in `node:test` + `node:assert`. No framework, no bundler.
- Extension scripts are plain browser scripts (no modules). `tests/js/load.js` loads one into a `vm` context with fake globals (`chrome`, `AudioContext`, `fetch`, ...) and the real file path, so `c8` attributes coverage to the source file.
- Top-level `let`/`const` state (e.g. `nextIndex`, `playing`, `processorNode`) is read via `run("expr")` evaluated inside the context.
- Fakes are minimal and hand-written per test file; they record calls into a `log` object that tests assert against.
- Cross-realm objects fail `deepStrictEqual`; use `assert.deepEqual`.
- Async flows are awaited with a `setImmediate` tick, no timers.

### Cases per file

- `options.test.js`: hint shown when token saved / not shown otherwise; empty input rejected; token trimmed, stored, badge cleared, input cleared.
- `background.test.js`: no token → setup badge + options page; silent tab → skip; happy path → offscreen doc created + `stream-id` message with token; existing offscreen doc reused; `backend-error` auth → badge + options page; unreachable → badge only; unrelated messages ignored.
- `capture-processor.test.js`: no input kept alive; chunk emitted after 6 s of samples; mono duplicated to right; silent chunk dropped; one loud channel kept.
- `offscreen.test.js`: unrelated messages ignored; chunk upload sends `X-Auth-Token`, fetches each stem, plays and revokes URLs; out-of-order chunks play in order and failed chunks skipped; 403 on `/separate` and `/stem` → auth error and capture stopped; `TypeError` → unreachable; 5xx → chunk skipped, capture continues; stale-session response dropped after `stopCapture`; `play()` rejection still completes the chunk; `encodeWav` header, stereo 16-bit PCM, clamping.

### Not covered / non-goals

- Real browser APIs, real audio output, real backend (see `tests/test_separation_integration.py` for backend).
- HTML pages (`popup.html`, `options.html`, `offscreen.html`).
- Remaining uncovered branches: a few defensive optional-chaining paths in `offscreen.js` (`stopCapture` before first capture, etc.).

### Adding tests

New extension script → add `tests/js/<name>.test.js` using `load("<name>.js", fakes)`. Keep coverage on new code high; Sonar gates on it.
