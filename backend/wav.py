import io
import struct
import wave

# Matches the extension's CHUNK_SECONDS: a full chunk is the longest upload.
MAX_SECONDS = 6
MIN_RATE = 8000
MAX_RATE = 48000
MAX_CHANNELS = 2
SAMPLE_WIDTH = 2

# Everything `wave` raises on malformed input. RuntimeError comes from a chunk
# that claims more bytes than its RIFF parent holds.
_PARSE_ERRORS = (wave.Error, EOFError, struct.error, ValueError, RuntimeError)


class InvalidWav(ValueError):
    pass


def validate_wav(data: bytes) -> None:
    try:
        # `wave` only reads PCM (plain or extensible). The read is bounded by
        # the body, which the request guard caps, whatever the header claims.
        with wave.open(io.BytesIO(data), "rb") as wav:
            frames = wav.readframes(wav.getnframes())
    except _PARSE_ERRORS as exc:
        raise InvalidWav() from exc
    expected_bytes = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
    if not _supported(wav) or len(frames) != expected_bytes:
        raise InvalidWav()


def _supported(wav: wave.Wave_read) -> bool:
    return (
        wav.getsampwidth() == SAMPLE_WIDTH
        and 1 <= wav.getnchannels() <= MAX_CHANNELS
        and MIN_RATE <= wav.getframerate() <= MAX_RATE
        and 0 < wav.getnframes() <= MAX_SECONDS * wav.getframerate()
    )
