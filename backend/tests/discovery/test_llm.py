import os
import pytest
from unittest.mock import patch, MagicMock

from app.discovery.llm import describe_table, describe_column
from app.discovery.introspect import TableInfo, ColumnInfo
from app.discovery.profiler import ColumnProfile

requires_llm = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="live network test — set RUN_LIVE_TESTS=1 to run",
)


def _sample_table():
    col = ColumnInfo(name="claim_amount", data_type="numeric", is_pk=False, is_fk=False, fk_table=None, fk_column=None)
    return TableInfo(name="claims", columns=[col]), {
        "claim_amount": ColumnProfile(row_count=1000, null_rate=0.02, distinct_count=950, mean_value=4200.5)
    }


def test_describe_table_calls_llm_with_profile_context():
    table, profiles = _sample_table()
    with patch("app.discovery.llm._get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Stores insurance claims."
        mock_get_llm.return_value = mock_llm

        result = describe_table(table, profiles)

        assert result == "Stores insurance claims."
        prompt_arg = mock_llm.invoke.call_args[0][0]
        assert "claims" in str(prompt_arg)
        assert "claim_amount" in str(prompt_arg)


def test_describe_column_includes_null_rate_in_prompt():
    table, profiles = _sample_table()
    with patch("app.discovery.llm._get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "The dollar amount of the claim."
        mock_get_llm.return_value = mock_llm

        result = describe_column("claims", table.columns[0], profiles["claim_amount"])

        assert result == "The dollar amount of the claim."
        prompt_arg = mock_llm.invoke.call_args[0][0]
        assert "0.02" in str(prompt_arg) or "2%" in str(prompt_arg) or "2.0%" in str(prompt_arg)


@requires_llm
def test_describe_table_against_real_llm():
    table, profiles = _sample_table()
    result = describe_table(table, profiles)
    assert isinstance(result, str) and len(result) > 0
