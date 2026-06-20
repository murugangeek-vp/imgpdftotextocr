"""
Kafka Producer Client
"""
import json
import asyncio
from kafka import KafkaProducer
import structlog
from config import settings

logger = structlog.get_logger()


class KafkaProducerClient:
    _producer = None

    @classmethod
    async def init(cls):
        def _connect():
            return KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=5,
            )
        cls._producer = await asyncio.to_thread(_connect)
        logger.info("kafka.producer_initialized")

    @classmethod
    async def send(cls, topic: str, key: str, value: dict):
        if cls._producer is None:
            raise RuntimeError("Kafka producer is not initialized.")
        def _send():
            future = cls._producer.send(topic, key=key, value=value)
            future.get(timeout=10)
        await asyncio.to_thread(_send)

    @classmethod
    async def close(cls):
        if cls._producer:
            await asyncio.to_thread(cls._producer.close)
            cls._producer = None
            logger.info("kafka.producer_closed")
