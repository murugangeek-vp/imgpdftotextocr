"""
Ingestion Service — Main FastAPI Application
Handles file uploads, validation, quota enforcement, virus scanning,
and job submission to Kafka.
"""
import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import make_asgi_app

from config import settings
from database import Database
from storage import StorageClient
from kafka_producer import KafkaProducerClient
from routers import upload, presigned, health

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ingestion_service.startup")
    await Database.connect()
    await StorageClient.init()
    await KafkaProducerClient.init()
    yield
    await KafkaProducerClient.close()
    await Database.disconnect()
    logger.info("ingestion_service.shutdown")


app = FastAPI(
    title="Ingestion Service",
    description="File upload, validation, ClamAV scan, quota check, and OCR job submission",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

app.include_router(health.router, tags=["health"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])
app.include_router(presigned.router, prefix="/api/v1/presigned", tags=["presigned"])

FastAPIInstrumentor.instrument_app(app)
