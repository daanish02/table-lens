"""The visualize agent: takes a query agent's already-finished result
(question, SQL, headline, columns, rows) and decides how to chart it — a
single structured LLM call, not a tool-calling agent, since it has
nothing left to look up. Generated JSON is validated (chart_guard)
before being returned; on repeated failure, falls back to a plain
table rather than shipping something broken to the frontend."""

import json
from app.query.llm import get_llm
from app.visualize import prompts
from app.visualize.chart_guard import validate_chart_spec, ChartValidationError
from app.visualize.theme import get_palette
from app.utils.logger import get_logger

__all__ = ["generate_chart"]

log = get_logger(__name__)

MAX_ATTEMPTS = 3


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def generate_chart(question: str, sql: str, headline: str, columns: list[str], rows: list[dict], theme: str = "dark") -> dict:
    palette = get_palette(theme)
    prompt = prompts.load("chart").format(
        question=question,
        sql=sql,
        headline=headline or "",
        columns=", ".join(columns),
        row_count=len(rows),
        rows=json.dumps(rows, default=str),
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
        log.info(f"visualize agent attempt {attempt}/{MAX_ATTEMPTS}")
        response = llm.invoke(full_prompt)
        try:
            spec = _extract_json(response.content)
            spec = validate_chart_spec(spec)
            log.info(f"chart generated: {spec['chart_type']} — {spec['title']!r}")
            return spec
        except (json.JSONDecodeError, ChartValidationError) as e:
            last_error = str(e)
            log.warning(f"chart generation attempt {attempt} failed: {e}")

    log.error(f"chart generation failed after {MAX_ATTEMPTS} attempts: {last_error}")
    return {"title": question, "chart_type": "table", "option": None, "error": last_error}
