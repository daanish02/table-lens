"""Read-only, paginated row browsing for the demo schema. No filtering or
sorting for v1 — see docs/PRD.md, data-overview feature spec."""

from sqlalchemy import text, Engine

from app.config import DEMO_SCHEMA
from app.db import queries
from app.discovery.introspect import get_schema_snapshot
from app.utils.logger import get_logger

__all__ = ["browse_table"]

log = get_logger(__name__)

MAX_PAGE_SIZE = 200


def browse_table(engine: Engine, table_name: str, page: int, page_size: int, schema: str = DEMO_SCHEMA) -> dict:
    """One page of a table's raw rows, ordered by primary key (or the
    first column if there isn't one).

    Args:
        table_name: Must be a real table in `schema` — raises ValueError
            otherwise.

    Returns:
        table/page/page_size/total_rows/columns/rows.
    """
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

    tables = {t.name: t for t in get_schema_snapshot(engine, schema)}
    table = tables.get(table_name)
    if table is None:
        raise ValueError(f"unknown table: {table_name}")

    pk_cols = [c.name for c in table.columns if c.is_pk]
    order_by = ", ".join(pk_cols) if pk_cols else table.columns[0].name

    with engine.connect() as conn:
        total = conn.execute(text(queries.load("data_row_count").format(schema=schema, table=table_name))).scalar()
        rows = conn.execute(
            text(queries.load("data_browse_rows").format(schema=schema, table=table_name, order_by=order_by)),
            {"limit": page_size, "offset": (page - 1) * page_size},
        ).mappings().all()

    return {
        "table": table_name,
        "page": page,
        "page_size": page_size,
        "total_rows": total,
        "columns": [c.name for c in table.columns],
        "rows": [dict(r) for r in rows],
    }
