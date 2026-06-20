"""
Quota Increment client for OCR Worker.
Calls Quota Service via gRPC.
"""
import grpc
import structlog
from shared.proto.gen import quota_pb2, quota_pb2_grpc
from config import settings

logger = structlog.get_logger()


async def increment_quota(
    user_id: str, session_id: str, tier: str, pages: int
):
    url = settings.QUOTA_SERVICE_URL
    host = url.split("//")[-1].split(":")[0]
    port = 50053
    target = f"{host}:{port}"

    logger.info(
        "quota_client.increment",
        target=target,
        user_id=user_id,
        session_id=session_id,
        tier=tier,
        pages=pages,
    )

    try:
        async with grpc.aio.insecure_channel(target) as channel:
            stub = quota_pb2_grpc.QuotaServiceStub(channel)
            req = quota_pb2.QuotaIncrementRequest(
                user_id=user_id,
                session_id=session_id,
                tier=tier,
                pages=pages,
            )
            resp = await stub.IncrementQuota(req, timeout=3.0)
            if not resp.success:
                logger.error("quota_client.increment_rejected")
    except Exception as e:
        logger.error("quota_client.increment_failed", error=str(e))
