import json
import re
from pathlib import Path

EXTENSION_DIR = Path(__file__).parent.parent / "extension"


def read(name):
    return (EXTENSION_DIR / name).read_text()


def worklet_module_path():
    match = re.search(r'audioWorklet\.addModule\("([^"]+)"\)', read("offscreen.js"))
    assert match, "offscreen.js must load a worklet module via audioWorklet.addModule"
    return match.group(1)


def test_tabs_permission_present_for_audible_check():
    manifest = json.loads((EXTENSION_DIR / "manifest.json").read_text())
    assert "tabs" in manifest["permissions"]


def test_background_checks_audible_before_creating_offscreen_document():
    background = read("background.js")
    assert "chrome.tabs.get" in background
    assert ".audible" in background

    audible_check_pos = background.index(".audible")
    offscreen_doc_pos = background.index("createDocument")
    assert audible_check_pos < offscreen_doc_pos, (
        "audible check must happen before the offscreen document is created, "
        "otherwise capture isn't actually skipped"
    )


def test_worklet_module_referenced_by_offscreen_exists():
    assert (EXTENSION_DIR / worklet_module_path()).is_file()


def test_worklet_processor_name_matches_registration():
    offscreen = read("offscreen.js")
    processor_source = read(worklet_module_path())

    node_name = re.search(
        r'new AudioWorkletNode\(\s*captureCtx,\s*"([^"]+)"', offscreen
    )
    registered_name = re.search(r'registerProcessor\("([^"]+)"', processor_source)

    assert node_name and registered_name
    assert node_name.group(1) == registered_name.group(1)


def test_capture_graph_routes_through_silent_sink_to_destination():
    offscreen = read("offscreen.js")
    assert "createGain()" in offscreen
    assert re.search(r"silentSink\.gain\.value\s*=\s*0", offscreen)
    assert "silentSink.connect(captureCtx.destination)" in offscreen


def test_capture_processor_skips_silent_chunks_before_posting():
    processor_source = read(worklet_module_path())

    silence_check_pos = processor_source.index("isSilent(left)")
    post_message_pos = processor_source.index("this.port.postMessage")
    assert silence_check_pos < post_message_pos, (
        "silence check must run before postMessage, otherwise silent chunks "
        "still get sent and downloaded"
    )


def test_silence_threshold_is_a_small_positive_number():
    processor_source = read(worklet_module_path())
    match = re.search(r"SILENCE_THRESHOLD\s*=\s*([\d.eE+-]+)", processor_source)
    assert match, "expected a named SILENCE_THRESHOLD constant"

    threshold = float(match.group(1))
    assert 0 < threshold < 0.01
