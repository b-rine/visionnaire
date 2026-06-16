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


def test_upload_writes_file_to_disk(client, photos_dir):
    client.post(
        "/api/photos/upload",
        files={"file": ("mountain.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    saved = list(photos_dir.glob("*_mountain.jpg"))
    assert len(saved) == 1


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


def test_upload_deduplicates_identical_images(client, photos_dir):
    jpeg = _jpeg_bytes()
    r1 = client.post("/api/photos/upload", files={"file": ("img.jpg", jpeg, "image/jpeg")})
    r2 = client.post("/api/photos/upload", files={"file": ("img.jpg", jpeg, "image/jpeg")})
    assert r1.json()["id"] == r2.json()["id"]
    assert len(list(photos_dir.glob("*.jpg"))) == 1


def test_search_returns_empty_list(client):
    response = client.post("/api/photos/search", json={"query": "nothing here"})
    assert response.status_code == 200
    assert response.json() == []


def test_get_photo_not_found(client):
    response = client.get("/api/photos/does-not-exist")
    assert response.status_code == 404


def test_get_photo_found(client, photos_dir):
    photo_id = "test-photo-id"
    (photos_dir / f"{photo_id}_sunset.jpg").write_bytes(_jpeg_bytes())
    response = client.get(f"/api/photos/{photo_id}")
    assert response.status_code == 200
