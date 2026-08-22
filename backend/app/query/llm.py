from functools import lru_cache
from langchain_openai import ChatOpenAI

from app.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL, LLM_MAX_RETRIES

__all__ = ["get_llm"]

# The query agent reasons over tool results (retrieved schema, SQL errors on
# retry) and can emit fairly long SQL for wide tables — more headroom than
# discovery's single-field description calls.
QUERY_LLM_MAX_TOKENS = 8000


@lru_cache
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        max_retries=LLM_MAX_RETRIES,
        max_tokens=QUERY_LLM_MAX_TOKENS,
        temperature=0,
    )
