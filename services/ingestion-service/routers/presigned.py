"""
Presigned URL router.
Provides endpoints for clients to request presigned S3 URLs to upload files directly.
"""
import uuid
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel

from config import settings
from storage import StorageClient
from validators.quota_check import check_quota_for_user

router = APIRouter()


class PresignedUrlRequest(BaseModel):
    file_name: str
    content_type: str
    user_id: str
    session_id: str
    tier: str = "free"


class PresignedUrlResponse(BaseModel):
    url: str
    job_id: str
    file_key: str
    bucket: str


@router.post("/", response_model=PresignedUrlResponse)
async def get_presigned_url(req: PresignedUrlRequest):
    """
    Generate a presigned upload URL for direct-to-S3 uploads.
    - Quota check is run for 1 page as a preliminary check before upload.
    """
    # 1. Quota check (assume at least 1 page)
    quota_result = await check_quota_for_user(
        user_id=req.user_id,
        session_id=req.session_id,
        tier=req.tier,
        pages=1,
    )
    if not quota_result["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "quota_exceeded",
                "message": quota_result["denied_reason"],
            },
        )

    job_id = str(uuid.uuid4())
    file_key = f"uploads/{req.user_id}/{job_id}/{req.file_name}"

    try:
        url = await StorageClient.generate_presigned_upload_url(
            bucket=settings.MINIO_BUCKET_UPLOADS,
            key=file_key,
            expiry_seconds=settings.PRESIGNED_URL_EXPIRY_SECONDS,
        )
        return PresignedUrlResponse(
            url=url,
            job_id=job_id,
            file_key=file_key,
            bucket=settings.MINIO_BUCKET_UPLOADS,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned URL: {str(e)}",
        )
