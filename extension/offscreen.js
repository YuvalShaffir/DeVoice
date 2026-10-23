const BACKEND = "http://127.0.0.1:8000";
const DEFAULT_GAINS = { vocals: 0, no_vocals: 1};

let mixerCtx;
const stemGains = {};

function buildMixer() {
    mixerCtx = new AudioContext();
    for (const [stem, val] of Object.entries(DEFAULT_GAINS)) {
        const node = mixerCtx.createGain()
        node.gain.value = val;
        node.connect(mixerCtx.destination);
        stemGains[stem] = node;
    }
}

chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type !== "stream-id") return;
    void startCapture(msg.streamId, msg.token);
});

let captureCtx, processorNode, captureStream;
let chunkIndex = 0;
let session = 0;

async function stopCapture() {
    session += 1;
    if (processorNode) processorNode.port.onmessage = null;
    captureStream?.getTracks().forEach((t) => t.stop());
    await captureCtx?.close();
    await mixerCtx?.close();
    captureCtx = mixerCtx = processorNode = captureStream = undefined;
    ready.clear();
    nextIndex = 1;
    chunkIndex = 0;
    playing = false;
}

async function startCapture(streamId, token) {
    await stopCapture();

    captureStream = await navigator.mediaDevices.getUserMedia({
        audio: {
            mandatory: {
                chromeMediaSource: "tab",
                chromeMediaSourceId: streamId,
            },
        },
    });

    buildMixer();
    await mixerCtx.resume();

    captureCtx = new AudioContext();
    const source = captureCtx.createMediaStreamSource(captureStream);

    await captureCtx.audioWorklet.addModule("capture-processor.js");

    processorNode = new AudioWorkletNode(captureCtx, "capture-processor", {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        outputChannelCount: [2],
    });

    const silentSink = captureCtx.createGain();
    silentSink.gain.value = 0;

    source.connect(processorNode);
    processorNode.connect(silentSink);
    silentSink.connect(captureCtx.destination);

    processorNode.port.onmessage = (e) => {
        const {left, right, sampleRate} = e.data;
        chunkIndex += 1;
        void processChunk(chunkIndex, left, right, sampleRate, token);
    }
}



async function processChunk(index, left, right, rate, token) {
    const mySession = session;
    const headers = {"X-Auth-Token": token};

    try {
        const form = new FormData();
        form.append("file", encodeWav(left, right, rate), "chunk.wav");

        const res = await fetch(
            `${BACKEND}/separate`,
            {
                method: "POST",
                body: form,
                headers: headers
            }
        )
        if (mySession !== session) return;
        if (res.status === 403) return fail("auth");
        if (!res.ok) throw new Error(`/separate returned ${res.status}`);
        const {id, stems} = await res.json();

        const blobs = {};
        await Promise.all(stems.map(async (stem) => {
            const r = await fetch(
                `${BACKEND}/stem/${id}/${stem}`,
                {headers: headers}
            )
            if (r.status === 403) throw Object.assign(new Error("auth"), {reason: "auth"});
            if (!r.ok) throw new Error(`/stem returned ${r.status}`);
            blobs[stem] = await r.blob()
        }));

        if (mySession !== session) return;
        enqueue(index, blobs);
    } catch (err) {
        if (err.reason === "auth") return fail("auth");
        if (err instanceof TypeError) return fail("unreachable");
        console.error("[offscrean] chunk", index, "failed:", err);
        enqueue(index, null);
    }
}

function encodeWav(left, right, sr) {
  const length = left.length;
  const buffer = new ArrayBuffer(44 + length * 4);
  const view = new DataView(buffer);
  const writeStr = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };

  writeStr(0, "RIFF"); view.setUint32(4, 36 + length * 4, true); writeStr(8, "WAVE");
  writeStr(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 2, true); view.setUint32(24, sr, true); view.setUint32(28, sr * 4, true);
  view.setUint16(32, 4, true); view.setUint16(34, 16, true);
  writeStr(36, "data"); view.setUint32(40, length * 4, true);

  let offset = 44;
  for (let i = 0; i < length; i++) {
    const l = Math.max(-1, Math.min(1, left[i]));
    const r = Math.max(-1, Math.min(1, right[i]));
    view.setInt16(offset, l < 0 ? l * 0x8000 : l * 0x7fff, true); offset += 2;
    view.setInt16(offset, r < 0 ? r * 0x8000 : r * 0x7fff, true); offset += 2;
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function fail(reason) {
  chrome.runtime.sendMessage({ type: "backend-error", reason });
  void stopCapture();
}

const ready = new Map();
let nextIndex = 1;
let playing = false;

function enqueue(index, blobs) {
    ready.set(index, blobs);
    pump();
}

function pump() {
    if (playing || !ready.has(nextIndex)) return;
    const blobs = ready.get(nextIndex);
    ready.delete(nextIndex);
    nextIndex += 1;
    if (!blobs) return pump();
    playing = true;
    void playChunk(blobs).then(() => {playing = false; pump();});
}

function playChunk(blobs) {
    return new Promise((resolve) => {
        const parts = Object.entries(blobs).map(([stem, blob]) => {
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            const src = mixerCtx.createMediaElementSource(audio);
            src.connect(stemGains[stem]);
            return {url, audio, src}
        });

        let finished = false;
        const done = () => {
            if (finished) return;
            finished = true;

            for (const {url, src} of parts) {
                src.disconnect();
                URL.revokeObjectURL(url);
            }
            resolve();
        };

        let remaining = parts.length;
        for (const {audio} of parts) {
            audio.addEventListener("ended", () => {if (--remaining === 0) done();});
            audio.play().catch(done);
        }
    })
}
