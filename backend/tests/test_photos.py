import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.routers.photos import _display_score
from PIL import Image


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(0, 128, 255)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.parametrize(
    "raw_score,expected",
    [
        (0.20, 0.0),  # floor (MIN_SCORE)
        (0.35, 1.0),  # ceiling (SCORE_CEILING)
        (0.50, 1.0),  # above ceiling, clamped
        (0.275, 0.5),  # midpoint
    ],
)
def test_display_score(raw_score, expected):
    assert _display_score(raw_score) == pytest.approx(expected)


def test_upload_returns_id_and_filename(client):
    response = client.post(
        "/api/photos/upload",
        files={"file": ("beach.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "id" in body
    assert body["filename"] == "beach.jpg"
    assert body["caption"] == "a cat on a mat"


def test_upload_rejects_non_image(client):
    response = client.post(
        "/api/photos/upload",
        files={"file": ("note.txt", b"text content", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_calls_storage(client):
    with patch(
        "app.routers.photos.upload_photo", new_callable=AsyncMock
    ) as mock_storage:
        client.post(
            "/api/photos/upload",
            files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
        )
    mock_storage.assert_called_once()
    assert mock_storage.call_args[0][0]  # photo_id was passed


def test_upload_deduplicates(client):
    jpeg = _jpeg_bytes()
    with (
        patch(
            "app.routers.photos.photo_exists",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.routers.photos.upload_photo", new_callable=AsyncMock
        ) as mock_storage,
    ):
        r1 = client.post(
            "/api/photos/upload", files={"file": ("img.jpg", jpeg, "image/jpeg")}
        )
        r2 = client.post(
            "/api/photos/upload", files={"file": ("img.jpg", jpeg, "image/jpeg")}
        )
    assert r1.json()["id"] == r2.json()["id"]
    mock_storage.assert_not_called()


def test_upload_dedup_returns_stored_caption(client):
    jpeg = _jpeg_bytes()
    with (
        patch(
            "app.routers.photos.photo_exists",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.routers.photos.get_photo_record",
            new_callable=AsyncMock,
            return_value={
                "id": "x",
                "filename": "img.jpg",
                "uploaded_at": "",
                "file_size": 1,
                "caption": "a dog on a beach",
            },
        ),
    ):
        response = client.post(
            "/api/photos/upload", files={"file": ("img.jpg", jpeg, "image/jpeg")}
        )
    assert response.json()["caption"] == "a dog on a beach"


def test_upload_reindexes_when_storage_exists_but_qdrant_point_missing(client):
    """Covers storage/vector-store drift: e.g. a shared storage backend
    (same R2 bucket) reused across environments with separate, independent
    Qdrant collections. photo_exists() can be True while get_photo_record()
    is None for the same photo_id — the upload must self-heal by indexing
    into Qdrant instead of silently returning a blank caption."""
    jpeg = _jpeg_bytes()
    with (
        patch(
            "app.routers.photos.photo_exists",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.routers.photos.get_photo_record",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.routers.photos.upload_photo", new_callable=AsyncMock
        ) as mock_storage,
        patch("app.routers.photos.upsert_photo", new_callable=AsyncMock) as mock_upsert,
    ):
        response = client.post(
            "/api/photos/upload", files={"file": ("img.jpg", jpeg, "image/jpeg")}
        )
    assert response.status_code == 200
    assert response.json()["caption"] == "a cat on a mat"
    mock_storage.assert_not_called()
    mock_upsert.assert_called_once()


def test_upload_rejects_over_storage_limit(client):
    one_gib = 1 * 1024**3
    with patch(
        "app.routers.photos.get_total_storage_bytes",
        new_callable=AsyncMock,
        return_value=one_gib,
    ):
        response = client.post(
            "/api/photos/upload",
            files={"file": ("big.jpg", _jpeg_bytes(), "image/jpeg")},
        )
    assert response.status_code == 400
    assert "Storage limit" in response.json()["detail"]


def test_search_returns_results(client):
    hit = MagicMock()
    hit.id = "photo-abc"
    hit.payload = {"filename": "mountain.jpg", "caption": "a mountain over a lake"}
    hit.score = 0.275  # midpoint of MIN_SCORE..SCORE_CEILING -> 0.5 display score

    with patch(
        "app.routers.photos.search_photos", new_callable=AsyncMock, return_value=[hit]
    ):
        response = client.post("/api/photos/search", json={"query": "a mountain lake"})

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == "photo-abc"
    assert results[0]["filename"] == "mountain.jpg"
    assert results[0]["caption"] == "a mountain over a lake"
    assert results[0]["score"] == pytest.approx(0.5)


def test_search_filters_low_score_results(client):
    def make_hit(id, score):
        h = MagicMock()
        h.id = id
        h.payload = {"filename": f"{id}.jpg"}
        h.score = score
        return h

    hits = [make_hit("a", 0.25), make_hit("b", 0.19)]
    with patch(
        "app.routers.photos.search_photos", new_callable=AsyncMock, return_value=hits
    ):
        response = client.post("/api/photos/search", json={"query": "something"})

    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == "a"
    assert results[0]["score"] == pytest.approx(1 / 3)


def test_search_returns_empty_list(client):
    response = client.post("/api/photos/search", json={"query": "nothing here"})
    assert response.status_code == 200
    assert response.json() == []


def test_search_uses_caption_override_when_present(client):
    hit = MagicMock()
    hit.id = "photo-abc"
    hit.payload = {
        "filename": "mountain.jpg",
        "caption": "a mountain over a lake",
        "caption_override": "Lake Tahoe trip",
    }
    hit.score = 0.275

    with patch(
        "app.routers.photos.search_photos", new_callable=AsyncMock, return_value=[hit]
    ):
        response = client.post("/api/photos/search", json={"query": "a mountain lake"})

    assert response.json()[0]["caption"] == "Lake Tahoe trip"


def test_keyword_search_returns_results_without_score(client):
    record = MagicMock()
    record.id = "photo-xyz"
    record.payload = {
        "filename": "party.jpg",
        "caption": "a group of people at a table",
    }

    with patch(
        "app.routers.photos.search_photos_keyword",
        new_callable=AsyncMock,
        return_value=[record],
    ) as mock_kw:
        response = client.post(
            "/api/photos/search", json={"query": "Alex", "mode": "keyword"}
        )

    mock_kw.assert_called_once_with("Alex", top_k=10)
    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == "photo-xyz"
    assert results[0]["caption"] == "a group of people at a table"
    assert "score" not in results[0]


def test_keyword_search_uses_caption_override(client):
    record = MagicMock()
    record.id = "photo-xyz"
    record.payload = {
        "filename": "party.jpg",
        "caption": "a group of people at a table",
        "caption_override": "Alex's birthday",
    }

    with patch(
        "app.routers.photos.search_photos_keyword",
        new_callable=AsyncMock,
        return_value=[record],
    ):
        response = client.post(
            "/api/photos/search", json={"query": "Alex", "mode": "keyword"}
        )

    assert response.json()[0]["caption"] == "Alex's birthday"


def test_list_photos_returns_page(client):
    photos = [
        {
            "id": "a",
            "filename": "a.jpg",
            "uploaded_at": "2026-01-01T00:00:00Z",
            "file_size": 100,
            "caption": "a cat",
        },
        {
            "id": "b",
            "filename": "b.jpg",
            "uploaded_at": "2026-01-02T00:00:00Z",
            "file_size": 200,
            "caption": "a dog",
        },
    ]
    with patch(
        "app.routers.photos.list_photos",
        new_callable=AsyncMock,
        return_value=(photos, "b"),
    ):
        response = client.get("/api/photos")
    assert response.status_code == 200
    body = response.json()
    assert body["photos"] == photos
    assert body["next_offset"] == "b"


def test_list_photos_passes_pagination_params(client):
    with patch(
        "app.routers.photos.list_photos",
        new_callable=AsyncMock,
        return_value=([], None),
    ) as mock_list:
        client.get("/api/photos?limit=10&offset=xyz")
    mock_list.assert_called_once_with(limit=10, offset="xyz")


def test_storage_stats(client):
    one_gib = 1 * 1024**3
    with patch(
        "app.routers.photos.get_total_storage_bytes",
        new_callable=AsyncMock,
        return_value=12345,
    ):
        response = client.get("/api/storage")
    assert response.status_code == 200
    assert response.json() == {"used_bytes": 12345, "limit_bytes": one_gib}


def test_get_photo_redirects(client):
    with patch(
        "app.routers.photos.photo_exists",
        new_callable=AsyncMock,
        return_value=True,
    ):
        response = client.get("/api/photos/some-id", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://r2.example.com/photo"


def test_get_photo_not_found(client):
    response = client.get("/api/photos/does-not-exist")
    assert response.status_code == 404


def test_delete_photo_success(client):
    with patch(
        "app.routers.photos.photo_exists",
        new_callable=AsyncMock,
        return_value=True,
    ):
        response = client.delete("/api/photos/some-id")
    assert response.status_code == 200
    assert response.json() == {"deleted": "some-id"}


def test_delete_photo_not_found(client):
    response = client.delete("/api/photos/does-not-exist")
    assert response.status_code == 404


def test_edit_caption_success(client):
    existing = {
        "id": "some-id",
        "filename": "img.jpg",
        "uploaded_at": "",
        "file_size": 1,
        "caption": "a cat on a mat",
        "caption_override": "",
    }
    with (
        patch(
            "app.routers.photos.get_photo_record",
            new_callable=AsyncMock,
            return_value=existing,
        ),
        patch(
            "app.routers.photos.update_caption_override", new_callable=AsyncMock
        ) as mock_update,
    ):
        response = client.patch(
            "/api/photos/some-id", json={"caption": "Alex's birthday"}
        )

    assert response.status_code == 200
    assert response.json() == {"id": "some-id", "caption": "Alex's birthday"}
    mock_update.assert_called_once_with("some-id", "Alex's birthday")


def test_edit_caption_not_found(client):
    response = client.patch("/api/photos/does-not-exist", json={"caption": "anything"})
    assert response.status_code == 404


def test_edit_caption_empty_string_reverts_to_auto_caption(client):
    existing = {
        "id": "some-id",
        "filename": "img.jpg",
        "uploaded_at": "",
        "file_size": 1,
        "caption": "a cat on a mat",
        "caption_override": "old note",
    }
    with patch(
        "app.routers.photos.get_photo_record",
        new_callable=AsyncMock,
        return_value=existing,
    ):
        response = client.patch("/api/photos/some-id", json={"caption": ""})

    assert response.status_code == 200
    assert response.json() == {"id": "some-id", "caption": "a cat on a mat"}
