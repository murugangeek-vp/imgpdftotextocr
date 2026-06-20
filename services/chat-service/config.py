"""
Chat Service Configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    APP_ENV: str = "local"
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "chat-service"

    # OpenAI
    OPENAI_API_KEY: str = "sk-your-key-here"
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MAX_TOKENS: int = 2000

    # Ollama
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "llama3.2:1b"

    # Langfuse (LLM Observability)
    LANGFUSE_HOST: str = "http://langfuse:3000"
    LANGFUSE_PUBLIC_KEY: str = "pk-lf-local-change-me"
    LANGFUSE_SECRET_KEY: str = "sk-lf-local-change-me"

    # Database
    MONGODB_URI: str = "mongodb://admin:password@mongodb:27017/ocrplatform?authSource=admin"
    MONGODB_DB: str = "ocrplatform"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Observability
    OTLP_ENDPOINT: str = "http://jaeger:4317"


settings = Settings()
