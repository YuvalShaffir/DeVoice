# AGENTS.md

## JS test plan (extension)

Scope: `extension/*.js` (`background.js`, `capture-processor.js`, `offscreen.js`, `options.js`, `popup.js`). Python tests in `tests/*.py` cover backend and static extension checks (manifest, file references); JS behavior is tested here.

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
- `popup.test.js`: initial on/off render per capturing tab; stored error shown; toggle starts/stops capture; silent tab keeps off with note; settings link opens options; capture switch labeled "DeVoice on this tab" next to a Vocals switch; Vocals disabled with "Turn DeVoice on first" when not capturing / capturing another tab; reopened popup shows current Vocals state; Vocals click sends `set-vocals` with the flipped state and re-renders; start enables Vocals (off), stop disables it.
- `background.test.js`: `start-capture`: no token → setup badge + options page; silent tab → skip; happy path → offscreen doc created + `stream-id` message with token and tab id; existing offscreen doc reused; `get-status` with/without offscreen doc (passes `vocals` through, null when not capturing, incl. after stop); `backend-error` auth → badge + options page; unreachable → badge only; unrelated messages (incl. `set-vocals`) ignored.
- `capture-processor.test.js`: no input kept alive; chunk emitted after 6 s of samples; mono duplicated to right; silent chunk dropped; one loud channel kept.
- `offscreen.test.js`: unrelated messages ignored; `capture-status` / `stop-capture`; `set-vocals` fades the vocals gain to 1/0 over 50 ms, `no_vocals` untouched; `capture-status` reports `vocals`, last toggle wins; new Session resets vocals to removed; `set-vocals` without capture or after stop is a no-op; toggle racing a stop leaves vocals reset; mid-chunk toggle fades the live mix without restarting capture; chunk upload sends `X-Auth-Token`, fetches each stem, plays and revokes URLs; out-of-order chunks play in order and failed chunks skipped; 403 on `/separate` and `/stem` → auth error and capture stopped; `TypeError` → unreachable; 5xx → chunk skipped, capture continues; stale-session response dropped after `stopCapture`; `play()` rejection still completes the chunk; `encodeWav` header, stereo 16-bit PCM, clamping.

### Not covered / non-goals

- Real browser APIs, real audio output, real backend (see `tests/test_separation_integration.py` for backend).
- HTML pages and CSS (`popup.html`, `options.html`, `offscreen.html`), except the popup switch labels, which `popup.test.js` checks in the markup.
- Remaining uncovered branches: a few defensive optional-chaining paths in `offscreen.js` (`stopCapture` before first capture, etc.).

### Adding tests

New extension script → add `tests/js/<name>.test.js` using `load("<name>.js", fakes)`. Keep coverage on new code high; Sonar gates on it.
