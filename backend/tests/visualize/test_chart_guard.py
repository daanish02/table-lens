import pytest

from app.visualize.chart_guard import validate_chart_spec, ChartValidationError


def test_accepts_valid_bar_spec():
    spec = {
        "title": "Claims by Status",
        "chart_type": "bar",
        "option": {"series": [{"type": "bar", "data": [1, 2, 3]}]},
    }
    assert validate_chart_spec(spec) == spec


def test_accepts_stat_spec_with_null_option():
    spec = {"title": "Total Customers", "chart_type": "stat", "option": None}
    assert validate_chart_spec(spec) == spec


def test_rejects_non_dict():
    with pytest.raises(ChartValidationError):
        validate_chart_spec("not a dict")


def test_rejects_missing_keys():
    with pytest.raises(ChartValidationError):
        validate_chart_spec({"title": "x", "chart_type": "bar"})


def test_rejects_empty_title():
    with pytest.raises(ChartValidationError):
        validate_chart_spec({"title": "  ", "chart_type": "bar", "option": {"series": [{"type": "bar"}]}})


def test_rejects_unknown_chart_type():
    with pytest.raises(ChartValidationError):
        validate_chart_spec({"title": "x", "chart_type": "pyramid", "option": {"series": [{"type": "bar"}]}})


def test_rejects_non_dict_option_for_non_stat():
    with pytest.raises(ChartValidationError):
        validate_chart_spec({"title": "x", "chart_type": "bar", "option": None})


def test_rejects_empty_series():
    with pytest.raises(ChartValidationError):
        validate_chart_spec({"title": "x", "chart_type": "bar", "option": {"series": []}})


def test_rejects_series_missing_type():
    with pytest.raises(ChartValidationError):
        validate_chart_spec({"title": "x", "chart_type": "bar", "option": {"series": [{"data": [1]}]}})
