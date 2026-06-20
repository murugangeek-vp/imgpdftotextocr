"""
Notification Service Configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    APP_ENV: str = "local"
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "notification-service"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_OCR_COMPLETED: str = "ocr.jobs.completed"
    KAFKA_TOPIC_OCR_FAILED: str = "ocr.jobs.failed"


settings = Settings()
