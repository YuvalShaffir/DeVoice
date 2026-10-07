import io
import os
import wave

import numpy as np
import torch
from demucs.api import Separator
from torch import Tensor

total_cores = os.cpu_count() or 1

DEMUCS_MODEL = "htdemucs"

VOCALS = "vocals"
NO_VOCALS = "no_vocals"


def _wav_bytes_to_tensor(data: bytes) -> tuple[torch.Tensor, int]:
    with wave.open(io.BytesIO(data), "rb") as wf:
        rate, channels = wf.getframerate(), wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return torch.from_numpy(samples.reshape(-1, channels).T.copy()), rate


def _tensor_to_wav_bytes(wav: torch.Tensor, rate: int) -> bytes:
    pcm = (wav.clamp(-1, 1).numpy() * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(pcm.shape[0])
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.T.reshape(-1).tobytes())
    return buf.getvalue()


def _sum_non_vocals(stems: dict[str, Tensor], vocals_tensor: Tensor) -> Tensor:
    no_vocals_tensor = torch.zeros_like(vocals_tensor)
    for stem in stems.values():
        no_vocals_tensor += stem
    return no_vocals_tensor


separator = Separator(
    model=DEMUCS_MODEL,
    device="cuda" if torch.cuda.is_available() else "cpu",
    jobs=max(1, total_cores - 1),
)


def separate(data: bytes) -> dict[str, bytes]:
    """
    Takes bytes data, processes it into tensors, splits the audio tensors using demucs

    :returns vocals and non-vocals
    """
    _, stems = separator.separate_tensor(*_wav_bytes_to_tensor(data))
    vocals_tensor = stems.pop(VOCALS)
    rate_out = separator.samplerate
    return {
        VOCALS: _tensor_to_wav_bytes(vocals_tensor.cpu(), rate_out),
        NO_VOCALS: _tensor_to_wav_bytes(
            _sum_non_vocals(stems, vocals_tensor).cpu(), rate_out
        ),
    }
