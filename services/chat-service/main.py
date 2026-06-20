"""
Chat Service — FastAPI App
Provides LLM chat over OCR-extracted text with:
- Smart model routing (OpenAI GPT-4o ↔ Ollama Llama 3.2:1b)
- Langfuse tracing for all LLM calls
- RAGAS evaluation on sample responses
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langfuse import Langfuse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import make_asgi_app

from config import settings
from database import Database
from routers import chat, health

logger = structlog.get_logger()

# Initialize Langfuse client (singleton)
langfuse = Langfuse(
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("chat_service.startup")
    await Database.connect()
    app.state.langfuse = langfuse
    yield
    await Database.disconnect()
    langfuse.flush()
    logger.info("chat_service.shutdown")


app = FastAPI(
    title="Chat Service",
    description="LLM chat over OCR-extracted text with OpenAI GPT-4o + Ollama fallback",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

app.include_router(health.router, tags=["health"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])

FastAPIInstrumentor.instrument_app(app)
