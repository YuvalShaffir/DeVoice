import secrets

from api import SEPARATE_PATH, STEM_PATH, TOKEN_HEADER, extension_origin
from guard import LOOPBACK_HOST

TOKEN = "test-token"
ORIGIN = extension_origin(secrets.token_hex(16))
BASE_URL = f"http://{LOOPBACK_HOST}"


def auth_headers(extra=None):
    return {TOKEN_HEADER: TOKEN, **(extra or {})}


def upload(client, headers=None):
    return client.post(
        SEPARATE_PATH, files={"file": ("c.wav", b"fake-wav")}, headers=headers or {}
    )


def fetch_stem(client, content_hash, stem, headers=None):
    path = STEM_PATH.format(content_hash=content_hash, stem=stem)
    return client.get(path, headers=headers or {})
