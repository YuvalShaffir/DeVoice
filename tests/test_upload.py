import builtins
import io
import sys
import tempfile

import pytest
from api import CONTENT_TYPE_HEADER, SEPARATE_PATH, WAV_MEDIA_TYPE
from api_client import auth_headers, fetch_stem, upload
from stems import STEMS

TEMPFILE_FACTORIES = (
    "SpooledTemporaryFile",
    "TemporaryFile",
    "NamedTemporaryFile",
    "mkstemp",
    "mkdtemp",
)
# Characters in an `open()` mode that create or modify a file.
WRITE_MODE_FLAGS = "wax+"
# Above Starlette's 1 MB spool-to-disk threshold for multipart uploads.
SPOOL_SIZED_BODY = b"\0" * 1_500_000


@pytest.fixture
def disk_write_traps(monkeypatch):
    """Make temp files and write-mode `open` raise; yields the list of fired traps."""
    fired = []

    def trap(name):
        def raise_on_call(*args, **kwargs):
            fired.append(name)
            raise AssertionError(f"disk write via {name}")

        return raise_on_call

    for name in TEMPFILE_FACTORIES:
        original = getattr(tempfile, name)
        # Also patch modules that did `from tempfile import ...` before the test.
        for module in list(sys.modules.values()):
            if getattr(module, "__dict__", {}).get(name) is original:
                monkeypatch.setattr(module, name, trap(name))

    real_open = builtins.open

    def read_only_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in WRITE_MODE_FLAGS):
            fired.append(f"open({file!r}, {mode!r})")
            raise AssertionError(f"disk write via open({file!r}, {mode!r})")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", read_only_open)
    monkeypatch.setattr(io, "open", read_only_open)
    return fired


def test_raw_wav_upload_accepted(client):
    res = upload(client, auth_headers())
    assert res.status_code == 200
    assert set(res.json()) == {"id", "stems"}


@pytest.mark.parametrize(
    "content_type", [f"{WAV_MEDIA_TYPE}; codecs=1", WAV_MEDIA_TYPE.upper()]
)
def test_wav_with_parameters_or_other_case_accepted(client, content_type):
    headers = auth_headers({CONTENT_TYPE_HEADER: content_type})
    assert upload(client, headers).status_code == 200


@pytest.mark.parametrize(
    "content_type", ["audio/x-wav", "application/octet-stream", "text/plain"]
)
def test_other_content_type_rejected(client, content_type):
    headers = auth_headers({CONTENT_TYPE_HEADER: content_type})
    assert upload(client, headers).status_code == 415


def test_multipart_upload_rejected(client, separated):
    res = client.post(
        SEPARATE_PATH, files={"file": ("c.wav", b"fake-wav")}, headers=auth_headers()
    )
    assert res.status_code == 415
    assert separated == []


def test_upload_without_content_type_rejected(client):
    res = client.post(SEPARATE_PATH, content=b"fake-wav", headers=auth_headers())
    assert res.status_code == 415


def test_round_trip_never_writes_to_disk(client, disk_write_traps):
    res = upload(client, auth_headers(), body=SPOOL_SIZED_BODY)
    assert res.status_code == 200
    content_hash = res.json()["id"]
    for stem in STEMS:
        assert fetch_stem(client, content_hash, stem, auth_headers()).status_code == 200
    assert disk_write_traps == []


def test_disk_write_traps_catch_open_and_tempfiles(tmp_path, disk_write_traps):
    with pytest.raises(AssertionError), open(tmp_path / "x", "w"):
        pass
    with pytest.raises(AssertionError):
        (tmp_path / "y").write_bytes(b"")
    with pytest.raises(AssertionError), tempfile.SpooledTemporaryFile():
        pass
    assert len(disk_write_traps) == 3
