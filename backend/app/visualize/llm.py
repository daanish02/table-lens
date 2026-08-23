"""Shared ChatOpenAI client for the visualize agent's single structured
chart-generation call."""

from functools import lru_cache
from langchain_openai import ChatOpenAI

from app.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL, LLM_MAX_RETRIES

__all__ = ["get_llm"]

# A full ECharts option — axis config, per-series styling, and every row's
# data point — is bulkier than the SQL the query agent emits, and deepseek
# spends a variable chunk of its budget on internal reasoning before any
# output text. A cap sized for SQL (query agent's 8000) truncates mid-JSON
# on charts with many categories/series, which then fails validation and
# forces a slow retry — more headroom here avoids paying for that twice.
VISUALIZE_LLM_MAX_TOKENS = 16000

# Without an explicit cap, a stuck/slow provider response can hang for the
# SDK's own default (effectively unbounded) before generate_chart's retry
# loop ever gets a chance to fail and try again — with MAX_ATTEMPTS=3 that
# multiplies into a multi-minute wait for one chart. 60s is generous for a
# single completion but still fails fast enough to make the 3-attempt retry
# loop's worst case bounded and reasonable.
VISUALIZE_LLM_TIMEOUT_SECONDS = 120


@lru_cache
def get_llm() -> ChatOpenAI:
    """Cached ChatOpenAI client for the visualize agent."""
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        max_retries=LLM_MAX_RETRIES,
        max_tokens=VISUALIZE_LLM_MAX_TOKENS,
        timeout=VISUALIZE_LLM_TIMEOUT_SECONDS,
        temperature=0,
    )
