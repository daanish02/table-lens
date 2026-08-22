from app.discovery.idempotency import schema_hash


def test_schema_hash_is_stable_for_same_input():
    snapshot = [{"table": "customers", "columns": ["id", "name"]}]
    assert schema_hash(snapshot) == schema_hash(snapshot)


def test_schema_hash_changes_when_schema_changes():
    a = [{"table": "customers", "columns": ["id", "name"]}]
    b = [{"table": "customers", "columns": ["id", "name", "email"]}]
    assert schema_hash(a) != schema_hash(b)


def test_schema_hash_is_order_independent():
    a = [{"table": "customers", "columns": ["id", "name"]}, {"table": "claims", "columns": ["id"]}]
    b = [{"table": "claims", "columns": ["id"]}, {"table": "customers", "columns": ["id", "name"]}]
    assert schema_hash(a) == schema_hash(b)
