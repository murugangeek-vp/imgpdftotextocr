"""
Result Service — Main FastAPI Application
"""
import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from config import settings
from database import Database
from consumer import start_kafka_consumer, stop_kafka_consumer
from routers import results, health

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("result_service.startup")
    await Database.connect()
    await start_kafka_consumer()
    yield
    await stop_kafka_consumer()
    await Database.disconnect()
    logger.info("result_service.shutdown")


app = FastAPI(
    title="Result Service",
    description="Manages job status database updates and query endpoints",
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(results.router, prefix="/api/v1/results", tags=["results"])
