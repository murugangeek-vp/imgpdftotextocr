"""
Kafka consumer for Result Service.
Consumes completed/failed job results and updates MongoDB.
"""
import asyncio
import json
from datetime import datetime
from kafka import KafkaConsumer
import structlog
from config import settings
from database import Database

logger = structlog.get_logger()
_running = True


async def start_kafka_consumer():
    global _running
    _running = True
    asyncio.create_task(_run_consumer())


async def stop_kafka_consumer():
    global _running
    _running = False


async def _run_consumer():
    logger.info("result_consumer.starting")

    def _init_consumer():
        return KafkaConsumer(
            settings.KAFKA_TOPIC_OCR_COMPLETED,
            settings.KAFKA_TOPIC_OCR_FAILED,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )

    try:
        consumer = await asyncio.to_thread(_init_consumer)
    except Exception as e:
        logger.error("result_consumer.connection_error", error=str(e))
        return

    logger.info(
        "result_consumer.started",
        topics=[
            settings.KAFKA_TOPIC_OCR_COMPLETED,
            settings.KAFKA_TOPIC_OCR_FAILED,
        ],
    )

    while _running:
        try:
            msg_pack = await asyncio.to_thread(consumer.poll, timeout_ms=1000)
            for tp, messages in msg_pack.items():
                for msg in messages:
                    event = msg.value
                    await _process_event(event)
        except Exception as e:
            logger.error("result_consumer.error", error=str(e))
            await asyncio.sleep(2)

    await asyncio.to_thread(consumer.close)
    logger.info("result_consumer.stopped")


async def _process_event(event: dict):
    event_type = event.get("event_type")
    result = event.get("result", {})
    job_id = result.get("job_id")
    user_id = result.get("user_id")

    if not job_id:
        return

    log = logger.bind(job_id=job_id, user_id=user_id, event_type=event_type)
    db = Database.get_db()
    if db is None:
        log.error("result_consumer.db_not_connected")
        return

    try:
        if event_type == "JOB_COMPLETED":
            log.info("result_consumer.job_completed_event")
            await db.ocr_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.utcnow(),
                        "pages": result.get("pages", []),
                        "confidence": result.get("confidence", 1.0),
                        "model_used": result.get("model_used", ""),
                        "result_key": result.get("result_key", ""),
                    }
                },
            )
        elif event_type == "JOB_FAILED":
            log.warn(
                "result_consumer.job_failed_event",
                error=result.get("error_message"),
            )
            await db.ocr_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "completed_at": datetime.utcnow(),
                        "error": result.get("error_message", "Unknown error"),
                    }
                },
            )
    except Exception as e:
        log.error("result_consumer.process_failed", error=str(e))
