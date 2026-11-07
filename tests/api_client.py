import secrets

from api import (
    CONTENT_TYPE_HEADER,
    SEPARATE_PATH,
    STEM_PATH,
    TOKEN_HEADER,
    WAV_MEDIA_TYPE,
    extension_origin,
)
from guard import LOOPBACK_HOST
from wav_factory import make_wav

TOKEN = "test-token"
ORIGIN = extension_origin(secrets.token_hex(16))
BASE_URL = f"http://{LOOPBACK_HOST}"
VALID_WAV = make_wav()


def auth_headers(extra=None):
    return {TOKEN_HEADER: TOKEN, **(extra or {})}


def upload(client, headers=None, body=VALID_WAV):
    headers = {CONTENT_TYPE_HEADER: WAV_MEDIA_TYPE, **(headers or {})}
    return client.post(SEPARATE_PATH, content=body, headers=headers)


def fetch_stem(client, content_hash, stem, headers=None):
    path = STEM_PATH.format(content_hash=content_hash, stem=stem)
    return client.get(path, headers=headers or {})
