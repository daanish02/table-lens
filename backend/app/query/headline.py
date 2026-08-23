"""Second LLM call after execution, with actual result data — deliberately
separate from SQL generation (see docs/PRD.md, Key Architectural Decisions
#3)."""

from app.query import prompts
from app.query.llm import get_llm
from app.utils.logger import get_logger

__all__ = ["generate_headline"]

log = get_logger(__name__)

SAMPLE_SIZE = 20


def generate_headline(question: str, sql: str, result: dict) -> str:
    """One-line plain-English summary of an already-executed query's
    result, from a sample of rows (not the full result)."""
    sample = result["rows"][:SAMPLE_SIZE]
    prompt = prompts.load("headline").format(
        question=question,
        sql=sql,
        sample_size=len(sample),
        total_rows=result["row_count"],
        columns=", ".join(result["columns"]),
        sample_rows="\n".join(str(row) for row in sample),
    )
    log.info("generating headline")
    response = get_llm().invoke(prompt)
    return response.content
