"""Validates the visualize agent's generated ECharts spec before it ever
reaches the frontend — same generate-then-validate shape as
app.query.sql_guard for the query agent's SQL. Structural validation only
(required keys, sane types) — not deep semantic checking of every string
inside an arbitrary ECharts option, which varies too much by chart type
to validate generically."""

__all__ = ["ChartValidationError", "validate_chart_spec"]

ALLOWED_CHART_TYPES = {"line", "bar", "pie", "scatter", "stat"}


class ChartValidationError(ValueError):
    """Raised when a generated chart spec fails validate_chart_spec()."""

    pass


def _strip_js_function_strings(node):
    """The option is JSON, so it can never carry a real function — if the LLM
    writes "function(params) {...}" as a formatter string, ECharts has nothing
    to execute and renders it as literal text. Drop any such key so ECharts
    falls back to its own default instead of showing raw JS source."""
    if isinstance(node, dict):
        for key in list(node.keys()):
            value = node[key]
            if isinstance(value, str) and "function(" in value.replace(" ", ""):
                del node[key]
            else:
                _strip_js_function_strings(value)
    elif isinstance(node, list):
        for item in node:
            _strip_js_function_strings(item)


def _has_rotated_or_crowded_labels(x_axis) -> bool:
    """True if this xAxis has rotated labels or enough categories that rotation
    is likely — either signal means a bottom-anchored legend will collide with
    the axis labels."""
    if not isinstance(x_axis, dict):
        return False
    axis_label = x_axis.get("axisLabel")
    if isinstance(axis_label, dict) and axis_label.get("rotate"):
        return True
    data = x_axis.get("data")
    return isinstance(data, list) and len(data) > 8


def _normalize_layout(option: dict) -> None:
    """Safety net for the class of bug where the LLM anchors the legend to the
    bottom of a chart with rotated/crowded x-axis category labels, so the two
    overlap. Same generate-then-validate pattern as SQL — the prompt already
    asks the LLM to avoid this, but this forcibly corrects it regardless of
    what the LLM actually produced."""
    x_axis_entries = option.get("xAxis")
    if isinstance(x_axis_entries, dict):
        x_axis_entries = [x_axis_entries]
    if not isinstance(x_axis_entries, list):
        return

    crowded = any(_has_rotated_or_crowded_labels(x) for x in x_axis_entries)
    if not crowded:
        return

    legend = option.get("legend")
    if isinstance(legend, list):
        legends = legend
    elif isinstance(legend, dict):
        legends = [legend]
    else:
        legends = []

    for entry in legends:
        if "bottom" in entry:
            del entry["bottom"]
            entry["top"] = entry.get("top", 0)

    grid = option.get("grid")
    if not isinstance(grid, dict):
        grid = {}
        option["grid"] = grid
    grid["bottom"] = "18%"


def _ensure_contain_label(option: dict) -> None:
    """Forces grid.containLabel = true unless the LLM explicitly set it.
    Without it, axis labels and axis `name` text (e.g. a "Ratio" title next
    to the value axis) are positioned assuming the grid box already leaves
    room for them — if it doesn't, they render past the plot's edge and get
    clipped by the chart card's fixed width instead of just being tight.
    containLabel makes ECharts auto-reserve the space instead of assuming
    it's already there. Handles grid as a single object or (for multi-grid
    combo charts) a list of them."""
    grid = option.get("grid")
    if isinstance(grid, list):
        for g in grid:
            if isinstance(g, dict):
                g.setdefault("containLabel", True)
    elif isinstance(grid, dict):
        grid.setdefault("containLabel", True)
    else:
        option["grid"] = {"containLabel": True}


def validate_chart_spec(spec: dict) -> dict:
    """Validates + normalizes a generated chart spec in place (stripping
    unusable JS-function strings, auto-fixing known layout collisions),
    raising ChartValidationError if it's structurally unusable."""
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

    _strip_js_function_strings(option)
    _normalize_layout(option)
    _ensure_contain_label(option)
    option.pop("title", None)  # frontend renders spec["title"] as its own heading; a
                                # duplicate ECharts title component wastes vertical space
                                # and can overlap the plot when the chart is shown small
                                # (e.g. a dashboard grid card).
    return spec
