import io
import sys
import wave
from unittest.mock import MagicMock, patch

import pytest
import torch

RATE_IN = 44100
RATE_OUT = 44100


@pytest.fixture
def separation():
    """Import separation with Demucs' Separator faked, so no model is loaded."""
    sys.modules.pop("separation", None)
    with patch("demucs.api.Separator") as fake_cls:
        fake_cls.return_value = MagicMock(samplerate=RATE_OUT)
        import separation as module

        yield module
    sys.modules.pop("separation", None)


def make_wav(samples: list[list[int]], rate: int = RATE_IN) -> bytes:
    """samples: one list of int16 values per channel."""
    channels = len(samples)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        interleaved = [s for frame in zip(*samples) for s in frame]
        wf.writeframes(torch.tensor(interleaved, dtype=torch.int16).numpy().tobytes())
    return buf.getvalue()


def test_wav_bytes_to_tensor_returns_channels_by_samples_and_rate(separation):
    wav = make_wav([[0, 16384, -16384], [0, 0, 0]])

    tensor, rate = separation._wav_bytes_to_tensor(wav)

    assert rate == RATE_IN
    assert tensor.shape == (2, 3)
    assert tensor.dtype == torch.float32
    assert tensor[0].tolist() == pytest.approx([0.0, 0.5, -0.5])


def test_tensor_to_wav_bytes_round_trips(separation):
    original = torch.tensor([[0.0, 0.5, -0.5], [0.25, 0.0, -0.25]])

    wav = separation._tensor_to_wav_bytes(original, RATE_IN)
    tensor, rate = separation._wav_bytes_to_tensor(wav)

    assert rate == RATE_IN
    assert tensor.shape == original.shape
    assert torch.allclose(tensor, original, atol=1e-3)


def test_tensor_to_wav_bytes_clamps_samples_beyond_full_scale(separation):
    loud = torch.tensor([[2.0, -2.0]])

    tensor, _ = separation._wav_bytes_to_tensor(
        separation._tensor_to_wav_bytes(loud, RATE_IN)
    )

    assert tensor[0, 0] == pytest.approx(1.0, abs=1e-3)
    assert tensor[0, 1] == pytest.approx(-1.0, abs=1e-3)


def test_sum_non_vocals_adds_all_stems(separation):
    vocals = torch.zeros(2, 4)
    stems = {
        "drums": torch.full((2, 4), 0.1),
        "bass": torch.full((2, 4), 0.2),
        "other": torch.full((2, 4), 0.3),
    }

    result = separation._sum_non_vocals(stems, vocals)

    assert torch.allclose(result, torch.full((2, 4), 0.6))


def test_sum_non_vocals_does_not_mutate_input_stems(separation):
    vocals = torch.zeros(1, 3)
    stems = {"drums": torch.full((1, 3), 0.1), "bass": torch.full((1, 3), 0.2)}

    separation._sum_non_vocals(stems, vocals)

    assert torch.allclose(stems["drums"], torch.full((1, 3), 0.1))


def test_separate_returns_vocals_and_summed_no_vocals(separation):
    stems = {
        "vocals": torch.full((2, 3), 0.5),
        "drums": torch.full((2, 3), 0.1),
        "bass": torch.full((2, 3), 0.1),
        "other": torch.full((2, 3), 0.2),
    }
    separation.separator.separate_tensor.return_value = (torch.zeros(2, 3), stems)
    wav = make_wav([[0, 0, 0], [0, 0, 0]])

    out = separation.separate(wav)

    assert set(out) == {"vocals", "no_vocals"}
    vocals, rate = separation._wav_bytes_to_tensor(out["vocals"])
    no_vocals, _ = separation._wav_bytes_to_tensor(out["no_vocals"])
    assert rate == RATE_OUT
    assert torch.allclose(vocals, torch.full((2, 3), 0.5), atol=1e-3)
    assert torch.allclose(no_vocals, torch.full((2, 3), 0.4), atol=1e-3)


def test_separate_passes_decoded_audio_to_model(separation):
    stems = {"vocals": torch.zeros(1, 2), "drums": torch.zeros(1, 2)}
    separation.separator.separate_tensor.return_value = (torch.zeros(1, 2), stems)

    separation.separate(make_wav([[16384, 0]]))

    wav_arg, rate_arg = separation.separator.separate_tensor.call_args.args
    assert rate_arg == RATE_IN
    assert wav_arg.shape == (1, 2)
