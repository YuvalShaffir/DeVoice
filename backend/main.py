from os import getenv
from pathlib import Path

from api import extension_origin
from auth import load_token
from separation import separate
from server import create_app

HERE = Path(__file__).parent
ID = getenv("EXTENSION_ID")
EXTENSION_ORIGIN = extension_origin(ID)

app = create_app(
    token=load_token(HERE / ".auth_token"),
    separate=separate,
    extension_origin=EXTENSION_ORIGIN,
)
