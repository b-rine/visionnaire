from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.triton_client import caption_image

router = APIRouter()


@router.post("/caption")
async def caption_endpoint(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    image_bytes = await file.read()
    caption = await caption_image(image_bytes)
    return {"caption": caption}
