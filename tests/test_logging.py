import logging

import pytest
from api import TOKEN_HEADER
from api_client import BASE_URL, TOKEN, VALID_WAV, auth_headers, fetch_stem, upload
from fastapi.testclient import TestClient
from guard import MAX_BODY
from stems import STEMS
from wav import SAMPLE_WIDTH
from wav_factory import make_wav

WRONG_TOKEN = "wrong-token-value"
WAV_MAGIC = "RIFF"
SERVER_ERROR_BODY = "Internal Server Error"


def crash(data):
    raise RuntimeError("model crashed")


@pytest.fixture
def logs(caplog):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="uvicorn")
    return caplog


@pytest.fixture
def crashing_client(make_app):
    return TestClient(
        make_app(separate=crash), base_url=BASE_URL, raise_server_exceptions=False
    )


def test_logs_hold_no_token_headers_or_audio(client, crashing_client, logs):
    content_hash = upload(client, auth_headers()).json()["id"]
    for stem in STEMS:
        assert fetch_stem(client, content_hash, stem, auth_headers()).status_code == 200
    responses = [
        upload(client, auth_headers(), body=make_wav(width=SAMPLE_WIDTH - 1)),
        upload(client, {TOKEN_HEADER: WRONG_TOKEN}),
        upload(client, auth_headers(), body=b"\0" * (MAX_BODY + 1)),
        upload(crashing_client, auth_headers()),
    ]
    assert [res.status_code for res in responses] == [400, 403, 413, 500]

    for secret in (TOKEN, WRONG_TOKEN, WAV_MAGIC, repr(VALID_WAV[:16])):
        assert secret not in logs.text


def test_server_error_body_is_generic(crashing_client):
    res = upload(crashing_client, auth_headers())
    assert res.status_code == 500
    assert res.text == SERVER_ERROR_BODY
    assert "Traceback" not in res.text
