import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from src.config import settings

logger = logging.getLogger(__name__)


def get_llm() -> ChatOpenAI:
    """
    Factory function returning configured ChatOpenAI model.
    Prioritizes Google Gemini (via OpenAI-compatible endpoint), then Groq, then OpenAI.
    """
    if settings.GOOGLE_API_KEY:
        logger.info(f"Using Google Gemini LLM ({settings.GEMINI_MODEL}) via OpenAI-compatible endpoint")
        return ChatOpenAI(
            model=settings.GEMINI_MODEL,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=settings.GOOGLE_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
        )
    elif settings.GROQ_API_KEY:
        logger.info(f"Using Groq LLM ({settings.GROQ_MODEL})")
        return ChatOpenAI(
            model=settings.GROQ_MODEL,
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.GROQ_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
        )
    elif settings.OPENAI_API_KEY:
        logger.info(f"Using OpenAI LLM ({settings.OPENAI_MODEL})")
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
        )
    else:
        raise ValueError(
            "No LLM API key configured! Please provide GOOGLE_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY in .env"
        )
