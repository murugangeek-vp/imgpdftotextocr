"""Health check router."""
from fastapi import APIRouter
from database import Database
from quota_engine import _redis

router = APIRouter()


@router.get("/health")
async def health():
    checks = {"service": "ok", "redis": "unknown", "mongodb": "unknown"}
    try:
        await _redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    try:
        db = Database.get_db()
        await db.command("ping")
        checks["mongodb"] = "ok"
    except Exception:
        checks["mongodb"] = "error"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
