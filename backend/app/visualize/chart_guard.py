"""Validates the visualize agent's generated ECharts spec before it ever
reaches the frontend — same generate-then-validate shape as
app.query.sql_guard for the query agent's SQL. Structural validation only
(required keys, sane types) — not deep semantic checking of every string
inside an arbitrary ECharts option, which varies too much by chart type
to validate generically."""

__all__ = ["ChartValidationError", "validate_chart_spec"]

ALLOWED_CHART_TYPES = {"line", "bar", "pie", "scatter", "stat"}


class ChartValidationError(ValueError):
    pass


def validate_chart_spec(spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise ChartValidationError("chart spec must be a JSON object")

    for key in ("title", "chart_type", "option"):
        if key not in spec:
            raise ChartValidationError(f"missing required key: {key}")

    if not isinstance(spec["title"], str) or not spec["title"].strip():
        raise ChartValidationError("title must be a non-empty string")

    if spec["chart_type"] not in ALLOWED_CHART_TYPES:
        raise ChartValidationError(f"unknown chart_type: {spec['chart_type']!r}, must be one of {ALLOWED_CHART_TYPES}")

    if spec["chart_type"] == "stat":
        return spec  # option may legitimately be null for a single-value display

    option = spec["option"]
    if not isinstance(option, dict):
        raise ChartValidationError("option must be a JSON object (unless chart_type is 'stat')")

    series = option.get("series")
    if not isinstance(series, list) or len(series) == 0:
        raise ChartValidationError("option.series must be a non-empty list")

    for s in series:
        if not isinstance(s, dict) or "type" not in s:
            raise ChartValidationError("each series entry must be an object with a 'type'")

    return spec
