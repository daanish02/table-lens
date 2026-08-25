"""The visualize agent: takes a query agent's already-finished result
(question, SQL, headline, columns, rows) and decides how to chart it.

Flow:
  1. Single LLM call → compact descriptor (column mappings + styling, no data)
  2. validate_descriptor() — column names must exist in the actual result
  3. build_option() — assembles the full ECharts option from descriptor + rows
  4. validate_chart_spec() — chart_guard normalizations (containLabel, pie labels, etc.)

The LLM never encodes data values — that's the builder's job. This cuts the
LLM's output from hundreds of data-point tokens to ~20 descriptor fields,
which is why a small fast model is the right fit for this step."""

import json
import time
import uuid
from app.visualize.llm import get_llm
from app.visualize import prompts
from app.visualize.builder import build_option, validate_descriptor
from app.visualize.chart_guard import validate_chart_spec, ChartValidationError
from app.visualize.theme import get_palette
from app.utils.logger import get_logger

__all__ = ["generate_chart"]

log = get_logger(__name__)

MAX_ATTEMPTS = 3

# Only pass a few sample rows — the LLM needs to understand column types
# (is this a date? a category string? a float?) to make good mapping decisions,
# not the full dataset. 5 rows is enough for that and keeps the prompt tiny.
SAMPLE_ROWS_FOR_PROMPT = 5


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
    call_id = uuid.uuid4().hex[:8]
    started = time.monotonic()
    palette = get_palette(theme)
    sample_rows = rows[:SAMPLE_ROWS_FOR_PROMPT]

    prompt = prompts.load("chart_spec").format(
        question=question,
        sql=sql,
        headline=headline or "",
        columns=", ".join(columns),
        row_count=len(rows),
        rows_note=f" (first {SAMPLE_ROWS_FOR_PROMPT} shown below)" if len(rows) > SAMPLE_ROWS_FOR_PROMPT else "",
        sample_rows=json.dumps(sample_rows, default=str),
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
            f"{prompt}\n\nYour previous descriptor failed: {last_error}\n"
            "Return ONLY corrected JSON, same shape as above."
        )
        log.info(f"[{call_id}] visualize agent attempt {attempt}/{MAX_ATTEMPTS}")
        response = llm.invoke(full_prompt)
        try:
            descriptor = _extract_json(response.content)
            validate_descriptor(descriptor, columns)
            option = build_option(descriptor, rows)
            spec = {
                "title": descriptor["title"],
                "chart_type": descriptor["chart_type"],
                "option": option,
            }
            spec = validate_chart_spec(spec)
            spec["elapsed_ms"] = round((time.monotonic() - started) * 1000)
            log.info(f"[{call_id}] chart generated: {spec['chart_type']} — {spec['title']!r} ({spec['elapsed_ms']}ms)")
            return spec
        except (json.JSONDecodeError, ChartValidationError, ValueError, KeyError) as e:
            last_error = str(e)
            log.warning(f"[{call_id}] attempt {attempt} failed: {e}")

    log.error(f"[{call_id}] chart generation failed after {MAX_ATTEMPTS} attempts: {last_error}")
    return {"title": question, "chart_type": "table", "option": None, "error": last_error}
