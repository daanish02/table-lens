"""Assembles a complete ECharts option from a compact LLM descriptor and
the already-executed SQL rows. The LLM decides structure and styling;
this module wires in the actual data values — keeping data encoding out
of the LLM's output entirely."""

from __future__ import annotations

__all__ = ["build_option", "validate_descriptor"]


def validate_descriptor(descriptor: dict, columns: list[str]) -> None:
    """Raises ValueError if any column reference in the descriptor doesn't
    exist in the actual query result columns."""
    col_set = set(columns)
    for field in ("x_column", "label_column", "value_column"):
        val = descriptor.get(field)
        if val and val not in col_set:
            raise ValueError(f"{field} {val!r} not in result columns {columns}")
    for yc in descriptor.get("y_columns") or []:
        col = yc.get("column")
        if col and col not in col_set:
            raise ValueError(f"y_column {col!r} not in result columns {columns}")


def build_option(descriptor: dict, rows: list[dict]) -> dict | None:
    chart_type = descriptor["chart_type"]
    if chart_type == "stat":
        return None
    builders = {
        "bar": _build_bar_line,
        "line": _build_bar_line,
        "pie": _build_pie,
        "scatter": _build_scatter,
    }
    fn = builders.get(chart_type)
    if fn is None:
        raise ValueError(f"unknown chart_type: {chart_type!r}")
    option = fn(descriptor, rows)
    option.setdefault("tooltip", {"trigger": "axis" if chart_type in ("bar", "line") else "item"})
    return option


def _build_bar_line(d: dict, rows: list[dict]) -> dict:
    chart_type = d["chart_type"]
    x_col = d["x_column"]
    y_cols: list[dict] = d.get("y_columns") or []

    categories = [str(r.get(x_col, "")) for r in rows]
    has_right = any(yc.get("axis") == "right" for yc in y_cols)

    series = []
    for yc in y_cols:
        s: dict = {
            "type": chart_type,
            "name": yc.get("label", yc["column"]),
            "data": [r.get(yc["column"]) for r in rows],
        }
        if color := yc.get("color"):
            s["itemStyle"] = {"color": color}
            if chart_type == "line":
                s["lineStyle"] = {"color": color}
        if has_right:
            s["yAxisIndex"] = 1 if yc.get("axis") == "right" else 0
        series.append(s)

    x_axis: dict = {"type": "category", "data": categories}
    if name := d.get("x_name"):
        x_axis["name"] = name
        x_axis["nameLocation"] = "middle"
        x_axis["nameGap"] = 30

    if d.get("rotate_x_labels"):
        x_axis["axisLabel"] = {"rotate": 35}

    left_y: dict = {"type": "value"}
    if name := d.get("y_name"):
        left_y["name"] = name

    option: dict = {"xAxis": x_axis, "series": series}

    if has_right:
        right_y: dict = {"type": "value", "position": "right"}
        if name := d.get("y2_name"):
            right_y["name"] = name
        option["yAxis"] = [left_y, right_y]
    else:
        option["yAxis"] = left_y

    if len(y_cols) > 1 or has_right:
        option["legend"] = {"top": 0 if d.get("rotate_x_labels") else "auto"}

    if d.get("rotate_x_labels"):
        option["legend"] = {"top": 0}
        option.setdefault("grid", {})["bottom"] = "20%"

    return option


def _build_pie(d: dict, rows: list[dict]) -> dict:
    label_col = d["label_column"]
    value_col = d["value_column"]
    data = [{"name": str(r.get(label_col, "")), "value": r.get(value_col)} for r in rows]
    option: dict = {"series": [{"type": "pie", "radius": "60%", "data": data}]}
    if colors := d.get("colors"):
        option["color"] = colors
    return option


def _build_scatter(d: dict, rows: list[dict]) -> dict:
    x_col = d["x_column"]
    y_cols: list[dict] = d.get("y_columns") or []
    y_col = y_cols[0]["column"] if y_cols else d.get("value_column", "")
    color = y_cols[0].get("color") if y_cols else None

    x_axis: dict = {"type": "value"}
    if name := d.get("x_name"):
        x_axis["name"] = name

    y_axis: dict = {"type": "value"}
    if name := d.get("y_name"):
        y_axis["name"] = name

    s: dict = {"type": "scatter", "data": [[r.get(x_col), r.get(y_col)] for r in rows]}
    if color:
        s["itemStyle"] = {"color": color}

    return {"xAxis": x_axis, "yAxis": y_axis, "series": [s]}
