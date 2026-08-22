"""Visualize agent HTTP route: takes a finished query agent result in,
returns a validated chart spec (title + chart_type + ECharts option).
See docs/PRD.md, Chat + Chart UI."""

from typing import Any
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.visualize import generate_chart
from app.api.middleware import limiter
from app.utils import get_logger

__all__ = ["router"]

log = get_logger(__name__)
router = APIRouter(prefix="/api/visualize", tags=["visualize"])


class VisualizeRequest(BaseModel):
    question: str
    sql: str
    headline: str | None = None
    columns: list[str]
    rows: list[dict[str, Any]]
    theme: str = "dark"


@router.post("")
@limiter.limit("20/minute")
def visualize(request: Request, body: VisualizeRequest):
    return generate_chart(body.question, body.sql, body.headline or "", body.columns, body.rows, theme=body.theme)
