"""
Quota Service — gRPC Servicer Implementation
"""
import grpc
import structlog
from shared.proto.gen import quota_pb2, quota_pb2_grpc
from quota_engine import QuotaEngine
from tier_config import TierConfigManager

logger = structlog.get_logger()


class QuotaServiceServicer(quota_pb2_grpc.QuotaServiceServicer):

    async def CheckQuota(self, request, context):
        logger.info(
            "grpc.check_quota",
            user_id=request.user_id,
            session_id=request.session_id,
            tier=request.tier,
            pages=request.pages,
        )
        try:
            res = await QuotaEngine.check(
                user_id=request.user_id,
                session_id=request.session_id,
                tier=request.tier,
                pages=request.pages,
            )
            return quota_pb2.QuotaCheckResponse(
                allowed=res["allowed"],
                denied_reason=res["denied_reason"],
                limit_type=res["limit_type"],
                current_usage=res["current_usage"],
                limit_value=res["limit_value"],
                reset_at_unix=res["reset_at_unix"],
            )
        except Exception as e:
            logger.error("grpc.check_quota_failed", error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return quota_pb2.QuotaCheckResponse(allowed=False, denied_reason=str(e))

    async def IncrementQuota(self, request, context):
        logger.info(
            "grpc.increment_quota",
            user_id=request.user_id,
            session_id=request.session_id,
            tier=request.tier,
            pages=request.pages,
        )
        try:
            success = await QuotaEngine.increment(
                user_id=request.user_id,
                session_id=request.session_id,
                tier=request.tier,
                pages=request.pages,
            )
            return quota_pb2.QuotaIncrementResponse(success=success)
        except Exception as e:
            logger.error("grpc.increment_quota_failed", error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return quota_pb2.QuotaIncrementResponse(success=False)

    async def GetUsage(self, request, context):
        logger.info("grpc.get_usage", user_id=request.user_id, tier=request.tier)
        try:
            # We don't have session_id in the request for GetUsage, we default it to empty or retrieve from active session keys if needed.
            # In the proto, QuotaUsageRequest only has user_id and tier. Let's pass empty string for session_id.
            usage = await QuotaEngine.get_usage(
                user_id=request.user_id,
                session_id="",
                tier=request.tier,
            )
            return quota_pb2.QuotaUsageResponse(
                session_used=usage["session_used"],
                daily_used=usage["daily_used"],
                weekly_used=usage["weekly_used"],
                monthly_used=usage["monthly_used"],
                session_limit=usage["session_limit"],
                daily_limit=usage["daily_limit"],
                weekly_limit=usage["weekly_limit"],
                monthly_limit=usage["monthly_limit"],
            )
        except Exception as e:
            logger.error("grpc.get_usage_failed", error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return quota_pb2.QuotaUsageResponse()

    async def GetTierConfig(self, request, context):
        logger.info("grpc.get_tier_config", tier=request.tier)
        try:
            config = TierConfigManager.get(request.tier)
            return quota_pb2.TierConfig(
                tier=config["tier"],
                pages_per_session=config["limits"]["pages_per_session"],
                pages_per_day=config["limits"]["pages_per_day"],
                pages_per_week=config["limits"]["pages_per_week"],
                pages_per_month=config["limits"]["pages_per_month"],
                max_file_size_mb=config["limits"]["max_file_size_mb"],
                max_pages_per_pdf=config["limits"]["max_pages_per_pdf"],
                concurrent_sessions=config["limits"]["concurrent_sessions"],
                result_retention_hours=config["limits"].get("result_retention_hours", config["limits"].get("result_retention_days", 24) * 24),
            )
        except Exception as e:
            logger.error("grpc.get_tier_config_failed", error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return quota_pb2.TierConfig()


async def start_grpc_server(host: str, port: int):
    server = grpc.aio.server()
    quota_pb2_grpc.add_QuotaServiceServicer_to_server(
        QuotaServiceServicer(), server
    )
    server.add_insecure_port(f"{host}:{port}")
    logger.info("grpc.server_starting", host=host, port=port)
    await server.start()
    return server
