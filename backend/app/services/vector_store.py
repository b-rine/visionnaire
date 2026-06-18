import os

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.models import Distance, PointStruct, ScoredPoint, VectorParams

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION = "photos"
VECTOR_SIZE = 768


def _client() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=15)


async def init_collection() -> None:
    client = _client()
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION in existing:
        info = client.get_collection(COLLECTION)
        vectors = info.config.params.vectors
        current_size = vectors.size if isinstance(vectors, VectorParams) else None
        if current_size == VECTOR_SIZE:
            return
        # Dimension changed (e.g. switched models) — recreate
        client.delete_collection(COLLECTION)
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )


async def upsert_photo(
    photo_id: str,
    embedding: list[float],
    filename: str,
    uploaded_at: str,
    file_size: int,
) -> None:
    client = _client()
    client.upsert(
        collection_name=COLLECTION,
        points=[
            PointStruct(
                id=photo_id,
                vector=embedding,
                payload={
                    "filename": filename,
                    "uploaded_at": uploaded_at,
                    "file_size": file_size,
                },
            )
        ],
    )


async def delete_photo(photo_id: str) -> None:
    client = _client()
    client.delete(
        collection_name=COLLECTION,
        points_selector=qmodels.PointIdsList(points=[photo_id]),
    )


async def get_total_storage_bytes() -> int:
    client = _client()
    total, offset = 0, None
    while True:
        records, next_offset = client.scroll(
            collection_name=COLLECTION,
            offset=offset,
            limit=256,
            with_payload=["file_size"],
            with_vectors=False,
        )
        total += sum(r.payload.get("file_size", 0) for r in records)
        if next_offset is None:
            break
        offset = next_offset
    return total


async def list_photos(
    limit: int = 50,
    offset: str | None = None,
) -> tuple[list[dict], str | None]:
    client = _client()
    records, next_offset = client.scroll(
        collection_name=COLLECTION,
        offset=offset,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    photos = [
        {
            "id": str(r.id),
            "filename": r.payload.get("filename", ""),
            "uploaded_at": r.payload.get("uploaded_at", ""),
            "file_size": r.payload.get("file_size", 0),
        }
        for r in records
    ]
    return photos, str(next_offset) if next_offset is not None else None


async def search_photos(
    query_embedding: list[float],
    top_k: int = 10,
) -> list[ScoredPoint]:
    client = _client()
    return client.search(
        collection_name=COLLECTION,
        query_vector=query_embedding,
        limit=top_k,
        with_payload=True,
    )
