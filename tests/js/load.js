const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const EXTENSION_DIR = path.join(__dirname, "..", "..", "extension");

// Run an extension script (plain browser script, no modules) against fake globals.
// Returns the context so tests can poke at top-level state via ctx.eval().
function load(name, globals = {}) {
  const file = path.join(EXTENSION_DIR, name);
  const ctx = vm.createContext({
    console: { log() {}, error() {} },
    Float32Array, ArrayBuffer, DataView, Blob, FormData, URL, Math, Promise, Object, Error, TypeError, Array, Map,
    ...globals,
  });
  vm.runInContext(fs.readFileSync(file, "utf8"), ctx, { filename: file });
  return { ctx, run: (code) => vm.runInContext(code, ctx) };
}

module.exports = { load };
