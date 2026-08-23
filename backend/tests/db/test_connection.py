import os
import pytest
from sqlalchemy import text

from app.db.connection import get_engine

requires_db = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="live network test — set RUN_LIVE_TESTS=1 to run",
)


@requires_db
def test_get_engine_connects_and_runs_select_1():
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@requires_db
def test_readonly_engine_rejects_write():
    engine = get_engine(readonly=True)
    with engine.connect() as conn:
        with pytest.raises(Exception):
            conn.execute(text("CREATE TABLE demo.__should_fail (id INT)"))
            conn.commit()
