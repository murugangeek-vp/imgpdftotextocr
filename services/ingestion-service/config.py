"""
Ingestion Service Configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    APP_ENV: str = "local"
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "ingestion-service"

    # Services
    QUOTA_SERVICE_URL: str = "http://quota-service:8003"
    WEB_APP_URL: str = "http://web-app:3000"

    # Limits
    MAX_PAGES_PER_PDF: int = 5

    # Storage (MinIO / S3)
    STORAGE_PROVIDER: str = "minio"
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_UPLOADS: str = "ocr-uploads"
    MINIO_BUCKET_RESULTS: str = "ocr-results"
    MINIO_USE_SSL: bool = False
    PRESIGNED_URL_EXPIRY_SECONDS: int = 900

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_OCR_PENDING: str = "ocr.jobs.pending"

    # MongoDB
    MONGODB_URI: str = "mongodb://admin:password@mongodb:27017/ocrplatform?authSource=admin"
    MONGODB_DB: str = "ocrplatform"

    # ClamAV
    CLAMAV_HOST: str = "clamav"
    CLAMAV_PORT: int = 3310


settings = Settings()
