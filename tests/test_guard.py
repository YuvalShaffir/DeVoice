import asyncio

import pytest
from api import CONTENT_TYPE_HEADER, SEPARATE_PATH, TOKEN_HEADER, WAV_MEDIA_TYPE
from api_client import ORIGIN, TOKEN, auth_headers, upload
from guard import LOOPBACK_HOST, MAX_BODY

LOOPBACK_WITH_PORT = f"{LOOPBACK_HOST}:8000"
CHUNK = 64 * 1024


def chunked(size):
    body = b"\0" * size
    return [body[i : i + CHUNK] for i in range(0, size, CHUNK)]


def loopback_auth(extra=None):
    return auth_headers(
        {
            "Host": LOOPBACK_WITH_PORT,
            CONTENT_TYPE_HEADER: WAV_MEDIA_TYPE,
            **(extra or {}),
        }
    )


def call_asgi(app, headers, chunks=()):
    """POST to /separate as raw ASGI; return (status, number of receive calls)."""
    pending = list(chunks) or [b""]
    receive_calls = 0
    sent = []

    async def receive():
        nonlocal receive_calls
        receive_calls += 1
        if pending:
            body = pending.pop(0)
            return {"type": "http.request", "body": body, "more_body": bool(pending)}
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": SEPARATE_PATH,
        "raw_path": SEPARATE_PATH.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (LOOPBACK_HOST, 50000),
        "server": (LOOPBACK_HOST, 8000),
    }
    asyncio.run(app(scope, receive, send))
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    return status, receive_calls


def test_foreign_host_rejected(client):
    assert upload(client, auth_headers({"Host": "evil.com:8000"})).status_code == 400


def test_loopback_host_with_port_accepted(client):
    res = upload(client, auth_headers({"Host": LOOPBACK_WITH_PORT}))
    assert res.status_code == 200


@pytest.mark.parametrize("host", ["localhost", "[::1]", "127.0.0.1.evil.com"])
def test_other_loopback_names_and_lookalikes_rejected(client, host):
    assert upload(client, auth_headers({"Host": host})).status_code == 400


def test_missing_host_rejected(app):
    assert call_asgi(app, auth_headers({"Content-Length": "0"}))[0] == 400


@pytest.mark.parametrize("token", ["", TOKEN[:-1] + "X", "nope"])
def test_empty_or_wrong_token_of_any_length_rejected(client, token):
    assert upload(client, {TOKEN_HEADER: token}).status_code == 403


def test_upload_without_content_length_rejected(app):
    assert call_asgi(app, loopback_auth(), chunked(1000))[0] == 411


@pytest.mark.parametrize("length", ["abc", "-1"])
def test_invalid_content_length_rejected(app, length):
    assert call_asgi(app, loopback_auth({"Content-Length": length}))[0] == 400


def test_declared_length_over_limit_rejected(app):
    headers = loopback_auth({"Content-Length": str(MAX_BODY + 1)})
    assert call_asgi(app, headers)[0] == 413


def test_body_exactly_at_limit_accepted(app, separated):
    headers = loopback_auth({"Content-Length": str(MAX_BODY)})
    status, _ = call_asgi(app, headers, chunked(MAX_BODY))
    assert status == 200
    assert len(separated) == 1


def test_body_streamed_past_limit_rejected(app, separated):
    headers = loopback_auth({"Content-Length": "100"})
    status, _ = call_asgi(app, headers, chunked(MAX_BODY + CHUNK))
    assert status == 413
    assert separated == []


@pytest.mark.parametrize(
    ("headers", "expected_status"),
    [
        pytest.param({"Host": "evil.com", "Content-Length": "8"}, 400, id="bad-host"),
        pytest.param(
            {"Host": LOOPBACK_HOST, "Content-Length": "8"}, 403, id="no-token"
        ),
        pytest.param(loopback_auth(), 411, id="no-length"),
        pytest.param(
            loopback_auth({"Content-Length": str(MAX_BODY + 1)}), 413, id="too-long"
        ),
    ],
)
def test_rejected_request_body_never_read(app, headers, expected_status):
    status, receive_calls = call_asgi(app, headers, [b"fake-wav"])
    assert status == expected_status
    assert receive_calls == 0


def test_guard_error_carries_cors_header_for_extension(client):
    res = upload(client, {"Origin": ORIGIN})
    assert res.status_code == 403
    assert res.headers["access-control-allow-origin"] == ORIGIN


def test_plain_options_does_not_reach_separate(client, separated):
    res = client.options(SEPARATE_PATH)
    assert res.status_code == 405
    assert separated == []
