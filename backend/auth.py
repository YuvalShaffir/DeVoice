import logging
import os
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import Header, HTTPException

logger = logging.getLogger()


def load_token(path: Path) -> str:
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(16))
        logger.info(
            f"Generated new auth token at {path} - paste it into the extension's options page."
        )
    token = path.read_text().strip()
    if not token:
        raise RuntimeError(f"{path} is empty, delete it to generate a new token")
    return token


def make_require_token(token: str) -> Callable[[str], None]:
    expected = token.encode()

    def require_token(x_auth_token: Annotated[str, Header()] = "") -> None:
        if not secrets.compare_digest(x_auth_token.encode(), expected):
            raise HTTPException(403, "invalid or missing token")

    return require_token
