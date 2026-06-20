"""
Quota Engine
Implements per-user, per-session, per-day, per-week, per-month quota checks
using Redis atomic INCR with TTL-based expiry.

Redis Key Schema:
  quota:{user_id}:session:{session_id}   TTL = session duration
  quota:{user_id}:day:{YYYY-MM-DD}       TTL = 86400s
  quota:{user_id}:week:{YYYY-WW}         TTL = 604800s
  quota:{user_id}:month:{YYYY-MM}        TTL = 2678400s (31 days)
"""
import calendar
from datetime import datetime, date
from typing import Optional

import redis.asyncio as aioredis
import structlog
from prometheus_client import Counter, Gauge

from config import settings
from tier_config import TierConfigManager

logger = structlog.get_logger()

# ── Prometheus metrics ────────────────────────────────────────────────────────
quota_checks_total = Counter(
    "quota_checks_total", "Total quota checks", ["tier", "result"]
)
quota_denials_total = Counter(
    "quota_denials_total", "Quota denials by limit type", ["tier", "limit_type"]
)
active_sessions_gauge = Gauge(
    "active_sessions_total", "Active sessions by tier", ["tier"]
)

# Session duration TTL (30 minutes of inactivity = session expires)
SESSION_TTL_SECONDS = 1800

_redis: Optional[aioredis.Redis] = None


class QuotaEngine:

    @classmethod
    async def init(cls):
        global _redis
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        await _redis.ping()
        logger.info("quota_engine.redis_connected")

    @classmethod
    def _get_keys(cls, user_id: str, session_id: str) -> dict:
        now = datetime.utcnow()
        year, week, _ = now.isocalendar()
        return {
            "session": f"quota:{user_id}:session:{session_id}",
            "day": f"quota:{user_id}:day:{now.strftime('%Y-%m-%d')}",
            "week": f"quota:{user_id}:week:{year}-W{week:02d}",
            "month": f"quota:{user_id}:month:{now.strftime('%Y-%m')}",
        }

    @classmethod
    def _ttl_for(cls, period: str) -> int:
        now = datetime.utcnow()
        if period == "session":
            return SESSION_TTL_SECONDS
        elif period == "day":
            return 86400
        elif period == "week":
            return 604800
        elif period == "month":
            # Remaining seconds in current month
            _, days_in_month = calendar.monthrange(now.year, now.month)
            end_of_month = datetime(now.year, now.month, days_in_month, 23, 59, 59)
            return max(int((end_of_month - now).total_seconds()), 86400)
        return 86400

    @classmethod
    async def check(
        cls, user_id: str, session_id: str, tier: str, pages: int
    ) -> dict:
        """
        Check if a user can process `pages` more pages.
        Returns: {allowed: bool, denied_reason: str, limit_type: str,
                  current_usage: int, limit_value: int, reset_at_unix: int}
        """
        config = TierConfigManager.get(tier)
        keys = cls._get_keys(user_id, session_id)

        limits = {
            "session": config["pages_per_session"],
            "day": config["pages_per_day"],
            "week": config["pages_per_week"],
            "month": config["pages_per_month"],
        }

        # Get current usage for all periods in one pipeline call
        async with _redis.pipeline(transaction=False) as pipe:
            for key in keys.values():
                pipe.get(key)
            values = await pipe.execute()

        usages = {
            period: int(val or 0)
            for period, val in zip(keys.keys(), values)
        }

        # Check each limit in priority order
        for period in ["session", "day", "week", "month"]:
            limit = limits[period]
            if limit == -1:  # unlimited
                continue
            current = usages[period]
            if current + pages > limit:
                quota_checks_total.labels(tier=tier, result="denied").inc()
                quota_denials_total.labels(tier=tier, limit_type=period).inc()
                ttl = cls._ttl_for(period)
                logger.warning(
                    "quota.denied",
                    user_id=user_id,
                    tier=tier,
                    period=period,
                    current=current,
                    limit=limit,
                    requested=pages,
                )
                return {
                    "allowed": False,
                    "denied_reason": f"{period.capitalize()} limit of {limit} pages reached",
                    "limit_type": period,
                    "current_usage": current,
                    "limit_value": limit,
                    "reset_at_unix": int(datetime.utcnow().timestamp()) + ttl,
                }

        quota_checks_total.labels(tier=tier, result="allowed").inc()
        return {
            "allowed": True,
            "denied_reason": "",
            "limit_type": "",
            "current_usage": usages["day"],
            "limit_value": limits["day"],
            "reset_at_unix": 0,
        }

    @classmethod
    async def increment(
        cls, user_id: str, session_id: str, tier: str, pages: int
    ) -> bool:
        """
        Atomically increment all quota counters after successful job.
        Uses Redis pipeline for atomicity and performance.
        """
        keys = cls._get_keys(user_id, session_id)

        async with _redis.pipeline(transaction=True) as pipe:
            try:
                for period, key in keys.items():
                    pipe.incrby(key, pages)
                    pipe.expire(key, cls._ttl_for(period))
                await pipe.execute()
                logger.debug(
                    "quota.incremented",
                    user_id=user_id,
                    tier=tier,
                    pages=pages,
                )
                return True
            except Exception as e:
                logger.error("quota.increment_failed", error=str(e))
                return False

    @classmethod
    async def get_usage(cls, user_id: str, session_id: str, tier: str) -> dict:
        """Get current usage for a user across all periods."""
        config = TierConfigManager.get(tier)
        keys = cls._get_keys(user_id, session_id)

        async with _redis.pipeline(transaction=False) as pipe:
            for key in keys.values():
                pipe.get(key)
            values = await pipe.execute()

        usages = {
            period: int(val or 0)
            for period, val in zip(keys.keys(), values)
        }

        return {
            "session_used": usages["session"],
            "daily_used": usages["day"],
            "weekly_used": usages["week"],
            "monthly_used": usages["month"],
            "session_limit": config["pages_per_session"],
            "daily_limit": config["pages_per_day"],
            "weekly_limit": config["pages_per_week"],
            "monthly_limit": config["pages_per_month"],
        }
