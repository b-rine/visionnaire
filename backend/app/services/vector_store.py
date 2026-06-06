import os

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, ScoredPoint, VectorParams

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION = "photos"
VECTOR_SIZE = 512


def _client() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


async def init_collection() -> None:
    client = _client()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


async def upsert_photo(
    photo_id: str,
    embedding: list[float],
    file_path: str,
    filename: str,
    uploaded_at: str,
) -> None:
    client = _client()
    client.upsert(
        collection_name=COLLECTION,
        points=[
            PointStruct(
                id=photo_id,
                vector=embedding,
                payload={
                    "file_path": file_path,
                    "filename": filename,
                    "uploaded_at": uploaded_at,
                },
            )
        ],
    )


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
