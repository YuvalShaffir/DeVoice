import logging
import os
import secrets
from pathlib import Path

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
