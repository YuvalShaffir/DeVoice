const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const { load } = require("./load");

const tick = () => new Promise((r) => setImmediate(r));

function setup({ status = { tabId: null, error: null, vocals: null }, startResult = { ok: true } } = {}) {
  const log = { sent: [], vocals: [], options: 0 };
  const els = {};
  const el = (id) => (els[id] ??= {
    id, hidden: false, disabled: false, textContent: "", attrs: {}, listeners: {},
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k]; },
    addEventListener(ev, f) { this.listeners[ev] = f; },
  });
  let current = status;
  const chrome = {
    tabs: { query: async () => [{ id: 1 }] },
    runtime: {
      openOptionsPage: () => log.options++,
      sendMessage: async (m) => {
        log.sent.push(m.type);
        if (m.type === "get-status") return current;
        if (m.type === "start-capture") {
          if (startResult.ok) current = { ...current, tabId: m.tabId, vocals: false };
          return startResult;
        }
        if (m.type === "stop-capture") current = { ...current, tabId: null, vocals: null };
        if (m.type === "set-vocals") {
          log.vocals.push(m.on);
          current = { ...current, vocals: m.on };
        }
        return { ok: true };
      },
    },
  };
  load("popup.js", { chrome, document: { getElementById: el } });
  return { els, log };
}

test("initial render: off when not capturing this tab", async () => {
  const { els } = setup();
  await tick();
  assert.strictEqual(els.toggle.attrs["aria-checked"], "false");
  assert.strictEqual(els.toggle.disabled, false);
  assert.strictEqual(els.error.hidden, true);
});

test("initial render: on when capturing this tab", async () => {
  const { els } = setup({ status: { tabId: 1, error: null } });
  await tick();
  assert.strictEqual(els.toggle.attrs["aria-checked"], "true");
  assert.match(els.state.textContent, /^On/);
});

test("capturing another tab shows off", async () => {
  const { els } = setup({ status: { tabId: 2, error: null } });
  await tick();
  assert.strictEqual(els.toggle.attrs["aria-checked"], "false");
});

test("stored error is shown", async () => {
  const { els } = setup({ status: { tabId: null, error: "boom" } });
  await tick();
  assert.strictEqual(els.error.hidden, false);
  assert.strictEqual(els.error.textContent, "boom");
});

test("click when off starts capture and shows on", async () => {
  const { els, log } = setup();
  await tick();
  await els.toggle.listeners.click();
  assert.deepEqual(log.sent, ["get-status", "start-capture", "get-status"]);
  assert.strictEqual(els.toggle.attrs["aria-checked"], "true");
});

test("click when on stops capture and shows off", async () => {
  const { els, log } = setup({ status: { tabId: 1, error: null } });
  await tick();
  await els.toggle.listeners.click();
  assert.deepEqual(log.sent, ["get-status", "stop-capture", "get-status"]);
  assert.strictEqual(els.toggle.attrs["aria-checked"], "false");
});

test("silent tab keeps toggle off with note", async () => {
  const { els } = setup({ startResult: { ok: false, reason: "silent" } });
  await tick();
  await els.toggle.listeners.click();
  assert.strictEqual(els.toggle.attrs["aria-checked"], "false");
  assert.match(els.state.textContent, /No audio/);
  assert.strictEqual(els.toggle.disabled, false);
});

test("failed start shows error and keeps toggle off", async () => {
  const { els } = setup({ startResult: { ok: false, reason: "setup" } });
  await tick();
  await els.toggle.listeners.click();
  assert.strictEqual(els.toggle.attrs["aria-checked"], "false");
});

test("settings link opens options page", async () => {
  const { els, log } = setup();
  await tick();
  let prevented = false;
  els.settings.listeners.click({ preventDefault: () => (prevented = true) });
  assert.strictEqual(log.options, 1);
  assert.ok(prevented);
});

test("capture switch is labeled DeVoice on this tab, next to a Vocals switch", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "..", "extension", "popup.html"), "utf8");
  assert.match(html, /id="label"[^>]*>DeVoice on this tab</);
  assert.match(html, /id="vocals-label"[^>]*>Vocals</);
  assert.match(html, /id="vocals"[^>]*role="switch"[^>]*aria-labelledby="vocals-label"/);
});

for (const [name, status] of [
  ["not capturing", { tabId: null, error: null, vocals: null }],
  ["capturing another tab", { tabId: 2, error: null, vocals: true }],
]) {
  test(`vocals switch disabled with hint when ${name}`, async () => {
    const { els } = setup({ status });
    await tick();
    assert.strictEqual(els.vocals.disabled, true);
    assert.strictEqual(els.vocals.attrs["aria-checked"], "false");
    assert.strictEqual(els["vocals-state"].textContent, "Turn DeVoice on first");
  });
}

test("reopened popup shows the current vocals state", async () => {
  const off = setup({ status: { tabId: 1, error: null, vocals: false } });
  await tick();
  assert.strictEqual(off.els.vocals.disabled, false);
  assert.strictEqual(off.els.vocals.attrs["aria-checked"], "false");
  assert.match(off.els["vocals-state"].textContent, /removed/);

  const on = setup({ status: { tabId: 1, error: null, vocals: true } });
  await tick();
  assert.strictEqual(on.els.vocals.attrs["aria-checked"], "true");
  assert.match(on.els["vocals-state"].textContent, /audible/);
});

test("clicking vocals sends set-vocals with the flipped state and re-renders", async () => {
  const { els, log } = setup({ status: { tabId: 1, error: null, vocals: false } });
  await tick();
  await els.vocals.listeners.click();
  assert.deepEqual(log.vocals, [true]);
  assert.strictEqual(els.vocals.attrs["aria-checked"], "true");

  await els.vocals.listeners.click();
  assert.deepEqual(log.vocals, [true, false]);
  assert.strictEqual(els.vocals.attrs["aria-checked"], "false");
});

test("starting capture enables vocals switch off; stopping disables it", async () => {
  const { els } = setup();
  await tick();
  await els.toggle.listeners.click();
  assert.strictEqual(els.vocals.disabled, false);
  assert.strictEqual(els.vocals.attrs["aria-checked"], "false");
  await els.toggle.listeners.click();
  assert.strictEqual(els.vocals.disabled, true);
});
