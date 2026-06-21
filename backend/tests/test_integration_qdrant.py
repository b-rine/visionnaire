"""Tests against a real Qdrant instance — run with: docker compose up -d qdrant && pytest -v -m integration

Uses a throwaway collection name per test (via monkeypatching vector_store.COLLECTION)
so this never touches the real "photos" collection.
"""

import asyncio
import os
import uuid

import pytest
from app.services import vector_store as vs
from qdrant_client import QdrantClient

pytestmark = pytest.mark.integration

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))


@pytest.fixture(autouse=True)
def isolated_collection(monkeypatch):
    test_collection = f"test_integration_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(vs, "COLLECTION", test_collection)
    yield
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=15)
    client.delete_collection(test_collection)


def test_init_collection_is_idempotent():
    asyncio.run(vs.init_collection())
    asyncio.run(vs.init_collection())  # second call must not raise


def test_upsert_and_get_photo_round_trip():
    asyncio.run(vs.init_collection())
    photo_id = str(uuid.uuid4())
    asyncio.run(
        vs.upsert_photo(
            photo_id=photo_id,
            embedding=[0.0] * vs.VECTOR_SIZE,
            filename="test.jpg",
            uploaded_at="2026-01-01T00:00:00Z",
            file_size=123,
            caption="a cat on a mat",
        )
    )
    photo = asyncio.run(vs.get_photo(photo_id))
    assert photo is not None
    assert photo["filename"] == "test.jpg"
    assert photo["caption"] == "a cat on a mat"


def test_update_caption_override_round_trip():
    asyncio.run(vs.init_collection())
    photo_id = str(uuid.uuid4())
    asyncio.run(
        vs.upsert_photo(
            photo_id=photo_id,
            embedding=[0.0] * vs.VECTOR_SIZE,
            filename="x.jpg",
            uploaded_at="",
            file_size=1,
            caption="auto caption",
        )
    )
    asyncio.run(vs.update_caption_override(photo_id, "Alex's birthday"))
    photo = asyncio.run(vs.get_photo(photo_id))
    assert photo is not None
    assert photo["caption"] == "auto caption"
    assert photo["caption_override"] == "Alex's birthday"


def test_search_photos_keyword_matches_caption_text():
    asyncio.run(vs.init_collection())
    photo_id = str(uuid.uuid4())
    asyncio.run(
        vs.upsert_photo(
            photo_id=photo_id,
            embedding=[0.0] * vs.VECTOR_SIZE,
            filename="party.jpg",
            uploaded_at="",
            file_size=1,
            caption="a group of people at a birthday party",
        )
    )
    results = asyncio.run(vs.search_photos_keyword("birthday", top_k=10))
    assert any(str(r.id) == photo_id for r in results)


def test_search_photos_keyword_matches_caption_override():
    asyncio.run(vs.init_collection())
    photo_id = str(uuid.uuid4())
    asyncio.run(
        vs.upsert_photo(
            photo_id=photo_id,
            embedding=[0.0] * vs.VECTOR_SIZE,
            filename="party.jpg",
            uploaded_at="",
            file_size=1,
            caption="a group of people at a table",
        )
    )
    asyncio.run(vs.update_caption_override(photo_id, "Alex's birthday party"))
    results = asyncio.run(vs.search_photos_keyword("birthday", top_k=10))
    assert any(str(r.id) == photo_id for r in results)
