"""Executes agent-generated SQL against the read-only engine. sql_guard has
already validated the statement is a single SELECT with a LIMIT before this
is ever called."""

from sqlalchemy import text, Engine

from app.utils.logger import get_logger

__all__ = ["run_query"]

log = get_logger(__name__)

STATEMENT_TIMEOUT_MS = 15_000  # belt-and-suspenders against a pathological query slipping past LIMIT (e.g. an expensive join/aggregate)


def run_query(engine: Engine, sql: str) -> dict:
    """Runs one already-validated SELECT, capped by STATEMENT_TIMEOUT_MS."""
    log.info(f"executing: {sql}")
    with engine.connect() as conn:
        conn.execute(text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}"))
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result]
    log.info(f"executed: {len(rows)} rows returned")
    return {"columns": columns, "rows": rows, "row_count": len(rows)}
