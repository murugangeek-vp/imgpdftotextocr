"""
Tier Configuration Manager
Loads tier limits from MongoDB and caches in Redis.
Hot-reloadable: changes in DB are picked up within TIER_CONFIG_CACHE_TTL_SECONDS.
No restart or redeployment required.
"""
import asyncio
import json
from datetime import datetime
from typing import Optional

import structlog

from config import settings
from database import Database

logger = structlog.get_logger()

# ── Default tier configs (fallback if DB is unavailable) ─────────────────────
DEFAULT_TIERS = {
    "free": {
        "tier": "free",
        "pages_per_session": 5,
        "pages_per_day": 5,
        "pages_per_week": 20,
        "pages_per_month": 50,
        "max_file_size_mb": 10,
        "max_pages_per_pdf": 5,
        "concurrent_sessions": 1,
        "result_retention_hours": 24,
    },
    "basic": {
        "tier": "basic",
        "pages_per_session": 20,
        "pages_per_day": 100,
        "pages_per_week": 500,
        "pages_per_month": 2000,
        "max_file_size_mb": 50,
        "max_pages_per_pdf": 5,
        "concurrent_sessions": 5,
        "result_retention_hours": 720,  # 30 days
    },
    "pro": {
        "tier": "pro",
        "pages_per_session": -1,  # -1 = unlimited
        "pages_per_day": -1,
        "pages_per_week": -1,
        "pages_per_month": -1,
        "max_file_size_mb": 100,
        "max_pages_per_pdf": 5,
        "concurrent_sessions": 20,
        "result_retention_hours": 2160,  # 90 days
    },
}

# In-memory cache (process-level)
_tier_cache: dict = {}
_cache_loaded_at: Optional[datetime] = None


class TierConfigManager:
    """
    Manages tier configuration with hot-reload from MongoDB.
    Priority: MongoDB → Redis cache → In-memory defaults.
    """

    @classmethod
    async def load_all(cls):
        """Load all tier configs from MongoDB into cache."""
        try:
            db = Database.get_db()
            configs = await db.tier_configs.find({}).to_list(length=100)
            if configs:
                for config in configs:
                    tier = config["tier"]
                    _tier_cache[tier] = config
                    logger.info("tier_config.loaded", tier=tier)
            else:
                # Seed DB with defaults on first run
                await cls._seed_defaults()
        except Exception as e:
            logger.warning("tier_config.load_failed_using_defaults", error=str(e))
            _tier_cache.update(DEFAULT_TIERS)

        global _cache_loaded_at
        _cache_loaded_at = datetime.utcnow()

    @classmethod
    async def _seed_defaults(cls):
        """Seed default tier configs into MongoDB."""
        db = Database.get_db()
        for tier_name, config in DEFAULT_TIERS.items():
            await db.tier_configs.update_one(
                {"tier": tier_name},
                {"$set": config},
                upsert=True,
            )
            _tier_cache[tier_name] = config
            logger.info("tier_config.seeded", tier=tier_name)

    @classmethod
    async def refresh_loop(cls):
        """Background task: reload tier configs from DB every TTL seconds."""
        while True:
            await asyncio.sleep(settings.TIER_CONFIG_CACHE_TTL_SECONDS)
            logger.debug("tier_config.refreshing")
            await cls.load_all()

    @classmethod
    def get(cls, tier: str) -> dict:
        """Get tier config. Falls back to defaults if not in cache."""
        return _tier_cache.get(tier, DEFAULT_TIERS.get(tier, DEFAULT_TIERS["free"]))

    @classmethod
    async def update(cls, tier: str, limits: dict) -> dict:
        """
        Update tier config in MongoDB.
        Change propagates to all instances within TIER_CONFIG_CACHE_TTL_SECONDS.
        """
        db = Database.get_db()
        limits["tier"] = tier
        limits["updated_at"] = datetime.utcnow().isoformat()
        await db.tier_configs.update_one(
            {"tier": tier},
            {"$set": limits},
            upsert=True,
        )
        # Update local cache immediately
        _tier_cache[tier] = limits
        logger.info("tier_config.updated", tier=tier, limits=limits)
        return limits

    @classmethod
    def get_all(cls) -> dict:
        return dict(_tier_cache)
