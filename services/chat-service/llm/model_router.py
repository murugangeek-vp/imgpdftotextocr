"""
Smart LLM Model Router
Routes chat requests to the appropriate LLM based on:
- User tier (free → Ollama, paid → OpenAI)
- OpenAI API health (fallback to Ollama on error/rate-limit)
- Request complexity heuristic
All routing decisions are traced in Langfuse.
"""
import asyncio
import time
from enum import Enum
from typing import Optional

import httpx
import structlog
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

from config import settings

logger = structlog.get_logger()


class LLMProvider(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"


# OpenAI health state (circuit breaker)
_openai_healthy = True
_openai_last_failure: Optional[float] = None
OPENAI_RECOVERY_SECONDS = 60  # Try OpenAI again after 60s


class ModelRouter:
    """
    Routes requests to OpenAI GPT-4o or Ollama Llama 3.2:1b.

    Routing Logic:
    1. Free tier users → Ollama (cost saving)
    2. Paid users + OpenAI healthy → OpenAI GPT-4o
    3. Paid users + OpenAI down → Ollama fallback (with alert)
    4. All routing decisions logged to Langfuse
    """

    @classmethod
    def select_provider(cls, tier: str) -> LLMProvider:
        global _openai_healthy, _openai_last_failure

        # Check if OpenAI has recovered from failure
        if not _openai_healthy and _openai_last_failure:
            if time.time() - _openai_last_failure > OPENAI_RECOVERY_SECONDS:
                _openai_healthy = True
                logger.info("model_router.openai_recovered")

        # Free tier → always Ollama to save cost
        if tier == "free":
            logger.info("model_router.selected", provider="ollama", reason="free_tier")
            return LLMProvider.OLLAMA

        # Paid tier
        if _openai_healthy:
            logger.info("model_router.selected", provider="openai", reason="paid_tier_healthy")
            return LLMProvider.OPENAI
        else:
            logger.warning("model_router.fallback", reason="openai_unhealthy", fallback="ollama")
            return LLMProvider.OLLAMA

    @classmethod
    def mark_openai_failure(cls):
        global _openai_healthy, _openai_last_failure
        _openai_healthy = False
        _openai_last_failure = time.time()
        logger.error("model_router.openai_marked_unhealthy")

    @classmethod
    def mark_openai_success(cls):
        global _openai_healthy
        _openai_healthy = True
