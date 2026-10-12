const test = require("node:test");
const assert = require("node:assert");
const { load } = require("./load");

function setup(sampleRate = 10) {
  let Ctor;
  load("capture-processor.js", {
    sampleRate,
    AudioWorkletProcessor: class { constructor() { this.port = { posted: [], postMessage: (m) => this.port.posted.push(m) }; } },
    registerProcessor: (_, c) => (Ctor = c),
  });
  return new Ctor();
}

const loud = (n) => new Float32Array(n).fill(0.5);

test("no input channels keeps processor alive", () => {
  const p = setup();
  assert.strictEqual(p.process([[]]), true);
  assert.strictEqual(p.port.posted.length, 0);
});

test("emits chunk after 6 seconds of audio", () => {
  const p = setup(10); // 60 samples per chunk
  p.process([[loud(30), loud(30)]]);
  assert.strictEqual(p.port.posted.length, 0);
  p.process([[loud(30), loud(30)]]);
  assert.strictEqual(p.port.posted.length, 1);
  const { left, right, sampleRate } = p.port.posted[0];
  assert.strictEqual(left.length, 60);
  assert.strictEqual(right.length, 60);
  assert.strictEqual(sampleRate, 10);
});

test("mono input duplicates to right channel", () => {
  const p = setup(10);
  p.process([[loud(60)]]);
  assert.strictEqual(p.port.posted[0].right[0], 0.5);
});

test("silent chunk dropped", () => {
  const p = setup(10);
  p.process([[new Float32Array(60), new Float32Array(60)]]);
  assert.strictEqual(p.port.posted.length, 0);
});

test("chunk kept when only one channel is loud", () => {
  const p = setup(10);
  p.process([[new Float32Array(60), loud(60)]]);
  assert.strictEqual(p.port.posted.length, 1);
});
