"""Read-only enforcement at the code level, not just prompt instructions
(see docs/PRD.md, Key Architectural Decisions #4) — the LLM's SQL is
parsed and validated with sqlglot before it ever reaches the database.

Note: the real read-only boundary is the DB role this runs under
(SUPABASE_DB_URL_READONLY — see app/db/connection.py); this parser-level
check is defense-in-depth on top of that, not a substitute for it.
Postgres allows calling volatile/side-effecting functions from inside a
plain SELECT (e.g. SELECT pg_sleep(60)), so "parses as a single SELECT"
alone doesn't guarantee harmlessness even if every write path were somehow
still open — see BLOCKED_FUNCTIONS below."""

import sqlglot
from sqlglot import exp

__all__ = ["SQLValidationError", "validate_and_normalize"]

DIALECT = "postgres"
DEFAULT_LIMIT = 1000

# Callable from inside a SELECT, but not read-only in effect: session/DoS
# (pg_sleep, pg_terminate_backend), sequence/config mutation (setval,
# set_config), locking (advisory locks can starve other connections),
# large-object and dblink functions (file/network I/O, potential
# exfiltration path). Not exhaustive — a blocklist never is — but closes
# off the obvious, known-dangerous ones a prompt-injected or directly
# submitted query could otherwise reach.
BLOCKED_FUNCTIONS = {
    "pg_sleep", "pg_sleep_for", "pg_sleep_until",
    "pg_terminate_backend", "pg_cancel_backend",
    "set_config", "setval", "nextval",
    "pg_advisory_lock", "pg_advisory_lock_shared",
    "pg_advisory_xact_lock", "pg_advisory_xact_lock_shared",
    "pg_advisory_unlock", "pg_advisory_unlock_all", "pg_advisory_unlock_shared",
    "lo_export", "lo_import", "lo_creat", "lo_create", "lo_unlink",
    "dblink", "dblink_connect", "dblink_exec", "dblink_connect_u",
}


class SQLValidationError(ValueError):
    pass


def _func_name(node: exp.Func) -> str | None:
    this = node.args.get("this")
    if isinstance(this, str):
        return this.lower()
    try:
        name = node.sql_name()
    except Exception:
        name = None
    return name.lower() if isinstance(name, str) and name else None


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

    for func_node in stmt.find_all(exp.Func):
        name = _func_name(func_node)
        if name in BLOCKED_FUNCTIONS:
            raise SQLValidationError(f"function not allowed: {name}()")

    if not stmt.args.get("limit"):
        stmt = stmt.limit(default_limit)

    # pretty=True gives readable multi-line SQL — this is the version both
    # executed and shown to the user, so what runs is exactly what's shown.
    return stmt.sql(dialect=DIALECT, pretty=True)
