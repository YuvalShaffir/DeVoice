chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type !== "stream-id") return;
    startCapture(msg.streamId);
});

let captureCtx, processorNode, chunkIndex;

async function startCapture(streamId) {
    const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
            mandatory: {
                chromeMediaSource: "tab",
                chromeMediaSourceId: streamId,
            },
        },
    });

    captureCtx = new AudioContext();
    const source = captureCtx.createMediaStreamSource(stream);

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
        console.log("[offscreen] cut chunk", chunkIndex, "samples:", left.length);
        saveChunkAsWav(left, right, sampleRate, chunkIndex);
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

function saveChunkAsWav(left, right, sr, index) {
  const blob = encodeWav(left, right, sr);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `chunk-${index}.wav`;
  a.click();
  console.log("[offscreen] downloaded chunk", index);
}
