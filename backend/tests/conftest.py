import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.responses import RedirectResponse
from starlette.testclient import TestClient

os.environ.setdefault("API_KEY", "test-api-key")


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from app.auth import limiter

    limiter._storage.reset()
    yield


@pytest.fixture
def client():
    with (
        patch("app.main.init_collection", new_callable=AsyncMock),
        patch(
            "app.routers.photos.caption_image",
            new_callable=AsyncMock,
            return_value="a cat on a mat",
        ),
        patch(
            "app.routers.photos.encode_image",
            new_callable=AsyncMock,
            return_value=[0.0] * 768,
        ),
        patch(
            "app.routers.photos.encode_text",
            new_callable=AsyncMock,
            return_value=[0.0] * 768,
        ),
        patch("app.routers.photos.upsert_photo", new_callable=AsyncMock),
        patch(
            "app.routers.photos.search_photos", new_callable=AsyncMock, return_value=[]
        ),
        patch(
            "app.routers.photos.search_photos_keyword",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch("app.routers.photos.update_caption_override", new_callable=AsyncMock),
        patch(
            "app.routers.photos.get_photo_record",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.routers.photos.photo_exists",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch("app.routers.photos.upload_photo", new_callable=AsyncMock),
        patch(
            "app.routers.photos.get_photo_response",
            new_callable=AsyncMock,
            return_value=RedirectResponse(
                "https://r2.example.com/photo", status_code=302
            ),
        ),
        patch("app.routers.photos.delete_photo_from_storage", new_callable=AsyncMock),
        patch("app.routers.photos.delete_photo", new_callable=AsyncMock),
        patch(
            "app.routers.photos.get_total_storage_bytes",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch(
            "app.routers.photos.list_photos",
            new_callable=AsyncMock,
            return_value=([], None),
        ),
    ):
        from app.main import app

        with TestClient(app) as c:
            c.headers.update({"X-API-Key": "test-api-key"})
            yield c
