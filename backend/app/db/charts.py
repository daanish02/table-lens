"""Persistence for saved charts and dashboards (public schema) — pure
CRUD, no chart-type/config generation here. Chart type + ECharts option
are decided client-side from the query result already returned by
/api/query, so the backend only needs to store/retrieve what the
frontend built. See docs/SCHEMAS.md."""

import json
from sqlalchemy import text, Engine

from app.db import queries
from app.utils.logger import get_logger

__all__ = ["save_chart", "list_charts", "get_chart", "get_charts", "save_dashboard", "list_dashboards", "get_dashboard"]

log = get_logger(__name__)


def save_chart(
    engine: Engine,
    title: str,
    question: str,
    sql: str,
    chart_type: str,
    chart_config: dict,
    result_cache: dict,
) -> dict:
    """Inserts one saved chart, returns the stored row (including its
    generated id)."""
    with engine.connect() as conn:
        row = conn.execute(
            text(queries.load("charts_insert")),
            {
                "title": title, "question": question, "sql": sql, "chart_type": chart_type,
                "chart_config": json.dumps(chart_config), "result_cache": json.dumps(result_cache, default=str),
            },
        ).mappings().first()
        conn.commit()
    log.info(f"saved chart {row['id']}: {title!r}")
    return dict(row)


def list_charts(engine: Engine) -> list[dict]:
    """All saved charts, most recent first."""
    with engine.connect() as conn:
        rows = conn.execute(text(queries.load("charts_list"))).mappings().all()
    return [dict(r) for r in rows]


def get_chart(engine: Engine, chart_id: str) -> dict | None:
    """One saved chart by id, or None if it doesn't exist."""
    with engine.connect() as conn:
        row = conn.execute(text(queries.load("charts_get")), {"id": chart_id}).mappings().first()
    return dict(row) if row else None


def get_charts(engine: Engine, chart_ids: list[str]) -> list[dict]:
    """Batch fetch — used to hydrate a dashboard's chart_ids into full
    chart rows."""
    if not chart_ids:
        return []
    with engine.connect() as conn:
        rows = conn.execute(text(queries.load("charts_get_many")), {"ids": chart_ids}).mappings().all()
    return [dict(r) for r in rows]


def save_dashboard(engine: Engine, title: str, chart_ids: list[str]) -> dict:
    """Inserts one dashboard (an ordered list of chart_ids), returns the
    stored row."""
    with engine.connect() as conn:
        row = conn.execute(
            text(queries.load("dashboards_insert")), {"title": title, "chart_ids": chart_ids}
        ).mappings().first()
        conn.commit()
    log.info(f"saved dashboard {row['id']}: {title!r} ({len(chart_ids)} charts)")
    return dict(row)


def list_dashboards(engine: Engine) -> list[dict]:
    """All saved dashboards, most recent first."""
    with engine.connect() as conn:
        rows = conn.execute(text(queries.load("dashboards_list"))).mappings().all()
    return [dict(r) for r in rows]


def get_dashboard(engine: Engine, dashboard_id: str) -> dict | None:
    """One dashboard by id, or None if it doesn't exist."""
    with engine.connect() as conn:
        row = conn.execute(text(queries.load("dashboards_get")), {"id": dashboard_id}).mappings().first()
    return dict(row) if row else None
