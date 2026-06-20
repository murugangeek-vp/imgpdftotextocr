"""
File validator — checks MIME type, file size against tier limits.
"""
from fastapi import HTTPException, status
import httpx

from config import settings

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/tiff", "image/webp", "image/bmp",
    "application/pdf",
}


async def validate_file(
    filename: str,
    content_type: str,
    file_size_mb: float,
    tier: str,
) -> None:
    """
    Validate file type and size.
    Raises HTTPException on any validation failure.
    """
    # 1. MIME type check
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File type '{content_type}' is not supported. "
                f"Supported types: JPEG, PNG, TIFF, WebP, BMP, PDF"
            ),
        )

    # 2. Get tier limit from quota-service
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.QUOTA_SERVICE_URL}/api/v1/tiers/{tier}"
            )
            tier_config = resp.json()
            max_size_mb = tier_config.get("max_file_size_mb", 10)
    except Exception:
        # Fallback to safe default if quota-service is unreachable
        max_size_mb = 10

    # 3. File size check
    if file_size_mb > max_size_mb:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File size {file_size_mb:.1f} MB exceeds your plan limit of {max_size_mb} MB. "
                f"Upgrade your plan to process larger files."
            ),
        )
