"""
Result Publisher for OCR Worker.
Publishes job completion/failure events to Kafka.
"""
import json
import asyncio
from datetime import datetime
from kafka import KafkaProducer
import structlog
from config import settings

logger = structlog.get_logger()


class ResultPublisher:
    _producer = None

    @classmethod
    def _get_producer(cls):
        if cls._producer is None:
            cls._producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=5,
            )
        return cls._producer

    @classmethod
    async def publish_success(
        cls,
        job_id: str,
        user_id: str,
        session_id: str,
        page_results: list,
        result_key: str,
    ):
        producer = cls._get_producer()
        now = int(datetime.utcnow().timestamp())

        # Calculate average confidence
        confidences = [p.get("confidence", 0.0) for p in page_results]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 1.0

        event = {
            "event_type": "JOB_COMPLETED",
            "result": {
                "job_id": job_id,
                "user_id": user_id,
                "status": 3,  # JOB_STATUS_COMPLETED
                "pages": page_results,
                "error_message": "",
                "completed_at": now,
                "confidence": avg_confidence,
                "model_used": settings.TRITON_MODEL_ENSEMBLE,
                "result_key": result_key,
                "session_id": session_id,
            },
            "timestamp": now,
        }

        def _send():
            future = producer.send(
                settings.KAFKA_TOPIC_OCR_COMPLETED,
                key=user_id,
                value=event,
            )
            future.get(timeout=10)

        await asyncio.to_thread(_send)
        logger.info(
            "kafka.result_published",
            topic=settings.KAFKA_TOPIC_OCR_COMPLETED,
            job_id=job_id,
        )

    @classmethod
    async def publish_failure(cls, job_id: str, user_id: str, error: str):
        producer = cls._get_producer()
        now = int(datetime.utcnow().timestamp())

        event = {
            "event_type": "JOB_FAILED",
            "result": {
                "job_id": job_id,
                "user_id": user_id,
                "status": 4,  # JOB_STATUS_FAILED
                "pages": [],
                "error_message": error,
                "completed_at": now,
                "confidence": 0.0,
                "model_used": "",
            },
            "timestamp": now,
        }

        def _send():
            future = producer.send(
                settings.KAFKA_TOPIC_OCR_FAILED,
                key=user_id,
                value=event,
            )
            future.get(timeout=10)

        await asyncio.to_thread(_send)
        logger.info(
            "kafka.result_published",
            topic=settings.KAFKA_TOPIC_OCR_FAILED,
            job_id=job_id,
        )
