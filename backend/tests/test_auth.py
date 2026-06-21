import io
from unittest.mock import AsyncMock, patch

from PIL import Image


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(0, 128, 255)).save(buf, format="JPEG")
    return buf.getvalue()


def test_upload_without_api_key_is_rejected(client):
    response = client.post(
        "/api/photos/upload",
        files={"file": ("beach.jpg", _jpeg_bytes(), "image/jpeg")},
        headers={"X-API-Key": ""},
    )
    assert response.status_code == 401


def test_upload_with_wrong_api_key_is_rejected(client):
    response = client.post(
        "/api/photos/upload",
        files={"file": ("beach.jpg", _jpeg_bytes(), "image/jpeg")},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_upload_with_correct_api_key_succeeds(client):
    response = client.post(
        "/api/photos/upload",
        files={"file": ("beach.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 200


def test_delete_without_api_key_is_rejected(client):
    with patch(
        "app.routers.photos.object_exists_in_r2",
        new_callable=AsyncMock,
        return_value=True,
    ):
        response = client.delete("/api/photos/some-id", headers={"X-API-Key": ""})
    assert response.status_code == 401


def test_edit_caption_without_api_key_is_rejected(client):
    response = client.patch(
        "/api/photos/some-id",
        json={"caption": "new caption"},
        headers={"X-API-Key": ""},
    )
    assert response.status_code == 401


def test_read_endpoints_work_without_api_key(client):
    assert client.get("/api/photos", headers={"X-API-Key": ""}).status_code == 200
    assert client.get("/api/storage", headers={"X-API-Key": ""}).status_code == 200
    assert (
        client.post(
            "/api/photos/search",
            json={"query": "anything"},
            headers={"X-API-Key": ""},
        ).status_code
        == 200
    )


def test_upload_rate_limit_returns_429_after_threshold(client):
    for _ in range(10):
        response = client.post(
            "/api/photos/upload",
            files={"file": ("beach.jpg", _jpeg_bytes(), "image/jpeg")},
        )
        assert response.status_code == 200

    response = client.post(
        "/api/photos/upload",
        files={"file": ("beach.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 429

    # A different, undecorated endpoint's counter is unaffected.
    assert client.get("/api/storage").status_code == 200
