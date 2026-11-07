import pytest
from api_client import BASE_URL, ORIGIN, TOKEN, fake_stems
from fastapi.testclient import TestClient
from server import create_app
from stems import Stems


@pytest.fixture
def separated():
    """Uploads that reached `separate`."""
    return []


@pytest.fixture
def make_app(separated):
    def fake_separate(data: bytes) -> Stems:
        separated.append(data)
        return fake_stems()

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
