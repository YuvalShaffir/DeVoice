import pytest
from api_client import BASE_URL, ORIGIN, TOKEN
from fastapi.testclient import TestClient
from server import create_app
from stems import NO_VOCALS, VOCALS


@pytest.fixture
def separated():
    """Uploads that reached `separate`."""
    return []


@pytest.fixture
def make_app(separated):
    """Builds the app; keyword arguments override `separate` and the limits."""

    def fake_separate(data: bytes) -> dict[str, bytes]:
        separated.append(data)
        return {VOCALS: b"v", NO_VOCALS: b"n"}

    def build(separate=fake_separate, **limits):
        return create_app(
            token=TOKEN, separate=separate, extension_origin=ORIGIN, **limits
        )

    return build


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def client(app):
    return TestClient(app, base_url=BASE_URL)
