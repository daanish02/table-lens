"""Saved charts + dashboards: persistence for the visualization page.
Chart type / ECharts config are decided client-side from a query result
already returned by /api/query — these routes just store/retrieve what
the frontend built. See docs/SCHEMAS.md."""

from typing import Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.db import get_engine, save_chart, list_charts, get_chart, get_charts, save_dashboard, list_dashboards, get_dashboard
from app.api.middleware import limiter
from app.utils import get_logger

__all__ = ["router"]

log = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["charts"])


class SaveChartRequest(BaseModel):
    title: str
    question: str
    sql: str
    chart_type: str
    chart_config: dict[str, Any]
    result_cache: dict[str, Any]


class SaveDashboardRequest(BaseModel):
    title: str
    chart_ids: list[str]


@router.post("/charts")
@limiter.limit("20/minute")
def create_chart(request: Request, body: SaveChartRequest):
    engine = get_engine()
    return save_chart(engine, body.title, body.question, body.sql, body.chart_type, body.chart_config, body.result_cache)


@router.get("/charts")
@limiter.limit("20/minute")
def get_charts_list(request: Request):
    engine = get_engine()
    return {"charts": list_charts(engine)}


@router.get("/charts/{chart_id}")
@limiter.limit("20/minute")
def get_one_chart(request: Request, chart_id: str):
    engine = get_engine()
    chart = get_chart(engine, chart_id)
    if chart is None:
        raise HTTPException(status_code=404, detail="chart not found")
    return chart


@router.post("/dashboards")
@limiter.limit("20/minute")
def create_dashboard(request: Request, body: SaveDashboardRequest):
    engine = get_engine()
    return save_dashboard(engine, body.title, body.chart_ids)


@router.get("/dashboards")
@limiter.limit("20/minute")
def get_dashboards_list(request: Request):
    engine = get_engine()
    return {"dashboards": list_dashboards(engine)}


@router.get("/dashboards/{dashboard_id}")
@limiter.limit("20/minute")
def get_one_dashboard(request: Request, dashboard_id: str):
    engine = get_engine()
    dashboard = get_dashboard(engine, dashboard_id)
    if dashboard is None:
        raise HTTPException(status_code=404, detail="dashboard not found")
    charts = get_charts(engine, dashboard["chart_ids"] or [])
    return {**dashboard, "charts": charts}
