import pytest

from app.query.sql_guard import validate_and_normalize, SQLValidationError


def test_accepts_plain_select():
    sql = validate_and_normalize("SELECT a, b FROM demo.claims WHERE a > 1")
    assert "SELECT" in sql
    assert "LIMIT 1000" in sql


def test_accepts_cte():
    sql = validate_and_normalize("WITH x AS (SELECT 1 AS a) SELECT * FROM x")
    assert "WITH" in sql
    assert "LIMIT 1000" in sql


def test_preserves_existing_limit():
    sql = validate_and_normalize("SELECT a FROM demo.claims LIMIT 50")
    assert sql.count("LIMIT") == 1
    assert "LIMIT 50" in sql


def test_rejects_ddl():
    with pytest.raises(SQLValidationError):
        validate_and_normalize("DROP TABLE demo.claims")


def test_rejects_insert():
    with pytest.raises(SQLValidationError):
        validate_and_normalize("INSERT INTO demo.claims (id) VALUES (1)")


def test_rejects_delete():
    with pytest.raises(SQLValidationError):
        validate_and_normalize("DELETE FROM demo.claims WHERE id = 1")


def test_rejects_multiple_statements():
    with pytest.raises(SQLValidationError):
        validate_and_normalize("SELECT 1; DROP TABLE demo.claims")


def test_rejects_unparseable_sql():
    with pytest.raises(SQLValidationError):
        validate_and_normalize("SELEKT nonsense FR0M")


def test_rejects_pg_sleep():
    with pytest.raises(SQLValidationError):
        validate_and_normalize("SELECT pg_sleep(60)")


def test_rejects_pg_sleep_used_as_a_predicate():
    with pytest.raises(SQLValidationError):
        validate_and_normalize("SELECT * FROM demo.claims WHERE pg_sleep(1) IS NULL")


def test_rejects_setval():
    with pytest.raises(SQLValidationError):
        validate_and_normalize("SELECT setval('some_seq', 1)")


def test_rejects_set_config():
    with pytest.raises(SQLValidationError):
        validate_and_normalize("SELECT set_config('statement_timeout', '0', false)")


def test_allows_ordinary_functions():
    sql = validate_and_normalize("SELECT COUNT(*), MAX(a), NOW() FROM demo.claims")
    assert "SELECT" in sql
