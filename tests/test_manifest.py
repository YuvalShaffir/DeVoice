import json
from pathlib import Path

EXTENSION_DIR = Path(__file__).parent.parent / "extension"


def load_manifest():
    return json.loads((EXTENSION_DIR / "manifest.json").read_text())


def test_manifest_is_mv3():
    manifest = load_manifest()
    assert manifest["manifest_version"] == 3


def test_required_permissions_present():
    manifest = load_manifest()
    for permission in ("tabCapture", "offscreen"):
        assert permission in manifest["permissions"]


def test_background_service_worker_file_exists():
    manifest = load_manifest()
    worker = manifest["background"]["service_worker"]
    assert (EXTENSION_DIR / worker).is_file()


def test_offscreen_document_and_its_script_exist():
    offscreen_html = EXTENSION_DIR / "offscreen.html"
    assert offscreen_html.is_file()

    referenced_scripts = [
        line.split('src="')[1].split('"')[0]
        for line in offscreen_html.read_text().splitlines()
        if 'src="' in line
    ]
    for script in referenced_scripts:
        assert (EXTENSION_DIR / script).is_file()
