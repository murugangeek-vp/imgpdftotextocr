"""
Tier config management endpoints.
Admins can update tier limits dynamically — changes propagate within 60 seconds
to all running service instances with NO restart or redeployment.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from tier_config import TierConfigManager

router = APIRouter()


class TierLimits(BaseModel):
    pages_per_session: int
    pages_per_day: int
    pages_per_week: int
    pages_per_month: int
    max_file_size_mb: int
    max_pages_per_pdf: int
    concurrent_sessions: int
    result_retention_hours: int


@router.get("/")
async def list_tiers():
    """List all current tier configurations."""
    return TierConfigManager.get_all()


@router.get("/{tier}")
async def get_tier(tier: str):
    """Get a specific tier's limits."""
    config = TierConfigManager.get(tier)
    if not config:
        raise HTTPException(status_code=404, detail=f"Tier '{tier}' not found")
    return config


@router.put("/{tier}")
async def update_tier(tier: str, limits: TierLimits):
    """
    Update a tier's limits dynamically.
    No restart required — changes are reflected within TIER_CONFIG_CACHE_TTL_SECONDS.

    NOTE: This endpoint should be protected by admin-only auth in production.
    """
    if tier not in ("free", "basic", "pro"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown tier: {tier}. Must be one of: free, basic, pro",
        )
    updated = await TierConfigManager.update(tier, limits.model_dump())
    return {
        "message": f"Tier '{tier}' updated. Changes propagate within 60 seconds.",
        "config": updated,
    }
