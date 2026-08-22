"""Query agent HTTP route: natural language in, validated SQL + results +
plain-English headline out. See docs/PRD.md, Query Agent."""

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
    return ask(engine, body.question, history=history)
