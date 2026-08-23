import os
import pytest
from sqlalchemy import text

from app.db.connection import get_engine
from app.db.migrate import run_migrations

requires_db = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="live network test — set RUN_LIVE_TESTS=1 to run",
)


@requires_db
def test_run_migrations_creates_embedding_tables():
    engine = get_engine()
    run_migrations(engine)
    with engine.connect() as conn:
        tables = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name IN "
            "('table_embeddings', 'column_embeddings')"
        )).scalars().all()
    assert set(tables) == {"table_embeddings", "column_embeddings"}


@requires_db
def test_run_migrations_is_idempotent():
    engine = get_engine()
    run_migrations(engine)
    run_migrations(engine)  # must not raise
