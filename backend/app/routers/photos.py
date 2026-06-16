import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.triton_client import encode_image, encode_text
from app.services.vector_store import search_photos, upsert_photo

PHOTOS_DIR = Path(os.getenv("PHOTOS_DIR", "/photos"))
router = APIRouter()


class SearchRequest(BaseModel):
    query: str


def _photo_id(image_bytes: bytes) -> str:
    digest = hashlib.sha256(image_bytes).hexdigest()
    return str(uuid.UUID(digest[:32]))


@router.post("/photos/upload")
async def upload_photo(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_bytes = await file.read()
    photo_id = _photo_id(image_bytes)

    matches = list(PHOTOS_DIR.glob(f"{photo_id}_*"))
    if matches:
        return {"id": photo_id, "filename": matches[0].name.split("_", 1)[1]}

    filename = f"{photo_id}_{file.filename}"
    file_path = PHOTOS_DIR / filename
    file_path.write_bytes(image_bytes)

    embedding = await encode_image(image_bytes)
    await upsert_photo(
        photo_id=photo_id,
        embedding=embedding,
        file_path=str(file_path),
        filename=file.filename or "",
        uploaded_at=datetime.now(timezone.utc).isoformat(),
    )

    return {"id": photo_id, "filename": file.filename}


MIN_SCORE = 0.20


@router.post("/photos/search")
async def search_photos_endpoint(body: SearchRequest):
    embedding = await encode_text(body.query)
    results = await search_photos(embedding, top_k=10)
    return [
        {
            "id": str(hit.id),
            "filename": hit.payload["filename"],
            "score": hit.score,
        }
        for hit in results
        if hit.score >= MIN_SCORE
    ]


@router.get("/photos/{photo_id}")
async def get_photo(photo_id: str):
    matches = list(PHOTOS_DIR.glob(f"{photo_id}_*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(matches[0])
