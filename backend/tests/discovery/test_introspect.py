import os
import pytest

from app.discovery.introspect import get_schema_snapshot, to_hashable
from app.db.connection import get_engine

requires_db = pytest.mark.skipif(
    not os.getenv("SUPABASE_DB_URL"), reason="SUPABASE_DB_URL not set"
)


@requires_db
def test_get_schema_snapshot_finds_demo_tables():
    engine = get_engine()
    tables = get_schema_snapshot(engine, "demo")
    names = {t.name for t in tables}
    assert "products" in names or "financial_periods" in names


@requires_db
def test_products_table_has_expected_columns():
    engine = get_engine()
    tables = get_schema_snapshot(engine, "demo")
    products = next((t for t in tables if t.name == "products"), None)
    assert products is not None
    col_names = {c.name for c in products.columns}
    assert "product_id" in col_names or len(col_names) > 0


def test_to_hashable_produces_sorted_dicts():
    from app.discovery.introspect import TableInfo, ColumnInfo

    tables = [
        TableInfo(name="b", columns=[ColumnInfo(name="id", data_type="int", is_pk=True, is_fk=False, fk_table=None, fk_column=None)]),
        TableInfo(name="a", columns=[ColumnInfo(name="id", data_type="int", is_pk=True, is_fk=False, fk_table=None, fk_column=None)]),
    ]
    hashable = to_hashable(tables)
    assert hashable[0]["table"] in {"a", "b"}
    assert all("columns" in t for t in hashable)
