import hashlib
import uuid
from datetime import datetime, timezone
from typing import Literal

from app.auth import limiter, require_api_key
from app.services.storage import delete_photo as delete_photo_from_storage
from app.services.storage import (
    photo_exists,
)
from app.services.storage import photo_response as get_photo_response
from app.services.storage import (
    upload_photo,
)
from app.services.triton_client import caption_image, encode_image, encode_text
from app.services.vector_store import (
    delete_photo,
)
from app.services.vector_store import get_photo as get_photo_record
from app.services.vector_store import (
    get_total_storage_bytes,
    list_photos,
    search_photos,
    search_photos_keyword,
    update_caption_override,
    upsert_photo,
)
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

STORAGE_LIMIT_BYTES = 1 * 1024**3  # 1 GiB
MIN_SCORE = 0.20
SCORE_CEILING = (
    0.35  # raw cosine representing a confident match for this CoCa checkpoint
)

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    mode: Literal["semantic", "keyword"] = "semantic"


class CaptionEditRequest(BaseModel):
    caption: str


def _photo_id(image_bytes: bytes) -> str:
    digest = hashlib.sha256(image_bytes).hexdigest()
    return str(uuid.UUID(digest[:32]))


def _display_score(raw_score: float) -> float:
    scaled = (raw_score - MIN_SCORE) / (SCORE_CEILING - MIN_SCORE)
    return max(0.0, min(1.0, scaled))


def _effective_caption(payload: dict) -> str:
    return payload.get("caption_override") or payload.get("caption", "")


@router.post("/photos/upload")
@limiter.limit("10/minute")
async def upload_photo_endpoint(
    request: Request,
    file: UploadFile = File(...),
    _: None = Depends(require_api_key),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_bytes = await file.read()
    photo_id = _photo_id(image_bytes)

    if await photo_exists(photo_id):
        existing = await get_photo_record(photo_id)
        return {
            "id": photo_id,
            "filename": file.filename,
            "caption": _effective_caption(existing) if existing else "",
        }

    file_size = len(image_bytes)
    used = await get_total_storage_bytes()
    if used + file_size > STORAGE_LIMIT_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Storage limit reached (1 GB). Delete some photos first.",
        )

    await upload_photo(photo_id, image_bytes, file.content_type or "image/jpeg")
    embedding = await encode_image(image_bytes)
    caption = await caption_image(image_bytes)
    await upsert_photo(
        photo_id=photo_id,
        embedding=embedding,
        filename=file.filename or "",
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        file_size=file_size,
        caption=caption,
    )

    return {"id": photo_id, "filename": file.filename, "caption": caption}


@router.post("/photos/search")
@limiter.limit("20/minute")
async def search_photos_endpoint(request: Request, body: SearchRequest):
    if body.mode == "keyword":
        records = await search_photos_keyword(body.query, top_k=10)
        return [
            {
                "id": str(record.id),
                "filename": (record.payload or {})["filename"],
                "caption": _effective_caption(record.payload or {}),
            }
            for record in records
        ]

    embedding = await encode_text(body.query)
    results = await search_photos(embedding, top_k=10)
    return [
        {
            "id": str(hit.id),
            "filename": (hit.payload or {})["filename"],
            "caption": _effective_caption(hit.payload or {}),
            "score": _display_score(hit.score),
        }
        for hit in results
        if hit.score >= MIN_SCORE
    ]


@router.get("/photos")
async def list_photos_endpoint(limit: int = 50, offset: str | None = None):
    photos, next_offset = await list_photos(limit=limit, offset=offset)
    photos = [{**p, "caption": _effective_caption(p)} for p in photos]
    for p in photos:
        p.pop("caption_override", None)
    return {"photos": photos, "next_offset": next_offset}


@router.patch("/photos/{photo_id}")
@limiter.limit("30/minute")
async def edit_caption(
    request: Request,
    photo_id: str,
    body: CaptionEditRequest,
    _: None = Depends(require_api_key),
):
    existing = await get_photo_record(photo_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    await update_caption_override(photo_id, body.caption)
    effective = body.caption or existing["caption"]
    return {"id": photo_id, "caption": effective}


@router.get("/storage")
async def storage_stats():
    used = await get_total_storage_bytes()
    return {"used_bytes": used, "limit_bytes": STORAGE_LIMIT_BYTES}


@router.get("/photos/{photo_id}")
async def get_photo(photo_id: str):
    if not await photo_exists(photo_id):
        raise HTTPException(status_code=404, detail="Photo not found")
    return await get_photo_response(photo_id)


@router.delete("/photos/{photo_id}")
@limiter.limit("30/minute")
async def delete_photo_endpoint(
    request: Request,
    photo_id: str,
    _: None = Depends(require_api_key),
):
    if not await photo_exists(photo_id):
        raise HTTPException(status_code=404, detail="Photo not found")
    await delete_photo_from_storage(photo_id)
    await delete_photo(photo_id)
    return {"deleted": photo_id}
