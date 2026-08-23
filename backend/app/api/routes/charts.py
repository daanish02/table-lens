"""Saved charts + dashboards: persistence for the visualization page.
Chart type / ECharts config are decided client-side from a query result
already returned by /api/query — these routes just store/retrieve what
the frontend built. See docs/SCHEMAS.md."""

import json
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.db import get_engine, save_chart, list_charts, get_chart, get_charts, save_dashboard, list_dashboards, get_dashboard
from app.api.middleware import limiter
from app.utils import get_logger

__all__ = ["router"]

log = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["charts"])

MAX_TEXT_LENGTH = 4000  # sql can legitimately be long (multi-CTE queries)
MAX_DICT_BYTES = 500_000  # generous for a real chart spec + cached rows, not for an arbitrary blob
MAX_CHART_IDS = 200


def _check_dict_size(value: dict[str, Any]) -> dict[str, Any]:
    """Pydantic field_validator — rejects a dict whose JSON size exceeds
    MAX_DICT_BYTES (dicts can't use Field(max_length=...) directly)."""
    size = len(json.dumps(value, default=str))
    if size > MAX_DICT_BYTES:
        raise ValueError(f"payload too large ({size} bytes, max {MAX_DICT_BYTES})")
    return value


class SaveChartRequest(BaseModel):
    """Body for POST /api/charts — a chart the frontend already built."""

    title: str = Field(max_length=MAX_TEXT_LENGTH)
    question: str = Field(max_length=MAX_TEXT_LENGTH)
    sql: str = Field(max_length=MAX_TEXT_LENGTH)
    chart_type: str = Field(max_length=100)
    chart_config: dict[str, Any]
    result_cache: dict[str, Any]

    _check_chart_config = field_validator("chart_config")(_check_dict_size)
    _check_result_cache = field_validator("result_cache")(_check_dict_size)


class SaveDashboardRequest(BaseModel):
    """Body for POST /api/dashboards — a named, ordered set of chart_ids."""

    title: str = Field(max_length=MAX_TEXT_LENGTH)
    chart_ids: list[str] = Field(max_length=MAX_CHART_IDS)


@router.post("/charts")
@limiter.limit("20/minute")
def create_chart(request: Request, body: SaveChartRequest):
    """Saves a chart the frontend already built."""
    engine = get_engine()
    return save_chart(engine, body.title, body.question, body.sql, body.chart_type, body.chart_config, body.result_cache)


@router.get("/charts")
@limiter.limit("20/minute")
def get_charts_list(request: Request):
    """All saved charts."""
    engine = get_engine()
    return {"charts": list_charts(engine)}


@router.get("/charts/{chart_id}")
@limiter.limit("20/minute")
def get_one_chart(request: Request, chart_id: str):
    """One saved chart, or 404."""
    engine = get_engine()
    chart = get_chart(engine, chart_id)
    if chart is None:
        raise HTTPException(status_code=404, detail="chart not found")
    return chart


@router.post("/dashboards")
@limiter.limit("20/minute")
def create_dashboard(request: Request, body: SaveDashboardRequest):
    """Saves a dashboard (a named group of already-saved chart_ids)."""
    engine = get_engine()
    return save_dashboard(engine, body.title, body.chart_ids)


@router.get("/dashboards")
@limiter.limit("20/minute")
def get_dashboards_list(request: Request):
    """All saved dashboards."""
    engine = get_engine()
    return {"dashboards": list_dashboards(engine)}


@router.get("/dashboards/{dashboard_id}")
@limiter.limit("20/minute")
def get_one_dashboard(request: Request, dashboard_id: str):
    """One dashboard with its charts hydrated, or 404."""
    engine = get_engine()
    dashboard = get_dashboard(engine, dashboard_id)
    if dashboard is None:
        raise HTTPException(status_code=404, detail="dashboard not found")
    charts = get_charts(engine, dashboard["chart_ids"] or [])
    return {**dashboard, "charts": charts}
