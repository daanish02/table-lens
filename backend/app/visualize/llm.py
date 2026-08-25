"""Shared ChatOpenAI client for the visualize agent's single structured
chart-generation call."""

from functools import lru_cache
from langchain_openai import ChatOpenAI

from app.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, VISUALIZE_LLM_MODEL, LLM_MAX_RETRIES

__all__ = ["get_llm"]

# The visualize agent now emits a compact descriptor (~20 fields, no data
# values) rather than a full ECharts option with every row encoded. The
# LLM's output is a small JSON object — 1000 tokens is generous headroom.
VISUALIZE_LLM_MAX_TOKENS = 1000

# Fast non-reasoning model + small output = quick completions; 30s is still
# a safe ceiling for any stuck provider response.
VISUALIZE_LLM_TIMEOUT_SECONDS = 30


@lru_cache
def get_llm() -> ChatOpenAI:
    """Cached ChatOpenAI client for the visualize agent."""
    return ChatOpenAI(
        model=VISUALIZE_LLM_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        max_retries=LLM_MAX_RETRIES,
        max_tokens=VISUALIZE_LLM_MAX_TOKENS,
        timeout=VISUALIZE_LLM_TIMEOUT_SECONDS,
        temperature=0,
    )
