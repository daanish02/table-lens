"""Idempotent, ordered SQL migration runner — plain .sql files in
migrations/, tracked in a schema_migrations table so re-running only
applies what's new."""

from pathlib import Path
from sqlalchemy import text, Engine

from app.db import queries
from app.utils.logger import get_logger

log = get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations(engine: Engine) -> None:
    """Applies every migration in MIGRATIONS_DIR not yet recorded as
    applied, in filename order. Safe to call on every startup."""
    with engine.connect() as conn:
        conn.execute(text(queries.load("create_schema_migrations_table")))
        conn.commit()
        applied = set(conn.execute(text(queries.load("list_applied_migrations"))).scalars().all())

    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            continue
        log.info(f"applying migration: {path.name}")
        with engine.connect() as conn:
            conn.execute(text(path.read_text()))
            conn.execute(text(queries.load("record_migration")), {"filename": path.name})
            conn.commit()
