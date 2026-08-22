"""Query agent HTTP route: natural language in, a server-sent-events
stream of live progress + validated SQL + results + plain-English headline
out. See docs/PRD.md, Query Agent."""

import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.db import get_engine
from app.query import ask_stream
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

    def event_source():
        try:
            for event in ask_stream(engine, body.question, history=history):
                if event["type"] == "done":
                    event["elapsed_ms"] = round((time.monotonic() - started) * 1000)
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as e:
            # ask_stream() already handles the recursion-limit case
            # gracefully — this is the last-resort net for anything else
            # (LLM API failure, etc.) so the client always gets a usable
            # terminal event, never a broken stream.
            log.error(f"query agent stream failed unexpectedly: {e}")
            done = {
                "type": "done",
                "answer": "Something went wrong answering that — try rephrasing the question.",
                "sql": None, "columns": None, "rows": None, "row_count": None, "headline": None,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
            }
            yield f"data: {json.dumps(done)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
