import base64
import json
import re
from pathlib import Path

import pytest
from startup import (
    ID_LENGTH,
    MANIFEST_PATH,
    extension_id_from_manifest,
    refuse_elevated,
)

REPO = Path(__file__).parents[1]
# A made-up key and its ID under Chrome's derivation (SHA-256, hex mapped to a-p).
FAKE_KEY = base64.b64encode(b"devoice test public key").decode()
FAKE_KEY_ID = "pcamamjgakmogljlhfkddmgppdcpffdf"
ID_PATTERN = re.compile(f"[a-p]{{{ID_LENGTH}}}")


def write_manifest(tmp_path, text):
    path = tmp_path / "manifest.json"
    path.write_bytes(text if isinstance(text, bytes) else text.encode())
    return path


def test_id_is_derived_from_the_manifest_key(tmp_path):
    path = write_manifest(tmp_path, json.dumps({"key": FAKE_KEY}))
    assert extension_id_from_manifest(path) == FAKE_KEY_ID


def test_repo_manifest_yields_a_chrome_extension_id():
    assert ID_PATTERN.fullmatch(extension_id_from_manifest(MANIFEST_PATH))


def test_missing_manifest_names_the_path(tmp_path):
    path = tmp_path / "nope.json"
    with pytest.raises(RuntimeError, match=re.escape(str(path))):
        extension_id_from_manifest(path)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        pytest.param("{not json", "not valid JSON", id="invalid-json"),
        pytest.param(json.dumps({"name": "DeVoice"}), 'no "key"', id="no-key"),
        pytest.param(json.dumps(["key"]), 'no "key"', id="not-an-object"),
        pytest.param(json.dumps({"key": 5}), "not valid base64", id="key-not-a-string"),
        pytest.param(b"\xff\xfe", "not valid JSON", id="not-utf8"),
        pytest.param(
            json.dumps({"key": "not base64!"}), "not valid base64", id="bad-b64"
        ),
        pytest.param(json.dumps({"key": ""}), "empty", id="empty-key"),
    ],
)
def test_unusable_manifest_is_a_clear_startup_error(tmp_path, text, message):
    with pytest.raises(RuntimeError, match=message):
        extension_id_from_manifest(write_manifest(tmp_path, text))


def test_unreadable_manifest_is_a_clear_startup_error(tmp_path):
    with pytest.raises(RuntimeError, match="cannot read"):
        extension_id_from_manifest(tmp_path)


def test_elevated_user_is_refused():
    with pytest.raises(SystemExit, match="root/Administrator"):
        refuse_elevated(is_admin=lambda: True)


def test_normal_user_is_allowed():
    refuse_elevated(is_admin=lambda: False)


@pytest.mark.parametrize("doc", ["backend/main.py", "README.md", "backend/AGENTS.md"])
def test_extension_id_env_var_is_gone(doc):
    assert "EXTENSION_ID" not in (REPO / doc).read_text()
