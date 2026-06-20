"""
Result Service Configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    APP_ENV: str = "local"
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "result-service"

    # Database
    MONGODB_URI: str = "mongodb://admin:password@mongodb:27017/ocrplatform?authSource=admin"
    MONGODB_DB: str = "ocrplatform"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_OCR_COMPLETED: str = "ocr.jobs.completed"
    KAFKA_TOPIC_OCR_FAILED: str = "ocr.jobs.failed"
    KAFKA_CONSUMER_GROUP: str = "result-service-group"

    # Observability
    OTLP_ENDPOINT: str = "http://jaeger:4317"


settings = Settings()
