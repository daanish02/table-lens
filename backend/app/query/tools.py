"""LangChain tool definitions the query agent calls — table/column
retrieval and SQL execution. Bound to a specific engine via a factory
(build_tools) rather than a module-level singleton, since the agent
should always run against the read-only engine, never whatever engine
happens to be default."""

import json
from langchain_core.tools import tool
from sqlalchemy import Engine

from app.query import retrieval, sql_guard, execute
from app.utils.logger import get_logger

__all__ = ["build_tools"]

log = get_logger(__name__)


def build_tools(engine: Engine) -> list:
    @tool
    def search_tables(query: str) -> str:
        """Semantic search over available database tables. Returns up to 8
        relevant tables with their descriptions, row counts, and column
        counts. Call this first to find which tables are relevant."""
        log.info(f"tool call: search_tables({query!r})")
        results = retrieval.search_tables(engine, query, top_k=8)
        return json.dumps(results, default=str)

    @tool
    def search_columns(table_name: str, query: str) -> str:
        """Semantic search over the columns of one specific table (must be
        a table_name already returned by search_tables). Returns up to 20
        relevant columns with descriptions and profile stats (null rate,
        distinct count, min/max, top values, histogram)."""
        log.info(f"tool call: search_columns({table_name!r}, {query!r})")
        results = retrieval.search_columns(engine, table_name, query, top_k=20)
        return json.dumps(results, default=str)

    @tool
    def run_sql(sql: str) -> str:
        """Execute a read-only PostgreSQL SELECT query and return the
        results. The query must be valid Postgres 15, SELECT-only (CTEs
        are fine), and should include a LIMIT (one is added automatically
        if missing). On error, the error message is returned instead of
        results — fix the SQL and call this again."""
        log.info(f"tool call: run_sql({sql!r})")
        try:
            normalized = sql_guard.validate_and_normalize(sql)
        except sql_guard.SQLValidationError as e:
            log.warning(f"run_sql rejected: {e}")
            return json.dumps({"error": str(e)})
        try:
            result = execute.run_query(engine, normalized)
        except Exception as e:
            log.error(f"run_sql execution failed: {e}")
            return json.dumps({"error": str(e), "sql": normalized})
        return json.dumps({"sql": normalized, **result}, default=str)

    return [search_tables, search_columns, run_sql]
