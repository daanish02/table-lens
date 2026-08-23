import os
import pytest

from app.discovery.relationships import infer_relationships, InferredRelationship
from app.discovery.introspect import get_schema_snapshot
from app.db.connection import get_engine

requires_db = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="live network test — set RUN_LIVE_TESTS=1 to run",
)


@requires_db
def test_infer_relationships_finds_undeclared_fk_like_columns():
    engine = get_engine()
    tables = get_schema_snapshot(engine, "demo")
    relationships = infer_relationships(engine, "demo", tables)
    assert all(isinstance(r, InferredRelationship) for r in relationships)
    assert all(0.0 <= r.overlap_pct <= 1.0 for r in relationships)


def test_infer_relationships_skips_columns_that_already_have_declared_fk():
    from app.discovery.introspect import TableInfo, ColumnInfo

    tables = [
        TableInfo(name="claims", columns=[
            ColumnInfo(name="customer_id", data_type="integer", is_pk=False, is_fk=True, fk_table="customers", fk_column="customer_id"),
        ]),
    ]
    from app.discovery.relationships import _candidate_columns
    candidates = _candidate_columns(tables)
    assert candidates == []
