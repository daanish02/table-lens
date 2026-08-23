"""Visualize agent HTTP route: takes a finished query agent result in,
returns a validated chart spec (title + chart_type + ECharts option).
See docs/PRD.md, Chat + Chart UI."""

from typing import Any
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.visualize import generate_chart
from app.api.middleware import limiter
from app.utils import get_logger

__all__ = ["router"]

log = get_logger(__name__)
router = APIRouter(prefix="/api/visualize", tags=["visualize"])

MAX_TEXT_LENGTH = 4000  # sql can legitimately be long (multi-CTE queries)

# Matches sql_guard's own DB-level LIMIT — a legitimate /api/query result can
# be up to 1000 rows, so this isn't tightening what's allowed, just closing
# the "unbounded body size" gap for anything beyond that.
MAX_ROWS = 1000
MAX_COLUMNS = 200


class VisualizeRequest(BaseModel):
    question: str = Field(max_length=MAX_TEXT_LENGTH)
    sql: str = Field(max_length=MAX_TEXT_LENGTH)
    headline: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH)
    columns: list[str] = Field(max_length=MAX_COLUMNS)
    rows: list[dict[str, Any]] = Field(max_length=MAX_ROWS)
    theme: str = "dark"


@router.post("")
@limiter.limit("20/minute")
def visualize(request: Request, body: VisualizeRequest):
    return generate_chart(body.question, body.sql, body.headline or "", body.columns, body.rows, theme=body.theme)
