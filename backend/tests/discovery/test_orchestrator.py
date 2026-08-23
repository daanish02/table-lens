import os
import pytest
from unittest.mock import patch, MagicMock

from app.discovery.orchestrator import run_discovery, get_discovery_status, _process_table, DiscoveryRunInProgress
from app.discovery.introspect import TableInfo, ColumnInfo
from app.discovery.profiler import ColumnProfile
from app.discovery.signature import column_signature

requires_full_stack = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="live network test — set RUN_LIVE_TESTS=1 to run",
)


@pytest.mark.slow
@requires_full_stack
def test_run_discovery_completes_and_reports_status():
    run_id = run_discovery(os.environ["SUPABASE_DB_URL"], schema="demo")
    status = get_discovery_status(run_id)
    assert status["status"] in {"running", "done"}


@patch("app.discovery.orchestrator.get_active_run")
@patch("app.discovery.orchestrator.run_migrations")
@patch("app.discovery.orchestrator.get_engine")
def test_run_discovery_refuses_when_a_run_is_already_active(mock_get_engine, mock_migrations, mock_active):
    mock_active.return_value = {"run_id": "already-running-id", "status": "running"}
    with pytest.raises(DiscoveryRunInProgress) as exc_info:
        run_discovery()
    assert exc_info.value.run_id == "already-running-id"


def _col(name="a", data_type="integer", is_pk=False, is_fk=False):
    return ColumnInfo(name=name, data_type=data_type, is_pk=is_pk, is_fk=is_fk, fk_table=None, fk_column=None)


def _profile(**overrides):
    defaults = dict(row_count=100, null_rate=0.0, distinct_count=5)
    defaults.update(overrides)
    return ColumnProfile(**defaults)


@patch("app.discovery.orchestrator.increment_tables_done")
@patch("app.discovery.orchestrator.update_step")
@patch("app.discovery.orchestrator.embed_and_store")
@patch("app.discovery.orchestrator.describe_column")
@patch("app.discovery.orchestrator.describe_table")
@patch("app.discovery.orchestrator.is_table_described")
@patch("app.discovery.orchestrator.refresh_profiles")
@patch("app.discovery.orchestrator.get_column_hashes")
def test_process_table_skips_llm_when_no_column_changed(
    mock_hashes, mock_refresh, mock_described, mock_describe_table, mock_describe_col, mock_embed, mock_step, mock_inc,
):
    col = _col()
    profile = _profile()
    table = TableInfo(name="t", columns=[col])
    mock_hashes.return_value = {"a": column_signature(col, profile)}
    mock_described.return_value = True

    _process_table(MagicMock(), "run1", "demo", table, {"a": profile}, ["t"])

    mock_refresh.assert_called_once()
    mock_describe_table.assert_not_called()
    mock_describe_col.assert_not_called()
    mock_embed.assert_not_called()


@patch("app.discovery.orchestrator.increment_tables_done")
@patch("app.discovery.orchestrator.update_step")
@patch("app.discovery.orchestrator.embed_and_store")
@patch("app.discovery.orchestrator.describe_column")
@patch("app.discovery.orchestrator.describe_table")
@patch("app.discovery.orchestrator.is_table_described")
@patch("app.discovery.orchestrator.refresh_profiles")
@patch("app.discovery.orchestrator.get_column_hashes")
def test_process_table_redescribes_changed_column(
    mock_hashes, mock_refresh, mock_described, mock_describe_table, mock_describe_col, mock_embed, mock_step, mock_inc,
):
    col = _col()
    profile = _profile()
    table = TableInfo(name="t", columns=[col])
    mock_hashes.return_value = {"a": "stale-hash-not-matching"}
    mock_described.return_value = True
    mock_describe_table.return_value = "a table"
    mock_describe_col.return_value = "a column"

    _process_table(MagicMock(), "run1", "demo", table, {"a": profile}, ["t"])

    mock_describe_table.assert_called_once()
    mock_describe_col.assert_called_once()
    mock_embed.assert_called_once()
    _, kwargs = mock_embed.call_args
    assert kwargs["column_count"] == 1
    assert "a" in kwargs["profiles"]


@patch("app.discovery.orchestrator.increment_tables_done")
@patch("app.discovery.orchestrator.update_step")
@patch("app.discovery.orchestrator.embed_and_store")
@patch("app.discovery.orchestrator.describe_column")
@patch("app.discovery.orchestrator.describe_table")
@patch("app.discovery.orchestrator.is_table_described")
@patch("app.discovery.orchestrator.refresh_profiles")
@patch("app.discovery.orchestrator.get_column_hashes")
def test_process_table_only_describes_new_column_on_existing_table(
    mock_hashes, mock_refresh, mock_described, mock_describe_table, mock_describe_col, mock_embed, mock_step, mock_inc,
):
    col_a, col_b = _col("a"), _col("b")
    profile_a, profile_b = _profile(), _profile(distinct_count=9)
    table = TableInfo(name="t", columns=[col_a, col_b])
    # "a" matches its stored hash (unchanged); "b" has no stored hash (new column).
    mock_hashes.return_value = {"a": column_signature(col_a, profile_a)}
    mock_described.return_value = True
    mock_describe_table.return_value = "a table"
    mock_describe_col.return_value = "a column"

    _process_table(MagicMock(), "run1", "demo", table, {"a": profile_a, "b": profile_b}, ["t"])

    # describe_column called once, and only for the new column "b".
    mock_describe_col.assert_called_once()
    called_column = mock_describe_col.call_args[0][1]
    assert called_column.name == "b"
    _, kwargs = mock_embed.call_args
    assert kwargs["column_count"] == 2
    assert list(kwargs["profiles"].keys()) == ["b"]
