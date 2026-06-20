"""
Notification Service — Real-time SSE (Server-Sent Events)
Consumers Kafka completed/failed job events and pushes to browser clients.
Each client subscribes to their own job_id stream.
"""
import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from kafka import KafkaConsumer

from config import settings

logger = structlog.get_logger()

# In-memory SSE queue: {job_id: asyncio.Queue}
_sse_queues: dict[str, asyncio.Queue] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("notification_service.startup")
    # Start Kafka consumer in background
    task = asyncio.create_task(_kafka_consumer_loop())
    yield
    task.cancel()
    logger.info("notification_service.shutdown")


app = FastAPI(title="Notification Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


async def _kafka_consumer_loop():
    """Consume OCR completion events and push to SSE queues."""
    consumer = KafkaConsumer(
        settings.KAFKA_TOPIC_OCR_COMPLETED,
        settings.KAFKA_TOPIC_OCR_FAILED,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id="notification-service",
        auto_offset_reset="latest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )
    logger.info("notification.kafka_consumer_started")

    while True:
        msg_pack = await asyncio.get_event_loop().run_in_executor(
            None, lambda: consumer.poll(timeout_ms=500)
        )
        for tp, messages in msg_pack.items():
            for msg in messages:
                event = msg.value
                job_id = event.get("job_id")
                if job_id and job_id in _sse_queues:
                    await _sse_queues[job_id].put(event)


async def _event_generator(job_id: str, request: Request) -> AsyncGenerator[str, None]:
    """SSE event generator for a specific job."""
    queue = asyncio.Queue(maxsize=10)
    _sse_queues[job_id] = queue
    logger.info("sse.client_connected", job_id=job_id)

    try:
        # Send initial "connected" event
        yield f"data: {json.dumps({'status': 'connected', 'job_id': job_id})}\n\n"

        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25.0)
                yield f"data: {json.dumps(event)}\n\n"
                # If job is done, close stream
                if event.get("status") in ("completed", "failed"):
                    break
            except asyncio.TimeoutError:
                # Heartbeat to keep connection alive
                yield ": heartbeat\n\n"
    finally:
        _sse_queues.pop(job_id, None)
        logger.info("sse.client_disconnected", job_id=job_id)


@app.get("/api/v1/jobs/{job_id}/stream")
async def stream_job_status(job_id: str, request: Request):
    """
    Subscribe to real-time job status updates via Server-Sent Events.
    The browser connects here and receives status updates as the OCR job progresses.
    """
    return StreamingResponse(
        _event_generator(job_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "active_streams": len(_sse_queues)}
