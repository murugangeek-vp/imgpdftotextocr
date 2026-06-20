"""
Quota Service — Main FastAPI Application
Handles per-user, per-session, per-day, per-week, per-month quota enforcement
with dynamically configurable tier limits (no restart required).
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import make_asgi_app

from config import settings
from database import Database
from routers import quota, tiers, health
from quota_engine import QuotaEngine
from tier_config import TierConfigManager

# ── Structured logging ────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger()


# ── OpenTelemetry setup ───────────────────────────────────────────────────────
def setup_telemetry():
    resource = Resource(attributes={"service.name": "quota-service"})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.OTLP_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


# ── App lifecycle ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("quota_service.startup", env=settings.APP_ENV)
    setup_telemetry()
    await Database.connect()
    await QuotaEngine.init()
    await TierConfigManager.load_all()
    # Start background task: refresh tier configs from DB every 60s
    refresh_task = asyncio.create_task(TierConfigManager.refresh_loop())
    # Start gRPC server
    from grpc_server import start_grpc_server
    grpc_server = await start_grpc_server("0.0.0.0", settings.QUOTA_SERVICE_GRPC_PORT)
    yield
    await grpc_server.stop(grace=5)
    refresh_task.cancel()
    await Database.disconnect()
    logger.info("quota_service.shutdown")


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Quota Service",
    description="Per-user, per-session, per-day/week/month cost control",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Kong handles CORS at edge
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router, tags=["health"])
app.include_router(quota.router, prefix="/api/v1/quota", tags=["quota"])
app.include_router(tiers.router, prefix="/api/v1/tiers", tags=["tiers"])

# ── Instrument with OTel ─────────────────────────────────────────────────────
FastAPIInstrumentor.instrument_app(app)
