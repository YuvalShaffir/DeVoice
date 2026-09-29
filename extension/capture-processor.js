const CHUNK_SECONDS = 6;

class CaptureProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.leftChunks = [];
        this.rightChuncks = [];
        this.samplesSinceCnt = 0;
    }

    process(inputs) {
        const input = inputs[0];
        if (input.length === 0) return true;

        this.leftChunks.push(new Float32Array(input[0]));
        this.rightChuncks.push(new Float32Array(input[1] ?? input[0]));
        this.samplesSinceCnt += input[0].length;

        const target = CHUNK_SECONDS * sampleRate;
        if (this.samplesSinceCnt >= target) {
            this.cutChunk();
            this.samplesSinceCnt = 0;
        }

        return true;
    }

    cutChunk() {
        const left = concatChunks(this.leftChunks);
        const right = concatChunks(this.rightChuncks);
        this.leftChunks = [];
        this.rightChuncks = [];
        if (isSilent(left) && isSilent(right)) return;
        this.port.postMessage({left, right, sampleRate}, [left.buffer, right.buffer]);
    }
}

const SILENCE_THRESHOLD = 1e-4;

function isSilent(samples) {
    for (let i = 0; i < samples.length; i++) {
        if (Math.abs(samples[i]) > SILENCE_THRESHOLD) return false;
    }
    return true;
}

function concatChunks(chunks) {
    const total = chunks.reduce((n, c) => n + c.length, 0);
    const out = new Float32Array(total);
    let offset = 0;
    for (const c of chunks) {
        out.set(c, offset);
        offset += c.length;
    }
    return out;
}

registerProcessor("capture-processor", CaptureProcessor);
