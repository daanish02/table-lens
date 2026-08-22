from functools import lru_cache
from langchain_openai import ChatOpenAI

from app.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL, LLM_MAX_RETRIES
from app.discovery.introspect import TableInfo, ColumnInfo
from app.logging.logger import get_logger

log = get_logger(__name__)


@lru_cache
def _get_llm():
    # OpenRouter exposes an OpenAI-compatible endpoint — ChatOpenAI works
    # unmodified against it via base_url. Model swap = change LLM_MODEL only.
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        max_retries=LLM_MAX_RETRIES,
        temperature=0,
    )


def describe_table(table: TableInfo, profiles: dict) -> str:
    col_summary = ", ".join(
        f"{c.name} ({c.data_type}, null_rate={profiles[c.name].null_rate:.2f})"
        for c in table.columns if c.name in profiles
    )
    prompt = (
        f"You are documenting a database table for an analyst who has never seen it.\n"
        f"Table: {table.name}\n"
        f"Columns: {col_summary}\n\n"
        f"Write 1-3 sentences: what this table is for, when to use it, and any "
        f"gotcha (e.g. null behavior, denormalization) an analyst should know."
    )
    log.info("llm.describe_table", table=table.name)
    response = _get_llm().invoke(prompt)
    return response.content


def describe_column(table_name: str, column: ColumnInfo, profile) -> str:
    stats = f"null_rate={profile.null_rate:.2f}, distinct={profile.distinct_count}"
    if profile.mean_value is not None:
        stats += f", mean={profile.mean_value}"
    if profile.top_values:
        stats += f", top_values={profile.top_values[:5]}"

    prompt = (
        f"You are documenting a database column for an analyst who has never seen it.\n"
        f"Table: {table_name}, Column: {column.name} ({column.data_type})\n"
        f"Stats: {stats}\n\n"
        f"Write 1 sentence: what this column represents, when to use it, and any "
        f"gotcha (nulls, encoding) an analyst should know."
    )
    log.info("llm.describe_column", table=table_name, column=column.name)
    response = _get_llm().invoke(prompt)
    return response.content
