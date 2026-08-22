"""The query agent: turns a natural-language question into SQL via
LangChain tool-calling (search_tables -> search_columns -> run_sql, with
run_sql failures fed back for the agent to retry), then a second LLM call
turns the result into a plain-English headline (see docs/PRD.md, Query
Agent)."""

import json
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from sqlalchemy import Engine

from app.query import prompts, tools as tools_module
from app.query.llm import get_llm
from app.query.headline import generate_headline
from app.utils.logger import get_logger

__all__ = ["ask"]

log = get_logger(__name__)

# Bounds total tool-call rounds per question — generous enough for
# search_tables -> a few search_columns -> run_sql -> up to ~3 retries, but
# not unbounded (each superstep is a real LLM call).
RECURSION_LIMIT = 20


def _last_successful_sql_result(messages: list) -> dict | None:
    """Walk the tool-call trace backwards for the most recent run_sql call
    that returned results rather than an error — that's the query the
    agent actually landed on, even if it retried earlier."""
    for msg in reversed(messages):
        if type(msg).__name__ != "ToolMessage":
            continue
        try:
            payload = json.loads(msg.content)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and "sql" in payload and "error" not in payload:
            return payload
    return None


def ask(engine: Engine, question: str, history: list[tuple[str, str]] | None = None) -> dict:
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
    result = agent.invoke({"messages": conversation}, config={"recursion_limit": RECURSION_LIMIT})

    messages = result["messages"]
    answer = messages[-1].content if messages else ""
    sql_result = _last_successful_sql_result(messages)

    headline = None
    if sql_result:
        headline = generate_headline(question, sql_result["sql"], sql_result)

    return {
        "answer": answer,
        "sql": sql_result["sql"] if sql_result else None,
        "columns": sql_result["columns"] if sql_result else None,
        "rows": sql_result["rows"] if sql_result else None,
        "row_count": sql_result["row_count"] if sql_result else None,
        "headline": headline,
    }
