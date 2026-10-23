const test = require("node:test");
const assert = require("node:assert");
const { load } = require("./load");

function setup({ token = "tok", audible = true, contexts = [], status = { tabId: 7 }, lastError } = {}) {
  const log = { badge: [], title: [], options: 0, offscreen: [], sent: [], session: [], removed: [] };
  const h = {};
  const chrome = {
    runtime: {
      onMessage: { addListener: (f) => (h.message = f) },
      openOptionsPage: () => log.options++,
      getContexts: async () => contexts,
      sendMessage: async (m) => { log.sent.push(m); return status; },
    },
    action: {
      setBadgeText: async (v) => log.badge.push(v.text),
      setTitle: async (v) => log.title.push(v.title),
    },
    storage: {
      local: { get: async () => (token ? { authToken: token } : {}) },
      session: {
        get: async () => (lastError ? { lastError } : {}),
        set: (v) => log.session.push(v),
        remove: async (k) => log.removed.push(k),
      },
    },
    tabs: { get: async () => ({ audible }) },
    offscreen: { createDocument: async (o) => log.offscreen.push(o) },
    tabCapture: { getMediaStreamId: async () => "sid" },
  };
  load("background.js", { chrome });
  const ask = (msg) => new Promise((resolve) => {
    const async = h.message(msg, {}, resolve);
    assert.strictEqual(async, true);
  });
  return { h, log, ask };
}

test("start without token shows setup error and opens options", async () => {
  const { ask, log } = setup({ token: null });
  assert.deepEqual(await ask({ type: "start-capture", tabId: 1 }), { ok: false, reason: "setup" });
  assert.deepEqual(log.badge, ["!"]);
  assert.strictEqual(log.options, 1);
  assert.strictEqual(log.offscreen.length, 0);
});

test("start on silent tab skips capture", async () => {
  const { ask, log } = setup({ audible: false });
  assert.deepEqual(await ask({ type: "start-capture", tabId: 1 }), { ok: false, reason: "silent" });
  assert.strictEqual(log.offscreen.length, 0);
  assert.strictEqual(log.sent.length, 0);
});

test("start creates offscreen doc, sends stream id with token and tab, clears error", async () => {
  const { ask, log } = setup();
  assert.deepEqual(await ask({ type: "start-capture", tabId: 1 }), { ok: true });
  assert.strictEqual(log.offscreen.length, 1);
  assert.deepEqual(log.sent, [{ type: "stream-id", streamId: "sid", token: "tok", tabId: 1 }]);
  assert.deepEqual(log.badge, [""]);
  assert.deepEqual(log.removed, ["lastError"]);
});

test("start reuses existing offscreen doc", async () => {
  const { ask, log } = setup({ contexts: [{}] });
  await ask({ type: "start-capture", tabId: 1 });
  assert.strictEqual(log.offscreen.length, 0);
  assert.strictEqual(log.sent.length, 1);
});

test("get-status without offscreen doc reports not capturing", async () => {
  const { ask, log } = setup();
  assert.deepEqual(await ask({ type: "get-status" }), { tabId: null, error: null });
  assert.strictEqual(log.sent.length, 0);
});

test("get-status with offscreen doc returns capturing tab and stored error", async () => {
  const { ask } = setup({ contexts: [{}], lastError: "boom" });
  assert.deepEqual(await ask({ type: "get-status" }), { tabId: 7, error: "boom" });
});

test("backend-error auth sets badge and opens options", () => {
  const { h, log } = setup();
  h.message({ type: "backend-error", reason: "auth" });
  assert.deepEqual(log.badge, ["AUTH"]);
  assert.strictEqual(log.session.length, 1);
  assert.strictEqual(log.options, 1);
});

test("backend-error unreachable sets badge only", () => {
  const { h, log } = setup();
  h.message({ type: "backend-error", reason: "unreachable" });
  assert.deepEqual(log.badge, ["DOWN"]);
  assert.strictEqual(log.options, 0);
});

test("other messages ignored", () => {
  const { h, log } = setup();
  assert.strictEqual(h.message({ type: "stream-id" }, {}, () => {}), undefined);
  assert.deepEqual(log.badge, []);
});
