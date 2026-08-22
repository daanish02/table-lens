"""Query agent HTTP route: natural language in, validated SQL + results +
plain-English headline out. See docs/PRD.md, Query Agent."""

import time
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db import get_engine
from app.query import ask
from app.api.middleware import limiter
from app.utils import get_logger

__all__ = ["router"]

log = get_logger(__name__)
router = APIRouter(prefix="/api/query", tags=["query"])


class HistoryTurn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class QueryRequest(BaseModel):
    question: str
    history: list[HistoryTurn] = []


@router.post("")
@limiter.limit("20/minute")
def query(request: Request, body: QueryRequest):
    engine = get_engine(readonly=True)
    history = [(turn.role, turn.content) for turn in body.history]
    started = time.monotonic()
    try:
        result = ask(engine, body.question, history=history)
    except Exception as e:
        # ask() already handles the recursion-limit case gracefully — this
        # is the last-resort net for anything else (LLM API failure, etc.)
        # so the frontend always gets a usable JSON body, never a raw 500.
        log.error(f"query agent failed unexpectedly: {e}")
        result = {
            "answer": "Something went wrong answering that — try rephrasing the question.",
            "sql": None, "columns": None, "rows": None, "row_count": None, "headline": None,
        }
    result["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    return result
