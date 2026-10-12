const test = require("node:test");
const assert = require("node:assert");
const { load } = require("./load");

function setup({ token = "tok", audible = true, contexts = [] } = {}) {
  const log = { badge: [], title: [], options: 0, offscreen: [], sent: [] };
  const h = {};
  const chrome = {
    runtime: {
      onMessage: { addListener: (f) => (h.message = f) },
      openOptionsPage: () => log.options++,
      getContexts: async () => contexts,
      sendMessage: async (m) => log.sent.push(m),
    },
    action: {
      onClicked: { addListener: (f) => (h.click = f) },
      setBadgeText: async (v) => log.badge.push(v.text),
      setTitle: async (v) => log.title.push(v.title),
    },
    storage: { local: { get: async () => (token ? { authToken: token } : {}) } },
    tabs: { get: async () => ({ audible }) },
    offscreen: { createDocument: async (o) => log.offscreen.push(o) },
    tabCapture: { getMediaStreamId: async () => "sid" },
  };
  load("background.js", { chrome });
  return { h, log };
}

test("click without token shows setup error and opens options", async () => {
  const { h, log } = setup({ token: null });
  await h.click({ id: 1 });
  assert.deepEqual(log.badge, ["!"]);
  assert.strictEqual(log.options, 1);
  assert.strictEqual(log.offscreen.length, 0);
});

test("click on silent tab skips capture", async () => {
  const { h, log } = setup({ audible: false });
  await h.click({ id: 1 });
  assert.strictEqual(log.offscreen.length, 0);
  assert.strictEqual(log.sent.length, 0);
});

test("click creates offscreen doc and sends stream id with token", async () => {
  const { h, log } = setup();
  await h.click({ id: 1 });
  assert.strictEqual(log.offscreen.length, 1);
  assert.deepEqual(log.sent, [{ type: "stream-id", streamId: "sid", token: "tok" }]);
});

test("click reuses existing offscreen doc", async () => {
  const { h, log } = setup({ contexts: [{}] });
  await h.click({ id: 1 });
  assert.strictEqual(log.offscreen.length, 0);
  assert.strictEqual(log.sent.length, 1);
});

test("backend-error auth sets badge and opens options", () => {
  const { h, log } = setup();
  h.message({ type: "backend-error", reason: "auth" });
  assert.deepEqual(log.badge, ["AUTH"]);
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
  h.message({ type: "stream-id" });
  assert.deepEqual(log.badge, []);
});
