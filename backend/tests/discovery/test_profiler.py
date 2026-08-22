import os
import pytest

from app.discovery.profiler import profile_table, ColumnProfile
from app.discovery.introspect import get_schema_snapshot
from app.db.connection import get_engine

requires_db = pytest.mark.skipif(
    not os.getenv("SUPABASE_DB_URL"), reason="SUPABASE_DB_URL not set"
)


@requires_db
def test_profile_table_covers_every_column():
    engine = get_engine()
    tables = get_schema_snapshot(engine, "demo")
    products = next(t for t in tables if t.name == "products")
    profiles = profile_table(engine, "demo", products)
    assert set(profiles.keys()) == {c.name for c in products.columns}


@requires_db
def test_profile_reports_null_rate_and_distinct_count():
    engine = get_engine()
    tables = get_schema_snapshot(engine, "demo")
    products = next(t for t in tables if t.name == "products")
    profiles = profile_table(engine, "demo", products)
    any_profile = next(iter(profiles.values()))
    assert isinstance(any_profile, ColumnProfile)
    assert any_profile.null_rate >= 0.0
    assert any_profile.distinct_count >= 0
