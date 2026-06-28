import os
from pathlib import Path

from app.logging_utils import log_call
from fastapi.responses import FileResponse, RedirectResponse

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
LOCAL_PHOTOS_DIR = Path(os.getenv("LOCAL_PHOTOS_DIR", "./photos"))


def _local_path(photo_id: str) -> Path:
    return LOCAL_PHOTOS_DIR / photo_id


@log_call("local.upload_photo", context_keys=("photo_id",))
async def _local_upload(photo_id: str, data: bytes, content_type: str) -> None:
    LOCAL_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    _local_path(photo_id).write_bytes(data)


@log_call("local.photo_exists", context_keys=("photo_id",))
async def _local_exists(photo_id: str) -> bool:
    return _local_path(photo_id).exists()


@log_call("local.delete_photo", context_keys=("photo_id",))
async def _local_delete(photo_id: str) -> None:
    path = _local_path(photo_id)
    if path.exists():
        path.unlink()


async def upload_photo(photo_id: str, data: bytes, content_type: str) -> None:
    if STORAGE_BACKEND == "r2":
        from app.services.r2_client import upload_photo_to_r2

        await upload_photo_to_r2(photo_id, data, content_type)
    else:
        await _local_upload(photo_id, data, content_type)


async def photo_exists(photo_id: str) -> bool:
    if STORAGE_BACKEND == "r2":
        from app.services.r2_client import object_exists_in_r2

        return await object_exists_in_r2(photo_id)
    else:
        return await _local_exists(photo_id)


async def delete_photo(photo_id: str) -> None:
    if STORAGE_BACKEND == "r2":
        from app.services.r2_client import delete_photo_from_r2

        await delete_photo_from_r2(photo_id)
    else:
        await _local_delete(photo_id)


async def photo_response(photo_id: str) -> FileResponse | RedirectResponse:
    if STORAGE_BACKEND == "r2":
        from app.services.r2_client import get_r2_presigned_url

        url = await get_r2_presigned_url(photo_id)
        return RedirectResponse(url, status_code=302)
    else:
        return FileResponse(_local_path(photo_id))
