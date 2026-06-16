import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(0, 128, 255)).save(buf, format="JPEG")
    return buf.getvalue()


def test_upload_returns_id_and_filename(client):
    response = client.post(
        "/api/photos/upload",
        files={"file": ("beach.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "id" in body
    assert body["filename"] == "beach.jpg"


def test_upload_rejects_non_image(client):
    response = client.post(
        "/api/photos/upload",
        files={"file": ("note.txt", b"text content", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_calls_r2(client):
    with patch("app.routers.photos.upload_photo_to_r2", new_callable=AsyncMock) as mock_r2:
        client.post(
            "/api/photos/upload",
            files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
        )
    mock_r2.assert_called_once()
    assert mock_r2.call_args[0][0]  # photo_id was passed


def test_upload_deduplicates_via_r2_head(client):
    jpeg = _jpeg_bytes()
    with (
        patch("app.routers.photos.object_exists_in_r2", new_callable=AsyncMock, return_value=True),
        patch("app.routers.photos.upload_photo_to_r2", new_callable=AsyncMock) as mock_r2,
    ):
        r1 = client.post("/api/photos/upload", files={"file": ("img.jpg", jpeg, "image/jpeg")})
        r2 = client.post("/api/photos/upload", files={"file": ("img.jpg", jpeg, "image/jpeg")})
    assert r1.json()["id"] == r2.json()["id"]
    mock_r2.assert_not_called()


def test_upload_rejects_over_storage_limit(client):
    one_gib = 1 * 1024 ** 3
    with patch("app.routers.photos.get_total_storage_bytes", new_callable=AsyncMock, return_value=one_gib):
        response = client.post(
            "/api/photos/upload",
            files={"file": ("big.jpg", _jpeg_bytes(), "image/jpeg")},
        )
    assert response.status_code == 400
    assert "Storage limit" in response.json()["detail"]


def test_search_returns_results(client):
    hit = MagicMock()
    hit.id = "photo-abc"
    hit.payload = {"filename": "mountain.jpg"}
    hit.score = 0.92

    with patch("app.routers.photos.search_photos", new_callable=AsyncMock, return_value=[hit]):
        response = client.post("/api/photos/search", json={"query": "a mountain lake"})

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == "photo-abc"
    assert results[0]["filename"] == "mountain.jpg"
    assert results[0]["score"] == pytest.approx(0.92)


def test_search_filters_low_score_results(client):
    def make_hit(id, score):
        h = MagicMock()
        h.id = id
        h.payload = {"filename": f"{id}.jpg"}
        h.score = score
        return h

    hits = [make_hit("a", 0.25), make_hit("b", 0.19)]
    with patch("app.routers.photos.search_photos", new_callable=AsyncMock, return_value=hits):
        response = client.post("/api/photos/search", json={"query": "something"})

    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == "a"


def test_search_returns_empty_list(client):
    response = client.post("/api/photos/search", json={"query": "nothing here"})
    assert response.status_code == 200
    assert response.json() == []


def test_get_photo_redirects(client):
    with patch("app.routers.photos.object_exists_in_r2", new_callable=AsyncMock, return_value=True):
        response = client.get("/api/photos/some-id", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://r2.example.com/photo"


def test_get_photo_not_found(client):
    response = client.get("/api/photos/does-not-exist")
    assert response.status_code == 404


def test_delete_photo_success(client):
    with patch("app.routers.photos.object_exists_in_r2", new_callable=AsyncMock, return_value=True):
        response = client.delete("/api/photos/some-id")
    assert response.status_code == 200
    assert response.json() == {"deleted": "some-id"}


def test_delete_photo_not_found(client):
    response = client.delete("/api/photos/does-not-exist")
    assert response.status_code == 404
