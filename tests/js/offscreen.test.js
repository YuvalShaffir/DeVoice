const test = require("node:test");
const assert = require("node:assert");
const { load } = require("./load");

const tick = () => new Promise((r) => setImmediate(r));

function setup({ fetchImpl } = {}) {
  const log = { sent: [], fetches: [], audios: [], closed: 0, trackStops: 0, revoked: [] };
  const h = {};
  const param = () => ({
    value: 1, ramps: [],
    cancelScheduledValues() {},
    setValueAtTime(v) { this.value = v; },
    linearRampToValueAtTime(v, t) { this.ramps.push([v, t]); },
  });
  const node = () => ({ connect() {}, disconnect() {}, gain: param() });
  class AudioContext {
    constructor() { this.destination = {}; this.currentTime = 10; this.audioWorklet = { addModule: async () => {} }; }
    createGain() { return node(); }
    createMediaStreamSource() { return node(); }
    createMediaElementSource() { return node(); }
    async resume() {}
    async close() { log.closed++; }
  }
  class AudioWorkletNode {
    constructor() { this.port = {}; }
    connect() {}
  }
  class Audio {
    constructor(url) {
      this.url = url; this.listeners = {}; log.audios.push(this);
    }
    addEventListener(ev, f) { this.listeners[ev] = f; }
    play() { return this.playResult ?? Promise.resolve(); }
  }
  let urlId = 0;
  const g = {
    chrome: {
      runtime: {
        onMessage: { addListener: (f) => (h.message = f) },
        sendMessage: (m) => log.sent.push(m),
      },
    },
    navigator: { mediaDevices: { getUserMedia: async () => ({ getTracks: () => [{ stop: () => log.trackStops++ }] }) } },
    AudioContext, AudioWorkletNode, Audio,
    fetch: async (url, opts) => {
      log.fetches.push({ url, opts });
      return fetchImpl(url, opts);
    },
    URL: { createObjectURL: () => `blob:${urlId++}`, revokeObjectURL: (u) => log.revoked.push(u) },
  };
  const env = load("offscreen.js", g);
  const ask = (msg) => new Promise((resolve) => h.message(msg, {}, resolve));
  return { ...env, h, log, ask };
}

const json = (body, status = 200) => ({ status, ok: status < 400, json: async () => body });
const blobRes = (status = 200) => ({ status, ok: status < 400, blob: async () => ({}) });

function happyFetch(url) {
  if (url.endsWith("/separate")) return json({ id: "x", stems: ["vocals", "no_vocals"] });
  return blobRes();
}

async function start(env) {
  env.h.message({ type: "stream-id", streamId: "sid", token: "tok", tabId: 5 });
  await tick();
}

const gain = (env, stem) => env.run(`stemGains.${stem}.gain`);

const chunk = (env, index = 1) => {
  const left = new Float32Array([0, 0.5, -0.5, 2, -2]);
  env.run("processorNode").port.onmessage({ data: { left, right: left, sampleRate: 100 } });
};

test("capture-status reports capturing tab, stop-capture stops and clears it", async () => {
  const env = setup({ fetchImpl: happyFetch });
  const { ask } = env;
  assert.deepEqual(await ask({ type: "capture-status" }), { tabId: undefined, vocals: false });
  await start(env);
  assert.deepEqual(await ask({ type: "capture-status" }), { tabId: 5, vocals: false });
  assert.deepEqual(await ask({ type: "stop-capture" }), { ok: true });
  assert.deepEqual(await ask({ type: "capture-status" }), { tabId: undefined, vocals: false });
  assert.strictEqual(env.log.trackStops, 1);
});

test("ignores unrelated messages", async () => {
  const env = setup({ fetchImpl: happyFetch });
  env.h.message({ type: "other" });
  await tick();
  assert.strictEqual(env.run("typeof processorNode"), "undefined");
  assert.strictEqual(env.run("processorNode"), undefined);
});

test("chunk is sent with token, stems fetched and played in order", async () => {
  const env = setup({ fetchImpl: happyFetch });
  await start(env);
  chunk(env);
  await tick(); await tick();

  assert.strictEqual(env.log.fetches[0].url, "http://127.0.0.1:8000/separate");
  assert.strictEqual(env.log.fetches[0].opts.headers["X-Auth-Token"], "tok");
  assert.strictEqual(env.log.fetches.length, 3);
  assert.strictEqual(env.log.audios.length, 2);

  for (const a of env.log.audios) a.listeners.ended();
  await tick();
  assert.strictEqual(env.log.revoked.length, 2);
  assert.strictEqual(env.run("playing"), false);
});

test("out-of-order chunks play in order; failed chunk skipped", async () => {
  const env = setup({ fetchImpl: happyFetch });
  await start(env);
  env.run("enqueue(2, null)");
  assert.strictEqual(env.run("nextIndex"), 1);
  env.run("enqueue(1, null)");
  assert.strictEqual(env.run("nextIndex"), 3);
});

test("403 on /separate reports auth and stops capture", async () => {
  const env = setup({ fetchImpl: () => json({}, 403) });
  await start(env);
  chunk(env);
  await tick(); await tick();
  assert.deepEqual(env.log.sent, [{ type: "backend-error", reason: "auth" }]);
  assert.strictEqual(env.run("processorNode"), undefined);
  assert.strictEqual(env.log.trackStops, 1);
});

test("403 on /stem reports auth", async () => {
  const env = setup({
    fetchImpl: (url) => (url.endsWith("/separate") ? json({ id: "x", stems: ["vocals"] }) : blobRes(403)),
  });
  await start(env);
  chunk(env);
  await tick(); await tick();
  assert.deepEqual(env.log.sent, [{ type: "backend-error", reason: "auth" }]);
});

test("network failure reports unreachable", async () => {
  const env = setup({ fetchImpl: () => { throw new TypeError("fetch failed"); } });
  await start(env);
  chunk(env);
  await tick(); await tick();
  assert.deepEqual(env.log.sent, [{ type: "backend-error", reason: "unreachable" }]);
});

test("server error skips chunk without stopping capture", async () => {
  const env = setup({ fetchImpl: () => json({}, 500) });
  await start(env);
  chunk(env);
  await tick(); await tick();
  assert.strictEqual(env.log.sent.length, 0);
  assert.strictEqual(env.run("nextIndex"), 2);
});

test("stale session response is dropped", async () => {
  let release;
  const gate = new Promise((r) => (release = r));
  const env = setup({ fetchImpl: async (url) => { await gate; return happyFetch(url); } });
  await start(env);
  chunk(env);
  await env.run("stopCapture()");
  release();
  await tick(); await tick();
  assert.strictEqual(env.log.fetches.length, 1);
  assert.strictEqual(env.log.audios.length, 0);
});

test("play() rejection still finishes chunk", async () => {
  const env = setup({ fetchImpl: happyFetch });
  await start(env);
  env.ctx.Audio.prototype.play = () => Promise.reject(new Error("blocked"));
  env.run("enqueue(1, {vocals: {}})");
  await tick();
  assert.strictEqual(env.log.revoked.length, 1);
  assert.strictEqual(env.run("playing"), false);
});

test("encodeWav writes stereo 16-bit PCM header and clamps", async () => {
  const env = setup({ fetchImpl: happyFetch });
  const blob = env.run("encodeWav(new Float32Array([1, -1, 2]), new Float32Array([0, 0, -2]), 8000)");
  const view = new DataView(await blob.arrayBuffer());
  assert.strictEqual(blob.size, 44 + 3 * 4);
  assert.strictEqual(view.getUint32(24, true), 8000);
  assert.strictEqual(view.getUint16(22, true), 2);
  assert.strictEqual(view.getInt16(44, true), 0x7fff);
  assert.strictEqual(view.getInt16(48, true), -0x8000);
  assert.strictEqual(view.getInt16(54, true), -0x8000);
});

test("set-vocals fades the vocals stem in and out over 50 ms, music untouched", async () => {
  const env = setup({ fetchImpl: happyFetch });
  await start(env);
  assert.strictEqual(gain(env, "vocals").value, 0);

  assert.deepEqual(await env.ask({ type: "set-vocals", on: true }), { ok: true });
  assert.deepEqual(gain(env, "vocals").ramps.at(-1), [1, 10.05]);

  await env.ask({ type: "set-vocals", on: false });
  assert.deepEqual(gain(env, "vocals").ramps.at(-1), [0, 10.05]);
  assert.deepEqual(gain(env, "no_vocals").ramps, []);
});

test("capture-status reports the vocals state; last toggle wins", async () => {
  const env = setup({ fetchImpl: happyFetch });
  await start(env);
  await env.ask({ type: "set-vocals", on: true });
  assert.deepEqual(await env.ask({ type: "capture-status" }), { tabId: 5, vocals: true });
  await env.ask({ type: "set-vocals", on: false });
  assert.deepEqual(await env.ask({ type: "capture-status" }), { tabId: 5, vocals: false });
});

test("every new capture Session starts with vocals removed", async () => {
  const env = setup({ fetchImpl: happyFetch });
  await start(env);
  await env.ask({ type: "set-vocals", on: true });
  await env.ask({ type: "stop-capture" });
  await start(env);
  assert.strictEqual(gain(env, "vocals").value, 0);
  assert.deepEqual(await env.ask({ type: "capture-status" }), { tabId: 5, vocals: false });
});

test("set-vocals without capture is a no-op", async () => {
  const env = setup({ fetchImpl: happyFetch });
  assert.deepEqual(await env.ask({ type: "set-vocals", on: true }), { ok: true });
  assert.deepEqual(await env.ask({ type: "capture-status" }), { tabId: undefined, vocals: false });
});

test("set-vocals after stop-capture is a no-op", async () => {
  const env = setup({ fetchImpl: happyFetch });
  await start(env);
  await env.ask({ type: "stop-capture" });
  assert.deepEqual(await env.ask({ type: "set-vocals", on: true }), { ok: true });
  assert.deepEqual(await env.ask({ type: "capture-status" }), { tabId: undefined, vocals: false });
});

test("set-vocals racing stop-capture leaves vocals reset", async () => {
  const env = setup({ fetchImpl: happyFetch });
  await start(env);
  const stopped = env.ask({ type: "stop-capture" });
  assert.deepEqual(await env.ask({ type: "set-vocals", on: true }), { ok: true });
  await stopped;
  assert.deepEqual(await env.ask({ type: "capture-status" }), { tabId: undefined, vocals: false });
});

test("set-vocals mid-chunk fades the live mix without restarting capture", async () => {
  const env = setup({ fetchImpl: happyFetch });
  await start(env);
  env.run("enqueue(1, {vocals: {}, no_vocals: {}})");
  assert.strictEqual(env.run("playing"), true);
  await env.ask({ type: "set-vocals", on: true });
  assert.deepEqual(gain(env, "vocals").ramps, [[1, 10.05]]);
  assert.strictEqual(env.run("playing"), true);
  assert.strictEqual(env.log.closed, 0);
});
