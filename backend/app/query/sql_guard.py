"""Read-only enforcement at the code level, not just prompt instructions
(see docs/PRD.md, Key Architectural Decisions #4) — the LLM's SQL is
parsed and validated with sqlglot before it ever reaches the database."""

import sqlglot
from sqlglot import exp

__all__ = ["SQLValidationError", "validate_and_normalize"]

DIALECT = "postgres"
DEFAULT_LIMIT = 1000


class SQLValidationError(ValueError):
    pass


def validate_and_normalize(sql: str, default_limit: int = DEFAULT_LIMIT) -> str:
    """Raises SQLValidationError for anything that isn't a single read-only
    SELECT (CTEs included — sqlglot represents `WITH ... SELECT` as an
    exp.Select with a `with` clause). Adds a LIMIT if the query doesn't
    already have one."""
    try:
        statements = [s for s in sqlglot.parse(sql, read=DIALECT) if s is not None]
    except Exception as e:
        raise SQLValidationError(f"could not parse SQL: {e}")

    if len(statements) != 1:
        raise SQLValidationError(f"exactly one SQL statement is required, got {len(statements)}")

    stmt = statements[0]
    if not isinstance(stmt, exp.Select):
        raise SQLValidationError(f"only SELECT statements are allowed, got {type(stmt).__name__}")

    if not stmt.args.get("limit"):
        stmt = stmt.limit(default_limit)

    return stmt.sql(dialect=DIALECT)
