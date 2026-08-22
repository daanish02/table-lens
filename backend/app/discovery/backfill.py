"""One-off maintenance: fills row_count/column_count/profile for tables
that were described before that data started being persisted (see spec
Decision — Step 1 of the data-overview work). Not part of the regular
discovery pipeline: a normal run already persists this data as it goes
(app.discovery.orchestrator), so this only matters for pre-existing rows.
Pure DB reads/writes — no LLM or embedding calls, no API cost."""

import json
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text

from app.config import DEMO_SCHEMA, DISCOVERY_PROFILE_CONCURRENCY
from app.db.connection import get_engine
from app.discovery.introspect import get_schema_snapshot
from app.discovery.profiler import profile_table
from app.discovery.embeddings import list_table_descriptions
from app.discovery import queries
from app.utils.logger import get_logger

__all__ = ["backfill_profile_stats"]

log = get_logger(__name__)


def _backfill_one(engine, schema: str, table) -> None:
    profiles = profile_table(engine, schema, table)
    row_count = next(iter(profiles.values())).row_count if profiles else None

    with engine.connect() as conn:
        conn.execute(
            text("UPDATE public.table_embeddings SET row_count = :r, column_count = :c WHERE table_name = :t"),
            {"r": row_count, "c": len(profiles), "t": table.name},
        )
        for col_name, profile in profiles.items():
            conn.execute(
                text(queries.load("embeddings_backfill_column_profile")),
                {"profile": json.dumps(profile.model_dump(mode="json")), "t": table.name, "c": col_name},
            )
        conn.commit()
    log.info(f"backfilled {table.name}: {len(profiles)} columns")


def backfill_profile_stats(schema: str = DEMO_SCHEMA) -> None:
    engine = get_engine()
    already_described = {row["table_name"] for row in list_table_descriptions(engine)}
    tables = [t for t in get_schema_snapshot(engine, schema) if t.name in already_described]

    log.info(f"backfilling profile stats for {len(tables)} tables")
    with ThreadPoolExecutor(max_workers=DISCOVERY_PROFILE_CONCURRENCY) as pool:
        list(pool.map(lambda t: _backfill_one(engine, schema, t), tables))

    log.info("backfill complete")
