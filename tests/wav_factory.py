"""Builds WAV bytes field by field, including headers `wave` refuses to write."""

import struct
import uuid

from wav import MAX_CHANNELS, MAX_RATE, SAMPLE_WIDTH

PCM = 0x0001
IEEE_FLOAT = 0x0003
EXTENSIBLE = 0xFFFE
PCM_SUBFORMAT = uuid.UUID("00000001-0000-0010-8000-00aa00389b71").bytes_le
FLOAT_SUBFORMAT = uuid.UUID("00000003-0000-0010-8000-00aa00389b71").bytes_le
EXTENSION_SIZE = 22
BITS_PER_BYTE = 8
CHUNK_NAME_SIZE = 4
CHUNK_SIZE_FIELD = struct.Struct("<I")
CHUNK_HEADER_SIZE = CHUNK_NAME_SIZE + CHUNK_SIZE_FIELD.size
# Byte offsets of header fields in a plain PCM `make_wav()` (the 44-byte layout).
HEADER_OFFSETS = {
    "riff_size": 4,
    "fmt_size": 16,
    "format_tag": 20,
    "channels": 22,
    "rate": 24,
    "bits": 34,
    "data_size": 40,
}


def chunk(name, payload, size=None):
    return (
        name + CHUNK_SIZE_FIELD.pack(len(payload) if size is None else size) + payload
    )


def make_wav(
    channels=MAX_CHANNELS,
    rate=MAX_RATE,
    width=SAMPLE_WIDTH,
    frames=None,
    format_tag=PCM,
    subformat=PCM_SUBFORMAT,
    declared_frames=None,
    junk_size=0,
):
    """Silent WAV, 1 s unless `frames` is given; the other arguments bend the header."""
    frames = rate if frames is None else frames
    declared_frames = frames if declared_frames is None else declared_frames
    block = channels * width
    bits = width * BITS_PER_BYTE
    fmt = struct.pack("<HHIIHH", format_tag, channels, rate, rate * block, block, bits)
    if format_tag == EXTENSIBLE:
        fmt += struct.pack("<HHI", EXTENSION_SIZE, bits, 0) + subformat
    chunks = chunk(b"fmt ", fmt)
    if junk_size:
        chunks += chunk(b"JUNK", b"\0" * junk_size)
    chunks += chunk(b"data", b"\0" * (frames * block), size=declared_frames * block)
    return chunk(b"RIFF", b"WAVE" + chunks)
