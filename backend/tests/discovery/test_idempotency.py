from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.config import DISCOVERY_STALE_RUN_MINUTES
from app.discovery.idempotency import get_active_run, schema_hash


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


def _mock_engine_returning(row: dict | None) -> MagicMock:
    engine = MagicMock()
    conn = engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.mappings.return_value.first.return_value = row
    return engine


@patch("app.discovery.idempotency.ensure_runs_table")
@patch("app.discovery.idempotency.mark_failed")
def test_get_active_run_reaps_a_stale_running_row(mock_mark_failed, mock_ensure):
    stale_row = {
        "run_id": "stale-run",
        "status": "running",
        "started_at": datetime.now(timezone.utc) - timedelta(minutes=DISCOVERY_STALE_RUN_MINUTES + 5),
    }
    result = get_active_run(_mock_engine_returning(stale_row))

    assert result is None
    mock_mark_failed.assert_called_once()
    assert mock_mark_failed.call_args[0][1] == "stale-run"


@patch("app.discovery.idempotency.ensure_runs_table")
@patch("app.discovery.idempotency.mark_failed")
def test_get_active_run_leaves_a_recent_running_row_alone(mock_mark_failed, mock_ensure):
    fresh_row = {
        "run_id": "fresh-run",
        "status": "running",
        "started_at": datetime.now(timezone.utc) - timedelta(minutes=5),
    }
    result = get_active_run(_mock_engine_returning(fresh_row))

    assert result == fresh_row
    mock_mark_failed.assert_not_called()


@patch("app.discovery.idempotency.ensure_runs_table")
@patch("app.discovery.idempotency.mark_failed")
def test_get_active_run_returns_none_when_nothing_active(mock_mark_failed, mock_ensure):
    assert get_active_run(_mock_engine_returning(None)) is None
    mock_mark_failed.assert_not_called()
