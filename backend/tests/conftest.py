import pytest
from unittest.mock import AsyncMock, patch
from starlette.testclient import TestClient


@pytest.fixture
def photos_dir(tmp_path):
    return tmp_path


@pytest.fixture
def client(photos_dir):
    with (
        patch("app.main.init_collection", new_callable=AsyncMock),
        patch("app.routers.caption.caption_image", new_callable=AsyncMock, return_value="a cat on a mat"),
        patch("app.routers.photos.encode_image", new_callable=AsyncMock, return_value=[0.0] * 512),
        patch("app.routers.photos.encode_text", new_callable=AsyncMock, return_value=[0.0] * 512),
        patch("app.routers.photos.upsert_photo", new_callable=AsyncMock),
        patch("app.routers.photos.search_photos", new_callable=AsyncMock, return_value=[]),
        patch("app.routers.photos.PHOTOS_DIR", photos_dir),
    ):
        from app.main import app
        with TestClient(app) as c:
            yield c
