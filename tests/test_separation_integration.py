import io
import wave

import pytest
import torch
from separation import _wav_bytes_to_tensor, separate

pytestmark = pytest.mark.slow

RATE = 44100
SECONDS = 3


def synthetic_mix() -> bytes:
    """Deterministic stereo clip: a few tones plus low noise, so it is clearly non-silent."""
    gen = torch.Generator().manual_seed(0)
    t = torch.arange(RATE * SECONDS) / RATE
    tones = sum(0.1 * torch.sin(2 * torch.pi * f * t) for f in (220.0, 440.0, 880.0))
    noise = 0.02 * torch.randn(len(t), generator=gen)
    mono = (tones + noise).clamp(-1, 1)
    pcm = (mono * 32767).to(torch.int16)
    stereo = torch.stack([pcm, pcm], dim=1).reshape(-1)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(stereo.numpy().tobytes())
    return buf.getvalue()


@pytest.fixture(scope="module")
def result():
    return separate(synthetic_mix())


def decode(data: bytes):
    return _wav_bytes_to_tensor(data)


def test_returns_both_stems(result):
    assert set(result) == {"vocals", "no_vocals"}


def test_stems_are_stereo_at_model_sample_rate(result):
    import separation

    for data in result.values():
        tensor, rate = decode(data)
        assert tensor.shape[0] == 2
        assert rate == separation.separator.samplerate


def test_stems_match_input_duration(result):
    for data in result.values():
        tensor, rate = decode(data)
        assert tensor.shape[1] / rate == pytest.approx(SECONDS, abs=0.05)


def test_stems_are_not_silent_and_within_range(result):
    for data in result.values():
        tensor, _ = decode(data)
        assert tensor.abs().max() > 0.001
        assert tensor.abs().max() <= 1.0


def test_stems_together_roughly_reconstruct_the_mix(result):
    mix, _ = decode(synthetic_mix())
    vocals, _ = decode(result["vocals"])
    no_vocals, _ = decode(result["no_vocals"])

    n = min(mix.shape[1], vocals.shape[1])
    recon = vocals[:, :n] + no_vocals[:, :n]
    err = (recon - mix[:, :n]).pow(2).mean().sqrt()
    ref = mix[:, :n].pow(2).mean().sqrt()

    assert err / ref < 0.5
