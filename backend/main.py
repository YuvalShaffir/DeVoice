from os import getenv
from pathlib import Path

from auth import load_token
from separation import separate
from server import create_app

HERE = Path(__file__).parent
ID = getenv("EXTENSION_ID")
EXTENSION_ORIGIN = f"chrome-extension://{ID}"

app = create_app(
    token=load_token(HERE / ".auth_token"),
    separate=separate,
    cache_dir=HERE / "cache",
    extension_origin=EXTENSION_ORIGIN,
)
