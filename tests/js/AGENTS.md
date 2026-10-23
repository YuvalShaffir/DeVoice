# tests/js/

`node:test` tests for `extension/*.js`.

- `load.js` — helper: runs an extension script in a `vm` context with fake globals, using the real file path so `c8` attributes coverage.
- `background.test.js`, `popup.test.js`, `offscreen.test.js`, `options.test.js`, `capture-processor.test.js` — one per extension script.

Case list and conventions: root `AGENTS.md`.
