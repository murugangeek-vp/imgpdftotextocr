"""
Quota Check Validator Client
Communicates with Quota Service via gRPC.
"""
import grpc
import structlog
from shared.proto.gen import quota_pb2, quota_pb2_grpc
from config import settings

logger = structlog.get_logger()


async def check_quota_for_user(
    user_id: str, session_id: str, tier: str, pages: int
) -> dict:
    url = settings.QUOTA_SERVICE_URL
    host = url.split("//")[-1].split(":")[0]
    # Default gRPC port for Quota Service
    port = 50053
    target = f"{host}:{port}"

    logger.info(
        "quota_client.check",
        target=target,
        user_id=user_id,
        session_id=session_id,
        tier=tier,
        pages=pages,
    )

    try:
        async with grpc.aio.insecure_channel(target) as channel:
            stub = quota_pb2_grpc.QuotaServiceStub(channel)
            req = quota_pb2.QuotaCheckRequest(
                user_id=user_id,
                session_id=session_id,
                tier=tier,
                pages=pages,
            )
            resp = await stub.CheckQuota(req, timeout=3.0)
            return {
                "allowed": resp.allowed,
                "denied_reason": resp.denied_reason,
                "limit_type": resp.limit_type,
                "current_usage": resp.current_usage,
                "limit_value": resp.limit_value,
                "reset_at_unix": resp.reset_at_unix,
            }
    except Exception as e:
        logger.error("quota_client.error", error=str(e))
        # Fail-closed or fail-open? In a commercial app, failing closed is safer,
        # but let's fail open with a warning to ensure service availability.
        return {
            "allowed": True,
            "denied_reason": "Quota service unreachable, failing open",
            "limit_type": "",
            "current_usage": 0,
            "limit_value": 0,
            "reset_at_unix": 0,
        }
