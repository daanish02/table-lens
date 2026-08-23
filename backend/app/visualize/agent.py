"""The visualize agent: takes a query agent's already-finished result
(question, SQL, headline, columns, rows) and decides how to chart it — a
single structured LLM call, not a tool-calling agent, since it has
nothing left to look up. Generated JSON is validated (chart_guard)
before being returned; on repeated failure, falls back to a plain
table rather than shipping something broken to the frontend."""

import json
import uuid
from app.visualize.llm import get_llm
from app.visualize import prompts
from app.visualize.chart_guard import validate_chart_spec, ChartValidationError
from app.visualize.theme import get_palette
from app.utils.logger import get_logger

__all__ = ["generate_chart"]

log = get_logger(__name__)

MAX_ATTEMPTS = 3

# Separate from sql_guard's 1000-row DB LIMIT (what's shown to the user) —
# this caps what actually gets JSON-dumped into the prompt. Every attempt
# in the retry loop below resends the same prompt, so an uncapped large
# result multiplies token cost by up to MAX_ATTEMPTS for no benefit: a
# chart's visual shape rarely needs more than a couple hundred data points
# to determine correctly.
MAX_ROWS_IN_PROMPT = 200


def _extract_json(text: str) -> dict:
    """Strips a markdown code fence around the LLM's JSON response, if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def generate_chart(question: str, sql: str, headline: str, columns: list[str], rows: list[dict], theme: str = "dark") -> dict:
    """One structured LLM call turning a finished query result into a
    validated {title, chart_type, option} spec, retrying up to
    MAX_ATTEMPTS on validation failure. Falls back to chart_type="table"
    if every attempt fails."""
    # Plain log lines have no request identity, so concurrent chart builds
    # (e.g. several dashboard cards queued close together) interleave into
    # an unreadable mess — a short id per call lets you grep one out.
    call_id = uuid.uuid4().hex[:8]
    palette = get_palette(theme)
    truncated = len(rows) > MAX_ROWS_IN_PROMPT
    rows_for_prompt = rows[:MAX_ROWS_IN_PROMPT] if truncated else rows
    rows_note = f" — showing the first {MAX_ROWS_IN_PROMPT}, truncated for length" if truncated else ""
    prompt = prompts.load("chart_spec").format(
        question=question,
        sql=sql,
        headline=headline or "",
        columns=", ".join(columns),
        row_count=len(rows),
        rows_note=rows_note,
        rows=json.dumps(rows_for_prompt, default=str),
        theme=theme,
        text_color=palette["text_color"],
        dim_text_color=palette["dim_text_color"],
        grid_color=palette["grid_color"],
        accent_color=palette["accent_color"],
        series_palette=json.dumps(palette["series_palette"]),
    )
    llm = get_llm()

    last_error: str | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        full_prompt = prompt if last_error is None else (
            f"{prompt}\n\nYour previous response failed validation: {last_error}\n"
            "Return ONLY corrected JSON, the exact same shape as instructed above."
        )
        log.info(f"[{call_id}] visualize agent attempt {attempt}/{MAX_ATTEMPTS}")
        response = llm.invoke(full_prompt)
        try:
            spec = _extract_json(response.content)
            spec = validate_chart_spec(spec)
            log.info(f"[{call_id}] chart generated: {spec['chart_type']} — {spec['title']!r}")
            return spec
        except (json.JSONDecodeError, ChartValidationError) as e:
            last_error = str(e)
            log.warning(f"[{call_id}] chart generation attempt {attempt} failed: {e}")

    log.error(f"[{call_id}] chart generation failed after {MAX_ATTEMPTS} attempts: {last_error}")
    return {"title": question, "chart_type": "table", "option": None, "error": last_error}
