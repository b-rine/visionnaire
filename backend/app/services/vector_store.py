import os
from asyncio import to_thread

from app.logging_utils import log_call
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchText,
    PointStruct,
    Record,
    ScoredPoint,
    TextIndexParams,
    TextIndexType,
    TokenizerType,
    VectorParams,
)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION = "photos"
VECTOR_SIZE = 768


async def qdrant_ready() -> bool:
    return await to_thread(lambda: bool(_client().get_collections().collections))


def _client() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=15)


def _payload(record: Record | ScoredPoint) -> dict:
    return record.payload or {}


@log_call("qdrant.init_collection")
async def init_collection() -> None:
    client = _client()
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION in existing:
        info = client.get_collection(COLLECTION)
        vectors = info.config.params.vectors
        current_size = vectors.size if isinstance(vectors, VectorParams) else None
        if current_size != VECTOR_SIZE:
            # Dimension changed (e.g. switched models) — recreate
            client.delete_collection(COLLECTION)
            client.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
    else:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
    _ensure_text_indexes(client)


def _ensure_text_indexes(client: QdrantClient) -> None:
    # WORD (not WHITESPACE) so punctuation-attached words like "Alex's" still
    # tokenize down to "alex" and remain matchable by a plain keyword query.
    text_index = TextIndexParams(
        type=TextIndexType.TEXT,
        tokenizer=TokenizerType.WORD,
        lowercase=True,
    )
    for field in ("caption", "caption_override"):
        client.create_payload_index(
            COLLECTION, field_name=field, field_schema=text_index
        )


@log_call("qdrant.upsert_photo", context_keys=("photo_id",))
async def upsert_photo(
    photo_id: str,
    embedding: list[float],
    filename: str,
    uploaded_at: str,
    file_size: int,
    caption: str,
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
                    "caption": caption,
                },
            )
        ],
    )


@log_call("qdrant.get_photo", context_keys=("photo_id",))
async def get_photo(photo_id: str) -> dict | None:
    client = _client()
    records = client.retrieve(
        collection_name=COLLECTION, ids=[photo_id], with_payload=True
    )
    if not records:
        return None
    r = records[0]
    payload = _payload(r)
    return {
        "id": str(r.id),
        "filename": payload.get("filename", ""),
        "uploaded_at": payload.get("uploaded_at", ""),
        "file_size": payload.get("file_size", 0),
        "caption": payload.get("caption", ""),
        "caption_override": payload.get("caption_override", ""),
    }


@log_call("qdrant.update_caption_override", context_keys=("photo_id",))
async def update_caption_override(photo_id: str, caption_override: str) -> None:
    client = _client()
    client.set_payload(
        collection_name=COLLECTION,
        payload={"caption_override": caption_override},
        points=[photo_id],
    )


@log_call("qdrant.delete_photo", context_keys=("photo_id",))
async def delete_photo(photo_id: str) -> None:
    client = _client()
    client.delete(
        collection_name=COLLECTION,
        points_selector=qmodels.PointIdsList(points=[photo_id]),
    )


@log_call("qdrant.get_total_storage_bytes")
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
        total += sum(_payload(r).get("file_size", 0) for r in records)
        if next_offset is None:
            break
        offset = next_offset
    return total


@log_call("qdrant.list_photos")
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
    photos = []
    for r in records:
        payload = _payload(r)
        photos.append(
            {
                "id": str(r.id),
                "filename": payload.get("filename", ""),
                "uploaded_at": payload.get("uploaded_at", ""),
                "file_size": payload.get("file_size", 0),
                "caption": payload.get("caption", ""),
                "caption_override": payload.get("caption_override", ""),
            }
        )
    return photos, str(next_offset) if next_offset is not None else None


@log_call("qdrant.search_photos")
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


@log_call("qdrant.search_photos_keyword", context_keys=("query",))
async def search_photos_keyword(query: str, top_k: int = 10) -> list[Record]:
    client = _client()
    records, _ = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            should=[
                FieldCondition(key="caption", match=MatchText(text=query)),
                FieldCondition(key="caption_override", match=MatchText(text=query)),
            ]
        ),
        limit=top_k,
        with_payload=True,
        with_vectors=False,
    )
    return records
