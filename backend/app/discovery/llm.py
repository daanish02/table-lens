from functools import lru_cache
from langchain_openai import ChatOpenAI

from app.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL, LLM_MAX_RETRIES, LLM_MAX_TOKENS
from app.discovery import prompts
from app.discovery.introspect import TableInfo, ColumnInfo
from app.utils.logger import get_logger

log = get_logger(__name__)


@lru_cache
def _get_llm():
    # OpenRouter exposes an OpenAI-compatible endpoint — ChatOpenAI works
    # unmodified against it via base_url. Model swap = change LLM_MODEL only.
    # timeout=60: without it a single stuck call can hang for the SDK's own
    # (effectively unbounded) default — bad anywhere, worse here since a
    # discovery run makes hundreds of these calls unattended.
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        max_retries=LLM_MAX_RETRIES,
        max_tokens=LLM_MAX_TOKENS,
        timeout=60,
        temperature=0,
    )


def describe_table(table: TableInfo, profiles: dict, sibling_tables: list[str] | None = None) -> str:
    col_summary = ", ".join(
        f"{c.name} ({c.data_type}, null_rate={profiles[c.name].null_rate:.2f})"
        for c in table.columns if c.name in profiles
    )
    prompt = prompts.load("table_description").format(
        table_name=table.name,
        columns=col_summary,
        sibling_tables=", ".join(sibling_tables or []),
    )
    log.info(f"describing table: {table.name}")
    response = _get_llm().invoke(prompt)
    return response.content


def describe_column(table_name: str, column: ColumnInfo, profile) -> str:
    stats = f"null_rate={profile.null_rate:.2f}, distinct={profile.distinct_count}"
    if profile.mean_value is not None:
        stats += f", mean={profile.mean_value}"
    if profile.top_values:
        stats += f", top_values={profile.top_values[:5]}"

    prompt = prompts.load("column_description").format(
        table_name=table_name,
        column_name=column.name,
        data_type=column.data_type,
        stats=stats,
    )
    log.info(f"describing column: {table_name}.{column.name}")
    response = _get_llm().invoke(prompt)
    return response.content
