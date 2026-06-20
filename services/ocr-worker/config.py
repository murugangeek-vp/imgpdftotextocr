"""
OCR Worker Configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    APP_ENV: str = "local"
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "ocr-worker"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_OCR_PENDING: str = "ocr.jobs.pending"
    KAFKA_TOPIC_OCR_COMPLETED: str = "ocr.jobs.completed"
    KAFKA_TOPIC_OCR_FAILED: str = "ocr.jobs.failed"
    KAFKA_CONSUMER_GROUP: str = "ocr-workers"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Triton Inference Server
    TRITON_GRPC_URL: str = "triton:8001"
    TRITON_HTTP_URL: str = "http://triton:8000"
    TRITON_MODEL_DETECTION: str = "ocr_detection"
    TRITON_MODEL_RECOGNITION: str = "ocr_recognition"
    TRITON_MODEL_ENSEMBLE: str = "ocr_ensemble"

    # Storage (S3 / MinIO)
    STORAGE_PROVIDER: str = "minio"
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_UPLOADS: str = "ocr-uploads"
    MINIO_BUCKET_RESULTS: str = "ocr-results"
    MINIO_USE_SSL: bool = False

    # Quota Service
    QUOTA_SERVICE_URL: str = "http://quota-service:8003"

    # Worker Concurrency
    WORKER_CONCURRENCY: int = 4


settings = Settings()
