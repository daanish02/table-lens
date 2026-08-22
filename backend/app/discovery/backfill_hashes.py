"""One-off maintenance: computes and stores content_hash for columns that
were profiled/described before the content_hash column existed (see spec
Step C — discovery re-run caching). Not part of the regular discovery
pipeline: a normal run already sets content_hash as it goes. Without this
backfill, every existing column's stored hash is NULL, which the
hash-diff check in app.discovery.orchestrator reads as "changed" — the
very first run after deploying that column would silently reprocess
everything via the LLM, exactly the cost this feature exists to avoid.

Pure DB reads/writes — no LLM or embedding calls, no API cost."""

import json
from sqlalchemy import text

from app.config import DEMO_SCHEMA
from app.db.connection import get_engine
from app.discovery.introspect import get_schema_snapshot
from app.discovery.profiler import ColumnProfile
from app.discovery.signature import column_signature
from app.utils.logger import get_logger

__all__ = ["backfill_content_hashes"]

log = get_logger(__name__)


def backfill_content_hashes(schema: str = DEMO_SCHEMA) -> None:
    engine = get_engine()
    tables_by_name = {t.name: t for t in get_schema_snapshot(engine, schema)}

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT table_name, column_name, profile FROM public.column_embeddings WHERE profile IS NOT NULL"
        )).all()
    log.info(f"backfilling content_hash for {len(rows)} columns")

    with engine.connect() as conn:
        updated, skipped = 0, 0
        for table_name, column_name, profile_json in rows:
            table = tables_by_name.get(table_name)
            col = next((c for c in table.columns if c.name == column_name), None) if table else None
            if col is None:
                skipped += 1
                continue

            profile = ColumnProfile(**profile_json)
            content_hash = column_signature(col, profile)
            conn.execute(
                text("UPDATE public.column_embeddings SET content_hash = :h WHERE table_name = :t AND column_name = :c"),
                {"h": content_hash, "t": table_name, "c": column_name},
            )
            updated += 1
            if updated % 100 == 0:
                conn.commit()
                log.info(f"backfilled {updated}/{len(rows)} columns")
        conn.commit()

    log.info(f"backfill complete: {updated} columns updated, {skipped} skipped (no longer in live schema)")
