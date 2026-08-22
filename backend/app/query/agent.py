"""The query agent: turns a natural-language question into SQL via
LangChain tool-calling (search_tables -> search_columns -> run_sql, with
run_sql failures fed back for the agent to retry), then a second LLM call
turns the result into a plain-English headline (see docs/PRD.md, Query
Agent)."""

import json
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.errors import GraphRecursionError
from sqlalchemy import Engine

from app.query import prompts, tools as tools_module
from app.query.llm import get_llm
from app.query.headline import generate_headline
from app.utils.logger import get_logger

__all__ = ["ask"]

log = get_logger(__name__)

# Bounds total tool-call rounds per question. A genuinely open-ended
# analytical question (e.g. "are our underwriters too conservative?") can
# legitimately need several rounds of search_tables/search_columns plus
# more than one run_sql attempt across different angles — 20 was measured
# too tight and cut off a question that was making real progress.
RECURSION_LIMIT = 45


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

    # Streaming (not invoke) so that hitting the recursion limit doesn't
    # lose everything the agent already found — invoke() only returns on
    # clean completion, raising GraphRecursionError with no access to the
    # partial state. Streaming keeps the last successfully reached state,
    # which still has whatever run_sql results the agent got before running
    # out of steps.
    last_state = {"messages": conversation}
    hit_recursion_limit = False
    try:
        for state in agent.stream({"messages": conversation}, config={"recursion_limit": RECURSION_LIMIT}, stream_mode="values"):
            last_state = state
    except GraphRecursionError:
        hit_recursion_limit = True
        log.warning(f"recursion limit ({RECURSION_LIMIT}) hit for question: {question!r}")

    messages = last_state["messages"]
    sql_result = _last_successful_sql_result(messages)
    last_text = next((m.content for m in reversed(messages) if type(m).__name__ == "AIMessage" and m.content), "")

    if hit_recursion_limit:
        answer = (
            (last_text + "\n\n" if last_text else "")
            + ("This needed more exploration than I could finish — the SQL/results shown are the most relevant I found, but I didn't get to fully verify or explain them. Try a more specific question."
               if sql_result else
               "This question needed more exploration than I could complete — try breaking it into a more specific question.")
        )
    else:
        answer = last_text

    headline = None
    if sql_result and not hit_recursion_limit:
        headline = generate_headline(question, sql_result["sql"], sql_result)

    return {
        "answer": answer,
        "sql": sql_result["sql"] if sql_result else None,
        "columns": sql_result["columns"] if sql_result else None,
        "rows": sql_result["rows"] if sql_result else None,
        "row_count": sql_result["row_count"] if sql_result else None,
        "headline": headline,
    }
