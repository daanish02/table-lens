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


def test_strips_js_function_string_formatter():
    spec = {
        "title": "x",
        "chart_type": "pie",
        "option": {
            "tooltip": {"trigger": "item", "formatter": "function(params) { return params.name; }"},
            "series": [{"type": "pie", "label": {"formatter": "function (p) {return p.value}"}}],
        },
    }
    result = validate_chart_spec(spec)
    assert "formatter" not in result["option"]["tooltip"]
    assert "formatter" not in result["option"]["series"][0]["label"]


def test_keeps_template_string_formatter():
    spec = {
        "title": "x",
        "chart_type": "pie",
        "option": {
            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
            "series": [{"type": "pie"}],
        },
    }
    result = validate_chart_spec(spec)
    assert result["option"]["tooltip"]["formatter"] == "{b}: {c} ({d}%)"


def test_moves_bottom_legend_to_top_when_labels_rotated():
    spec = {
        "title": "x",
        "chart_type": "bar",
        "option": {
            "legend": {"bottom": 0},
            "xAxis": {"type": "category", "data": ["A"], "axisLabel": {"rotate": 45}},
            "series": [{"type": "bar", "data": [1]}],
        },
    }
    result = validate_chart_spec(spec)
    assert "bottom" not in result["option"]["legend"]
    assert result["option"]["legend"]["top"] == 0
    assert result["option"]["grid"]["bottom"] == "18%"


def test_moves_bottom_legend_to_top_when_many_categories():
    spec = {
        "title": "x",
        "chart_type": "bar",
        "option": {
            "legend": {"bottom": 0},
            "xAxis": {"type": "category", "data": [f"cat_{i}" for i in range(15)]},
            "series": [{"type": "bar", "data": list(range(15))}],
        },
    }
    result = validate_chart_spec(spec)
    assert "bottom" not in result["option"]["legend"]
    assert result["option"]["grid"]["bottom"] == "18%"


def test_leaves_layout_untouched_when_few_categories_no_rotation():
    spec = {
        "title": "x",
        "chart_type": "bar",
        "option": {
            "legend": {"bottom": 0},
            "xAxis": {"type": "category", "data": ["A", "B", "C"]},
            "series": [{"type": "bar", "data": [1, 2, 3]}],
        },
    }
    result = validate_chart_spec(spec)
    assert result["option"]["legend"] == {"bottom": 0}
    # containLabel is always forced on (see test_forces_contain_label_on) —
    # only the crowded-labels-specific "bottom" adjustment is untouched here.
    assert result["option"]["grid"] == {"containLabel": True}


def test_forces_contain_label_on_when_no_grid_given():
    spec = {
        "title": "x",
        "chart_type": "bar",
        "option": {"series": [{"type": "bar", "data": [1, 2, 3]}]},
    }
    result = validate_chart_spec(spec)
    assert result["option"]["grid"] == {"containLabel": True}


def test_forces_contain_label_on_without_overriding_existing_grid_settings():
    spec = {
        "title": "x",
        "chart_type": "bar",
        "option": {
            "grid": {"left": "10%", "containLabel": False},
            "series": [{"type": "bar", "data": [1, 2, 3]}],
        },
    }
    result = validate_chart_spec(spec)
    # containLabel: False was explicit, not just unset — left as the LLM's choice.
    assert result["option"]["grid"] == {"left": "10%", "containLabel": False}


def test_strips_duplicate_option_title():
    spec = {
        "title": "Claims by Status",
        "chart_type": "bar",
        "option": {
            "title": {"text": "Claims by Status"},
            "series": [{"type": "bar", "data": [1, 2, 3]}],
        },
    }
    result = validate_chart_spec(spec)
    assert "title" not in result["option"]
    assert result["title"] == "Claims by Status"
