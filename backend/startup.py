import base64
import binascii
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path

MANIFEST_PATH = Path(__file__).parents[1] / "extension" / "manifest.json"
ID_LENGTH = 32
# Chrome writes the ID's hex digits 0-f as the letters a-p.
ID_FIRST_LETTER = "a"
HEX_BASE = 16


def extension_id_from_manifest(path: Path) -> str:
    """The extension ID Chrome derives from the manifest's pinned public `key`."""
    digest = hashlib.sha256(_public_key(path)).hexdigest()[:ID_LENGTH]
    return "".join(chr(ord(ID_FIRST_LETTER) + int(c, HEX_BASE)) for c in digest)


def _public_key(path: Path) -> bytes:
    key = _read_manifest(path).get("key")
    if key is None:
        raise RuntimeError(f'{path} has no "key" to derive the extension ID')
    try:
        der = base64.b64decode(key, validate=True)
    except (binascii.Error, TypeError):
        raise RuntimeError(f'{path} "key" is not valid base64') from None
    if not der:
        raise RuntimeError(f'{path} "key" is empty')
    return der


def _read_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_text())
    except FileNotFoundError:
        raise RuntimeError(f"extension manifest not found at {path}") from None
    except OSError as exc:
        raise RuntimeError(f"cannot read {path}: {exc.strerror}") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise RuntimeError(f"{path} is not valid JSON") from None
    return manifest if isinstance(manifest, dict) else {}


def _is_admin() -> bool:
    if hasattr(os, "geteuid"):
        return os.geteuid() == 0
    import ctypes  # Windows only: no euid there.

    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def refuse_elevated(is_admin: Callable[[], bool] = _is_admin) -> None:
    if is_admin():
        raise SystemExit(
            "Refusing to run as root/Administrator: start the backend as a normal user."
        )
