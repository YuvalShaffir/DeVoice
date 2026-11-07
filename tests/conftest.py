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
def app(separated):
    def fake_separate(data: bytes) -> dict[str, bytes]:
        separated.append(data)
        return {VOCALS: b"v", NO_VOCALS: b"n"}

    return create_app(token=TOKEN, separate=fake_separate, extension_origin=ORIGIN)


@pytest.fixture
def client(app):
    return TestClient(app, base_url=BASE_URL)
