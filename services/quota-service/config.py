"""
Quota Service Configuration
All settings loaded from environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    APP_ENV: str = "local"
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "quota-service"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # MongoDB
    MONGODB_URI: str = "mongodb://admin:password@mongodb:27017/ocrplatform?authSource=admin"
    MONGODB_DB: str = "ocrplatform"

    # Tier config cache TTL (seconds) — hot-reload without restart
    TIER_CONFIG_CACHE_TTL_SECONDS: int = 60

    # Observability
    OTLP_ENDPOINT: str = "http://jaeger:4317"

    # gRPC
    QUOTA_SERVICE_GRPC_PORT: int = 50053


settings = Settings()
