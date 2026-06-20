"""
Auth Service Configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    APP_ENV: str = "local"
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "auth-service"

    SECRET_KEY: str = "change-me-in-production-min-32-chars"

    # Keycloak (Local Auth Provider)
    KEYCLOAK_URL: str = "http://keycloak:8080"
    KEYCLOAK_REALM: str = "ocr-platform"
    KEYCLOAK_CLIENT_ID: str = "ocr-api"
    KEYCLOAK_CLIENT_SECRET: str = "change-me"

    # Database
    MONGODB_URI: str = "mongodb://admin:password@mongodb:27017/ocrplatform?authSource=admin"
    MONGODB_DB: str = "ocrplatform"

    # Redis (For blacklisted tokens)
    REDIS_URL: str = "redis://redis:6379/0"

    # Observability
    OTLP_ENDPOINT: str = "http://jaeger:4317"

    # gRPC Port
    AUTH_SERVICE_GRPC_PORT: int = 50051


settings = Settings()
