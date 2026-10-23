const test = require("node:test");
const assert = require("node:assert");
const { load } = require("./load");

function setup(stored) {
  const els = {
    token: { value: "" },
    status: { textContent: "" },
    save: { handler: null, addEventListener(_, h) { this.handler = h; } },
  };
  const calls = { set: [], badge: [] };
  const chrome = {
    storage: { local: {
      get: async () => stored,
      set: async (v) => calls.set.push(v),
    } },
    action: { setBadgeText: async (v) => calls.badge.push(v) },
  };
  load("options.js", { chrome, document: { getElementById: (id) => els[id] } });
  return { els, calls };
}

const tick = () => new Promise((r) => setImmediate(r));

test("shows hint when token already saved", async () => {
  const { els } = setup({ authToken: "abc" });
  await tick();
  assert.match(els.status.textContent, /already|saved/i);
});

test("no hint when nothing saved", async () => {
  const { els } = setup({});
  await tick();
  assert.strictEqual(els.status.textContent, "");
});

test("save rejects empty input", async () => {
  const { els, calls } = setup({});
  els.token.value = "   ";
  await els.save.handler();
  assert.strictEqual(calls.set.length, 0);
  assert.match(els.status.textContent, /Paste the token/);
});

test("save stores trimmed token, clears badge and input", async () => {
  const { els, calls } = setup({});
  els.token.value = "  tok  ";
  await els.save.handler();
  assert.deepEqual(calls.set, [{ authToken: "tok" }]);
  assert.deepEqual(calls.badge, [{ text: "" }]);
  assert.strictEqual(els.token.value, "");
  assert.match(els.status.textContent, /Saved/);
});
