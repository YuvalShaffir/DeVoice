from pathlib import Path

from api import extension_origin
from auth import load_token
from server import create_app
from startup import MANIFEST_PATH, extension_id_from_manifest, refuse_elevated

refuse_elevated()

# Imported after the privilege check: it loads the Demucs model.
from separation import separate

HERE = Path(__file__).parent

app = create_app(
    token=load_token(HERE / ".auth_token"),
    separate=separate,
    extension_origin=extension_origin(extension_id_from_manifest(MANIFEST_PATH)),
)
