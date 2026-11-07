import random
import struct
import tracemalloc

import pytest
from api import INVALID_AUDIO
from api_client import auth_headers, upload
from guard import MAX_BODY
from wav import (
    MAX_CHANNELS,
    MAX_RATE,
    MAX_SECONDS,
    MIN_RATE,
    SAMPLE_WIDTH,
    InvalidWav,
    validate_wav,
)
from wav_factory import (
    EXTENSIBLE,
    FLOAT_SUBFORMAT,
    HEADER_OFFSETS,
    IEEE_FLOAT,
    chunk,
    make_wav,
)

MAX_FRAMES = MAX_SECONDS * MAX_RATE
CD_RATE = 44100
ABOVE_MAX_RATE = 2 * MAX_RATE
UINT16_MAX = 0xFFFF
UINT32_MAX = 0xFFFFFFFF
FUZZ_SEED = 14
FUZZ_ROUNDS = 2000
MAX_RANDOM_TAIL = 512
# Small mono base keeps the fuzz fast; it has the 44-byte layout HEADER_OFFSETS maps.
FUZZ_BASE = make_wav(channels=1, rate=MIN_RATE, frames=64)
HEADER_OVERRIDES = [
    ("<H", "format_tag", IEEE_FLOAT),
    ("<H", "format_tag", EXTENSIBLE),
    ("<H", "format_tag", 0),
    ("<H", "channels", 0),
    ("<H", "channels", MAX_CHANNELS + 1),
    ("<H", "channels", UINT16_MAX),
    ("<I", "rate", 0),
    ("<I", "rate", ABOVE_MAX_RATE),
    ("<I", "rate", UINT32_MAX),
    ("<H", "bits", 0),
    ("<H", "bits", 8),
    ("<H", "bits", 24),
    ("<H", "bits", 32),
    ("<I", "data_size", UINT32_MAX),
    ("<I", "riff_size", 0),
    ("<I", "fmt_size", UINT32_MAX),
]


def assert_only_invalid_wav_raised(data):
    try:
        validate_wav(data)
    except InvalidWav:
        pass


@pytest.mark.parametrize(
    "wav",
    [
        pytest.param(make_wav(channels=2, frames=MAX_FRAMES), id="stereo-48k-6s"),
        pytest.param(make_wav(channels=1, rate=CD_RATE), id="mono-44.1k-1s"),
        pytest.param(make_wav(rate=MIN_RATE), id="lowest-rate"),
        pytest.param(make_wav(format_tag=EXTENSIBLE), id="extensible-pcm"),
    ],
)
def test_short_16_bit_pcm_wav_is_valid(wav):
    validate_wav(wav)


@pytest.mark.parametrize(
    "wav",
    [
        pytest.param(make_wav(width=SAMPLE_WIDTH - 1), id="8-bit"),
        pytest.param(make_wav(width=SAMPLE_WIDTH + 1), id="24-bit"),
        pytest.param(make_wav(channels=MAX_CHANNELS + 1), id="3-channels"),
        pytest.param(make_wav(rate=ABOVE_MAX_RATE), id="96k"),
        pytest.param(make_wav(rate=0, frames=1), id="rate-0"),
        pytest.param(make_wav(rate=MIN_RATE - 1), id="rate-below-min"),
        pytest.param(make_wav(frames=MAX_FRAMES + 1), id="6s-plus-1-frame"),
        pytest.param(make_wav(frames=0), id="0-frames"),
        pytest.param(b"not a wav at all", id="non-riff"),
        pytest.param(b"", id="empty"),
        pytest.param(make_wav(frames=100, declared_frames=110), id="data-short"),
        pytest.param(make_wav(format_tag=IEEE_FLOAT), id="float"),
        pytest.param(
            make_wav(format_tag=EXTENSIBLE, subformat=FLOAT_SUBFORMAT),
            id="extensible-float",
        ),
        pytest.param(
            chunk(b"RIFF", b"WAVE" + chunk(b"JUNK", b"", size=MAX_BODY)),
            id="chunk-larger-than-riff",
        ),
    ],
)
def test_unsupported_or_malformed_wav_is_invalid(wav):
    with pytest.raises(InvalidWav):
        validate_wav(wav)


def test_huge_declared_length_is_invalid_without_large_allocation():
    block = MAX_CHANNELS * SAMPLE_WIDTH
    wav = make_wav(
        channels=MAX_CHANNELS, frames=100, declared_frames=UINT32_MAX // block
    )
    tracemalloc.start()
    try:
        with pytest.raises(InvalidWav):
            validate_wav(wav)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < MAX_BODY


def test_invalid_upload_rejected_before_separation(client, separated):
    res = upload(client, auth_headers(), body=make_wav(width=SAMPLE_WIDTH - 1))
    assert res.status_code == 400
    assert res.json() == {"detail": INVALID_AUDIO}
    assert separated == []


def test_fuzz_bit_flips():
    rng = random.Random(FUZZ_SEED)
    for _ in range(FUZZ_ROUNDS):
        data = bytearray(FUZZ_BASE)
        for _ in range(rng.randint(1, 8)):
            data[rng.randrange(len(data))] ^= 1 << rng.randrange(8)
        assert_only_invalid_wav_raised(bytes(data))


def test_fuzz_truncation_at_every_offset():
    for length in range(len(FUZZ_BASE)):
        assert_only_invalid_wav_raised(FUZZ_BASE[:length])


@pytest.mark.parametrize(
    ("fmt", "field", "value"),
    HEADER_OVERRIDES,
    ids=[f"{field}={value}" for _, field, value in HEADER_OVERRIDES],
)
def test_fuzz_header_overrides(fmt, field, value):
    data = bytearray(FUZZ_BASE)
    struct.pack_into(fmt, data, HEADER_OFFSETS[field], value)
    assert_only_invalid_wav_raised(bytes(data))


def test_fuzz_random_bytes():
    rng = random.Random(FUZZ_SEED)
    for _ in range(FUZZ_ROUNDS):
        prefix = FUZZ_BASE[: rng.randrange(len(FUZZ_BASE))]
        assert_only_invalid_wav_raised(
            prefix + rng.randbytes(rng.randrange(MAX_RANDOM_TAIL))
        )
