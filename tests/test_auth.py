import hashlib

import pytest
from auth import load_token
from fastapi.testclient import TestClient
from server import create_app
from stems import NO_VOCALS, VOCALS

TOKEN = "test-token"
ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
HASH = hashlib.sha256(b"cached").hexdigest()


def fake_separate(data: bytes) -> dict[str, bytes]:
    return {VOCALS: b"v", NO_VOCALS: b"n"}


@pytest.fixture
def client():
    return TestClient(
        create_app(
            token=TOKEN,
            separate=fake_separate,
            extension_origin=ORIGIN,
        )
    )


def upload(client, headers=None):
    return client.post(
        "/separate", files={"file": ("c.wav", b"fake-wav")}, headers=headers or {}
    )


def preflight(client, origin):
    return client.options(
        "/separate",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-auth-token",
        },
    )


def test_separate_without_token_rejected(client):
    assert upload(client).status_code == 403


def test_separate_with_wrong_token_rejected(client):
    assert upload(client, {"X-Auth-Token": "nope"}).status_code == 403


def test_separate_with_correct_token_accepted(client):
    res = upload(client, {"X-Auth-Token": TOKEN})
    assert res.status_code == 200
    assert set(res.json()) == {"id", "stems"}


def test_stem_with_correct_token_accepted(client):
    id_ = upload(client, {"X-Auth-Token": TOKEN}).json()["id"]
    res = client.get(f"/stem/{id_}/vocals", headers={"X-Auth-Token": TOKEN})
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/wav"
    assert res.content == b"v"


def test_stem_without_token_rejected(client):
    id_ = upload(client, {"X-Auth-Token": TOKEN}).json()["id"]
    assert client.get(f"/stem/{id_}/vocals").status_code == 403


def test_stem_served_once_then_gone(client):
    headers = {"X-Auth-Token": TOKEN}
    id_ = upload(client, headers).json()["id"]
    assert client.get(f"/stem/{id_}/vocals", headers=headers).status_code == 200
    assert client.get(f"/stem/{id_}/vocals", headers=headers).status_code == 404


def test_unknown_stem_returns_404(client):
    res = client.get(f"/stem/{HASH}/drums", headers={"X-Auth-Token": TOKEN})
    assert res.status_code == 404


def test_unknown_hash_returns_404(client):
    res = client.get(f"/stem/{HASH}/vocals", headers={"X-Auth-Token": TOKEN})
    assert res.status_code == 404


def test_cors_preflight_allows_only_pinned_origin(client):
    res = preflight(client, ORIGIN)
    assert res.headers["access-control-allow-origin"] == ORIGIN


def test_cors_preflight_rejects_other_origin(client):
    res = preflight(client, "https://evil.example")
    assert "access-control-allow-origin" not in res.headers


def test_missing_token_file_is_generated_not_skipped(tmp_path):
    path = tmp_path / ".auth_token"
    assert load_token(path) == path.read_text().strip() != ""


def test_empty_token_file_refuses_to_start(tmp_path):
    path = tmp_path / ".auth_token"
    path.write_text("")
    with pytest.raises(RuntimeError):
        load_token(path)
