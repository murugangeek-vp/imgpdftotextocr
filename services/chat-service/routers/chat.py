"""
Chat router — LLM chat over OCR-extracted text.
Routes to OpenAI GPT-4o or Ollama based on user tier and API health.
All calls traced in Langfuse.
"""
import uuid
from datetime import datetime
from typing import List, Optional

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from openai import AsyncOpenAI
from langfuse import Langfuse

from config import settings
from llm.model_router import ModelRouter, LLMProvider

logger = structlog.get_logger()
router = APIRouter()

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    job_id: str
    user_id: str
    tier: str
    messages: List[ChatMessage]
    ocr_context: Optional[str] = None  # Extracted OCR text as context


class ChatResponse(BaseModel):
    message: str
    model_used: str
    provider: str
    trace_id: str


SYSTEM_PROMPT = """You are an expert document analysis assistant.
You have been provided with OCR-extracted text from a document.
Help the user understand, summarize, translate, or query this content.
Always be accurate and cite specific parts of the text when answering.
If the OCR text has errors, intelligently interpret what the text likely says.
Supported languages: English and all 22 Indian scheduled languages."""


@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    """
    Chat with OCR-extracted text using smart LLM routing.
    - Free tier: Ollama Llama 3.2:1b (cost-free)
    - Paid tier: OpenAI GPT-4o (best quality)
    - Auto-fallback to Ollama if OpenAI is unavailable
    """
    trace_id = str(uuid.uuid4())
    langfuse: Langfuse = request.app.state.langfuse

    provider = ModelRouter.select_provider(req.tier)

    # Build messages with OCR context
    system_msg = SYSTEM_PROMPT
    if req.ocr_context:
        system_msg += f"\n\nOCR EXTRACTED TEXT:\n---\n{req.ocr_context[:4000]}\n---"

    messages = [{"role": "system", "content": system_msg}]
    messages += [{"role": m.role, "content": m.content} for m in req.messages]

    # Create Langfuse trace
    trace = langfuse.trace(
        name="chat",
        id=trace_id,
        user_id=req.user_id,
        metadata={"job_id": req.job_id, "tier": req.tier, "provider": provider},
    )

    try:
        if provider == LLMProvider.OPENAI:
            response_text, model_name = await _call_openai(messages, trace)
            ModelRouter.mark_openai_success()
        else:
            response_text, model_name = await _call_ollama(messages, trace)

    except Exception as e:
        if provider == LLMProvider.OPENAI:
            logger.warning("chat.openai_failed_falling_back", error=str(e))
            ModelRouter.mark_openai_failure()
            try:
                response_text, model_name = await _call_ollama(messages, trace)
                provider = LLMProvider.OLLAMA
            except Exception as e2:
                raise HTTPException(status_code=503, detail=f"LLM unavailable: {str(e2)}")
        else:
            raise HTTPException(status_code=503, detail=f"LLM unavailable: {str(e)}")

    # Score with Langfuse (flush async)
    trace.generation(
        name="completion",
        model=model_name,
        input=messages,
        output=response_text,
    )

    return ChatResponse(
        message=response_text,
        model_used=model_name,
        provider=provider,
        trace_id=trace_id,
    )


async def _call_openai(messages: list, trace) -> tuple[str, str]:
    """Call OpenAI GPT-4o."""
    response = await openai_client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        max_tokens=settings.OPENAI_MAX_TOKENS,
        temperature=0.3,
    )
    text = response.choices[0].message.content
    return text, settings.OPENAI_MODEL


async def _call_ollama(messages: list, trace) -> tuple[str, str]:
    """Call local Ollama Llama 3.2:1b."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()
        text = data["message"]["content"]
    return text, settings.OLLAMA_MODEL
