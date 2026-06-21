import os

import boto3
import botocore.exceptions
from botocore.config import Config

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "visionnaire-photos")
_R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"


def _client():
    return boto3.client(
        "s3",
        endpoint_url=_R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


async def upload_photo_to_r2(
    photo_id: str, image_bytes: bytes, content_type: str
) -> None:
    _client().put_object(
        Bucket=R2_BUCKET_NAME,
        Key=photo_id,
        Body=image_bytes,
        ContentType=content_type,
    )


async def object_exists_in_r2(photo_id: str) -> bool:
    try:
        _client().head_object(Bucket=R2_BUCKET_NAME, Key=photo_id)
        return True
    except botocore.exceptions.ClientError:
        return False


async def get_r2_presigned_url(photo_id: str, expires_in: int = 300) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": photo_id},
        ExpiresIn=expires_in,
    )


async def delete_photo_from_r2(photo_id: str) -> None:
    _client().delete_object(Bucket=R2_BUCKET_NAME, Key=photo_id)
