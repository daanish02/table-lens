import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text

from app.config import DEMO_SCHEMA, DISCOVERY_DESCRIBE_CONCURRENCY
from app.db.connection import get_engine
from app.db.migrate import run_migrations
from app.discovery.idempotency import schema_hash, should_skip, start_run, update_step, mark_done, mark_failed, get_status
from app.discovery.introspect import get_schema_snapshot, to_hashable
from app.discovery.profiler import profile_table
from app.discovery.relationships import infer_relationships
from app.discovery.llm import describe_table, describe_column
from app.discovery.embeddings import embed_and_store, is_table_described
from app.utils.logger import get_logger

log = get_logger(__name__)


def _existing_run_id_for_hash(engine, hash_value: str) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT run_id FROM public.discovery_runs WHERE schema_hash = :h ORDER BY started_at DESC LIMIT 1"),
            {"h": hash_value},
        ).first()
    return row[0] if row else None


def _describe_column_safe(table_name: str, col, profile) -> tuple[str, str | None]:
    """One column's LLM call failing shouldn't take the rest of the table
    down with it. Caller filters out None results before embedding."""
    try:
        return col.name, describe_column(table_name, col, profile)
    except Exception as e:
        log.error(f"describing column {table_name}.{col.name} failed: {e}")
        return col.name, None


def _describe_and_embed_table(engine, run_id: str, schema: str, table, profiles: dict) -> None:
    update_step(engine, run_id, f"describing:{table.name}")
    table_desc = describe_table(table, profiles)

    cols = [c for c in table.columns if c.name in profiles]
    # Column descriptions are independent LLM calls — run them concurrently
    # instead of one at a time. This is the dominant cost (thousands of
    # columns across a wide schema); bounded width avoids hammering the
    # provider with unlimited concurrent requests.
    with ThreadPoolExecutor(max_workers=DISCOVERY_DESCRIBE_CONCURRENCY) as pool:
        results = pool.map(lambda c: _describe_column_safe(table.name, c, profiles[c.name]), cols)
    column_descs = {name: desc for name, desc in results if desc is not None}

    failed = len(cols) - len(column_descs)
    if failed:
        log.error(f"{table.name}: {failed} of {len(cols)} columns failed to describe, skipping them")

    update_step(engine, run_id, f"embedding:{table.name}")
    embed_and_store(engine, table.name, table_desc, column_descs)


def _run_pipeline(engine, run_id: str, schema: str, tables) -> None:
    # Resume support: a table that already has an embedding entry was
    # already finished by an earlier run (including one that later failed
    # on a different table, e.g. hit a rate/credit limit) — skip it rather
    # than redoing already-paid-for LLM + embedding calls.
    remaining = [t for t in tables if not is_table_described(engine, t.name)]
    skipped = len(tables) - len(remaining)
    if skipped:
        log.info(f"resuming: {skipped} tables already described, {len(remaining)} remaining")

    try:
        update_step(engine, run_id, "profiling")
        profiles_by_table = {}
        for t in remaining:
            profiles_by_table[t.name] = profile_table(engine, schema, t)
            update_step(engine, run_id, f"profiling:{t.name}")

        update_step(engine, run_id, "inferring_relationships")
        infer_relationships(engine, schema, tables)  # logged; consumed by Stage 1b, not persisted here
    except Exception as e:
        # Profiling/relationship inference are schema-wide, not per-table —
        # a failure here means nothing downstream can proceed.
        mark_failed(engine, run_id, f"profiling/relationships failed: {e}")
        return

    # One table's failure (e.g. its embedding batch call fails outright)
    # doesn't stop the rest — each remaining table gets a chance, so a
    # single run makes maximum forward progress. Only mark_failed if
    # something is genuinely still incomplete at the end; resume then
    # retries just the failures, not everything.
    table_failures: list[str] = []
    for table in remaining:
        try:
            _describe_and_embed_table(engine, run_id, schema, table, profiles_by_table[table.name])
        except Exception as e:
            log.error(f"table {table.name} failed: {e}")
            table_failures.append(table.name)

    if table_failures:
        mark_failed(engine, run_id, f"{len(table_failures)} table(s) failed: {', '.join(table_failures)}")
    else:
        mark_done(engine, run_id)


def run_discovery(db_url: str = "", schema: str = DEMO_SCHEMA, background: bool = False) -> str:
    engine = get_engine()
    run_migrations(engine)

    tables = get_schema_snapshot(engine, schema)
    hash_value = schema_hash(to_hashable(tables))

    if should_skip(engine, hash_value):
        run_id = _existing_run_id_for_hash(engine, hash_value)
        log.info(f"discovery skipped for {schema}, reusing run {run_id}")
        return run_id

    run_id = str(uuid.uuid4())
    start_run(engine, run_id, hash_value)

    if background:
        # API path: return run_id immediately, run the (potentially long,
        # LLM-call-heavy) pipeline off-thread so the request doesn't block.
        threading.Thread(target=_run_pipeline, args=(engine, run_id, schema, tables), daemon=True).start()
    else:
        _run_pipeline(engine, run_id, schema, tables)

    return run_id


def get_discovery_status(run_id: str) -> dict | None:
    engine = get_engine()
    return get_status(engine, run_id)
