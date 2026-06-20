"""
Quota Service API Routers — Quota endpoints
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from quota_engine import QuotaEngine

router = APIRouter()


class QuotaCheckRequest(BaseModel):
    user_id: str
    session_id: str
    tier: str
    pages: int


class QuotaCheckResponse(BaseModel):
    allowed: bool
    denied_reason: str = ""
    limit_type: str = ""
    current_usage: int = 0
    limit_value: int = 0
    reset_at_unix: int = 0


class QuotaIncrementRequest(BaseModel):
    user_id: str
    session_id: str
    tier: str
    pages: int


class QuotaUsageRequest(BaseModel):
    user_id: str
    session_id: str
    tier: str


@router.post("/check", response_model=QuotaCheckResponse)
async def check_quota(req: QuotaCheckRequest):
    """
    Check if a user can process N more pages.
    Call this BEFORE submitting any OCR job.
    Returns 200 with allowed=False instead of 429 — caller decides the HTTP status.
    """
    result = await QuotaEngine.check(
        user_id=req.user_id,
        session_id=req.session_id,
        tier=req.tier,
        pages=req.pages,
    )
    return QuotaCheckResponse(**result)


@router.post("/increment")
async def increment_quota(req: QuotaIncrementRequest):
    """
    Increment quota counters after a successful OCR job.
    Call this only after the job completes successfully.
    """
    success = await QuotaEngine.increment(
        user_id=req.user_id,
        session_id=req.session_id,
        tier=req.tier,
        pages=req.pages,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update quota counters",
        )
    return {"success": True}


@router.post("/usage", response_model=dict)
async def get_usage(req: QuotaUsageRequest):
    """Get current quota usage for a user across all time periods."""
    return await QuotaEngine.get_usage(
        user_id=req.user_id,
        session_id=req.session_id,
        tier=req.tier,
    )
