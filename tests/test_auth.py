import hashlib

import pytest
from api import CONTENT_TYPE_HEADER, SEPARATE_PATH, TOKEN_HEADER
from api_client import ORIGIN, auth_headers, fetch_stem, upload
from auth import load_token
from stems import VOCALS

HASH = hashlib.sha256(b"cached").hexdigest()


def preflight(client, origin):
    return client.options(
        SEPARATE_PATH,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            # What the extension's raw WAV upload makes the browser ask for.
            "Access-Control-Request-Headers": f"{TOKEN_HEADER}, {CONTENT_TYPE_HEADER}",
        },
    )


def test_separate_without_token_rejected(client):
    assert upload(client).status_code == 403


def test_separate_with_wrong_token_rejected(client):
    assert upload(client, {TOKEN_HEADER: "nope"}).status_code == 403


def test_separate_with_correct_token_accepted(client):
    res = upload(client, auth_headers())
    assert res.status_code == 200
    assert set(res.json()) == {"id", "stems"}


def test_stem_with_correct_token_accepted(client):
    id_ = upload(client, auth_headers()).json()["id"]
    res = fetch_stem(client, id_, VOCALS, auth_headers())
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/wav"
    assert res.content == b"v"


def test_stem_without_token_rejected(client):
    id_ = upload(client, auth_headers()).json()["id"]
    assert fetch_stem(client, id_, VOCALS).status_code == 403


def test_stem_served_once_then_gone(client):
    id_ = upload(client, auth_headers()).json()["id"]
    assert fetch_stem(client, id_, VOCALS, auth_headers()).status_code == 200
    assert fetch_stem(client, id_, VOCALS, auth_headers()).status_code == 404


def test_unknown_stem_returns_404(client):
    assert fetch_stem(client, HASH, "drums", auth_headers()).status_code == 404


def test_unknown_hash_returns_404(client):
    assert fetch_stem(client, HASH, VOCALS, auth_headers()).status_code == 404


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
