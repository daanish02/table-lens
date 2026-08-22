"""The query agent: turns a natural-language question into SQL via
LangChain tool-calling (search_tables -> search_columns -> run_sql, with
run_sql failures fed back for the agent to retry), then a second LLM call
turns the result into a plain-English headline (see docs/PRD.md, Query
Agent).

ask_stream() is the primary entrypoint — a generator yielding progress
events (tool calls, tool results, answer text deltas) as the agent works,
so a caller can show live progress instead of a blank wait. ask() is a
thin wrapper for callers (tests, scripts) that just want the final
result."""

import json
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.errors import GraphRecursionError
from sqlalchemy import Engine

from app.query import prompts, tools as tools_module
from app.query.llm import get_llm
from app.query.headline import generate_headline
from app.utils.logger import get_logger

__all__ = ["ask", "ask_stream"]

log = get_logger(__name__)

# Bounds total tool-call rounds per question. A genuinely open-ended
# analytical question (e.g. "are our underwriters too conservative?") can
# legitimately need several rounds of search_tables/search_columns plus
# more than one run_sql attempt across different angles — 20 was measured
# too tight and cut off a question that was making real progress.
RECURSION_LIMIT = 45


def _summarize_tool_result(name: str, content: str) -> str:
    try:
        payload = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return content[:200]
    if isinstance(payload, dict) and "error" in payload:
        return f"error: {payload['error']}"
    if isinstance(payload, list):
        return f"{len(payload)} results"
    if isinstance(payload, dict) and "row_count" in payload:
        return f"{payload['row_count']} rows"
    return str(payload)[:200]


def ask_stream(engine: Engine, question: str, history: list[tuple[str, str]] | None = None):
    """Yields progress dicts as the agent works:
    - {"type": "tool_call", "tool": str, "args": dict}
    - {"type": "tool_result", "tool": str, "summary": str}
    - {"type": "answer_delta", "text": str}
    - {"type": "done", "answer", "sql", "columns", "rows", "row_count", "headline"} (always last)
    """
    agent = create_agent(
        get_llm(),
        tools=tools_module.build_tools(engine),
        system_prompt=prompts.load("system"),
    )

    conversation = []
    for role, content in (history or [])[-10:]:
        conversation.append(HumanMessage(content=content) if role == "user" else AIMessage(content=content))
    conversation.append(HumanMessage(content=question))

    log.info(f"query agent: {question!r}")

    sql_result = None
    answer_chunks: dict[str, list[str]] = {}
    answer_order: list[str] = []
    hit_recursion_limit = False

    try:
        # 'updates' gives per-step tool-call/tool-result events (for live
        # progress); 'messages' gives token-level deltas of whatever text
        # the model is currently generating (for the typing effect on the
        # final answer). Tool-calling turns have empty .content — only the
        # final synthesis turn streams real text — so any non-empty chunk
        # is answer text, no separate signal needed to tell them apart.
        for mode, chunk in agent.stream(
            {"messages": conversation},
            config={"recursion_limit": RECURSION_LIMIT},
            stream_mode=["updates", "messages"],
        ):
            if mode == "updates":
                for _node_name, node_update in chunk.items():
                    for msg in node_update.get("messages", []):
                        cls = type(msg).__name__
                        if cls == "AIMessage":
                            for tc in (msg.tool_calls or []):
                                yield {"type": "tool_call", "tool": tc["name"], "args": tc["args"]}
                        elif cls == "ToolMessage":
                            name = getattr(msg, "name", "tool") or "tool"
                            yield {"type": "tool_result", "tool": name, "summary": _summarize_tool_result(name, msg.content)}
                            if name == "run_sql":
                                try:
                                    payload = json.loads(msg.content)
                                except (TypeError, json.JSONDecodeError):
                                    payload = None
                                if isinstance(payload, dict) and "sql" in payload and "error" not in payload:
                                    sql_result = payload
            elif mode == "messages":
                msg_chunk, _meta = chunk
                if type(msg_chunk).__name__ == "AIMessageChunk" and msg_chunk.content:
                    mid = msg_chunk.id
                    if mid not in answer_chunks:
                        answer_chunks[mid] = []
                        answer_order.append(mid)
                    answer_chunks[mid].append(msg_chunk.content)
                    yield {"type": "answer_delta", "text": msg_chunk.content}
    except GraphRecursionError:
        hit_recursion_limit = True
        log.warning(f"recursion limit ({RECURSION_LIMIT}) hit for question: {question!r}")

    answer = "".join(answer_chunks[answer_order[-1]]) if answer_order else ""

    if hit_recursion_limit:
        note = (
            "\n\nThis needed more exploration than I could finish — the SQL/results shown are the most relevant I found, but I didn't get to fully verify or explain them. Try a more specific question."
            if sql_result else
            "This question needed more exploration than I could complete — try breaking it into a more specific question."
        )
        yield {"type": "answer_delta", "text": note}
        answer = (answer + note) if answer else note.strip()

    headline = None
    if sql_result and not hit_recursion_limit:
        headline = generate_headline(question, sql_result["sql"], sql_result)

    yield {
        "type": "done",
        "answer": answer,
        "sql": sql_result["sql"] if sql_result else None,
        "columns": sql_result["columns"] if sql_result else None,
        "rows": sql_result["rows"] if sql_result else None,
        "row_count": sql_result["row_count"] if sql_result else None,
        "headline": headline,
    }


def ask(engine: Engine, question: str, history: list[tuple[str, str]] | None = None) -> dict:
    """Non-streaming: consumes ask_stream() and returns just the final
    result. For tests/scripts that don't need live progress."""
    result = {}
    for event in ask_stream(engine, question, history=history):
        if event["type"] == "done":
            result = {k: v for k, v in event.items() if k != "type"}
    return result
