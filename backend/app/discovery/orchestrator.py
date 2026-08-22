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


def _describe_and_embed_table(engine, run_id: str, schema: str, table, profiles: dict) -> None:
    update_step(engine, run_id, f"describing:{table.name}")
    table_desc = describe_table(table, profiles)

    cols = [c for c in table.columns if c.name in profiles]
    # Column descriptions are independent LLM calls — run them concurrently
    # instead of one at a time. This is the dominant cost (thousands of
    # columns across a wide schema); bounded width avoids hammering the
    # provider with unlimited concurrent requests.
    with ThreadPoolExecutor(max_workers=DISCOVERY_DESCRIBE_CONCURRENCY) as pool:
        results = pool.map(lambda c: (c.name, describe_column(table.name, c, profiles[c.name])), cols)
    column_descs = dict(results)

    update_step(engine, run_id, f"embedding:{table.name}")
    embed_and_store(engine, table.name, table_desc, column_descs)


def _run_pipeline(engine, run_id: str, schema: str, tables) -> None:
    try:
        # Resume support: a table that already has an embedding entry was
        # already finished by an earlier run (including one that later
        # failed on a different table, e.g. hit a rate/credit limit) —
        # skip it rather than redoing already-paid-for LLM + embedding calls.
        remaining = [t for t in tables if not is_table_described(engine, t.name)]
        skipped = len(tables) - len(remaining)
        if skipped:
            log.info(f"resuming: {skipped} tables already described, {len(remaining)} remaining")

        update_step(engine, run_id, "profiling")
        profiles_by_table = {}
        for t in remaining:
            profiles_by_table[t.name] = profile_table(engine, schema, t)
            update_step(engine, run_id, f"profiling:{t.name}")

        update_step(engine, run_id, "inferring_relationships")
        infer_relationships(engine, schema, tables)  # logged; consumed by Stage 1b, not persisted here

        for table in remaining:
            _describe_and_embed_table(engine, run_id, schema, table, profiles_by_table[table.name])

        mark_done(engine, run_id)
    except Exception as e:
        mark_failed(engine, run_id, str(e))


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
