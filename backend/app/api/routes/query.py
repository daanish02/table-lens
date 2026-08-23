"""Query agent HTTP route: natural language in, a server-sent-events
stream of live progress + validated SQL + results + plain-English headline
out. See docs/PRD.md, Query Agent."""

import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.db import get_engine
from app.query import ask_stream
from app.api.middleware import limiter
from app.utils import get_logger

__all__ = ["router"]

log = get_logger(__name__)
router = APIRouter(prefix="/api/query", tags=["query"])

MAX_TEXT_LENGTH = 2000  # generous headroom for a real question/answer, not a body-size DoS vector
MAX_HISTORY_TURNS = 20


class HistoryTurn(BaseModel):
    """One prior message in the conversation, fed back to the agent for context."""

    role: str  # "user" or "assistant"
    content: str = Field(max_length=MAX_TEXT_LENGTH)


class QueryRequest(BaseModel):
    """Body for POST /api/query."""

    question: str = Field(max_length=MAX_TEXT_LENGTH)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)


@router.post("")
@limiter.limit("20/minute")
def query(request: Request, body: QueryRequest):
    """SSE stream of the query agent's progress and final answer for one
    question. See ask_stream() for the event shapes."""
    engine = get_engine(readonly=True)
    history = [(turn.role, turn.content) for turn in body.history]
    started = time.monotonic()

    def event_source():
        """Wraps ask_stream() as SSE `data: {...}\\n\\n` lines, guaranteeing
        a terminal "done" event even if something inside fails."""
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
