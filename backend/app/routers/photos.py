import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.services.r2_client import (
    delete_photo_from_r2,
    get_r2_presigned_url,
    object_exists_in_r2,
    upload_photo_to_r2,
)
from app.services.triton_client import caption_image, encode_image, encode_text
from app.services.vector_store import (
    delete_photo,
    get_photo as get_photo_record,
    get_total_storage_bytes,
    list_photos,
    search_photos,
    upsert_photo,
)

STORAGE_LIMIT_BYTES = 1 * 1024**3  # 1 GiB
MIN_SCORE = 0.20
SCORE_CEILING = 0.35  # raw cosine representing a confident match for this CoCa checkpoint

router = APIRouter()


class SearchRequest(BaseModel):
    query: str


def _photo_id(image_bytes: bytes) -> str:
    digest = hashlib.sha256(image_bytes).hexdigest()
    return str(uuid.UUID(digest[:32]))


def _display_score(raw_score: float) -> float:
    scaled = (raw_score - MIN_SCORE) / (SCORE_CEILING - MIN_SCORE)
    return max(0.0, min(1.0, scaled))


@router.post("/photos/upload")
async def upload_photo(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_bytes = await file.read()
    photo_id = _photo_id(image_bytes)

    if await object_exists_in_r2(photo_id):
        existing = await get_photo_record(photo_id)
        return {"id": photo_id, "filename": file.filename, "caption": existing["caption"] if existing else ""}

    file_size = len(image_bytes)
    used = await get_total_storage_bytes()
    if used + file_size > STORAGE_LIMIT_BYTES:
        raise HTTPException(status_code=400, detail="Storage limit reached (1 GB). Delete some photos first.")

    await upload_photo_to_r2(photo_id, image_bytes, file.content_type or "image/jpeg")
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
async def search_photos_endpoint(body: SearchRequest):
    embedding = await encode_text(body.query)
    results = await search_photos(embedding, top_k=10)
    return [
        {
            "id": str(hit.id),
            "filename": hit.payload["filename"],
            "caption": hit.payload.get("caption", ""),
            "score": _display_score(hit.score),
        }
        for hit in results
        if hit.score >= MIN_SCORE
    ]


@router.get("/photos")
async def list_photos_endpoint(limit: int = 50, offset: str | None = None):
    photos, next_offset = await list_photos(limit=limit, offset=offset)
    return {"photos": photos, "next_offset": next_offset}


@router.get("/storage")
async def storage_stats():
    used = await get_total_storage_bytes()
    return {"used_bytes": used, "limit_bytes": STORAGE_LIMIT_BYTES}


@router.get("/photos/{photo_id}")
async def get_photo(photo_id: str):
    if not await object_exists_in_r2(photo_id):
        raise HTTPException(status_code=404, detail="Photo not found")
    url = await get_r2_presigned_url(photo_id)
    return RedirectResponse(url, status_code=302)


@router.delete("/photos/{photo_id}")
async def delete_photo_endpoint(photo_id: str):
    if not await object_exists_in_r2(photo_id):
        raise HTTPException(status_code=404, detail="Photo not found")
    await delete_photo_from_r2(photo_id)
    await delete_photo(photo_id)
    return {"deleted": photo_id}
