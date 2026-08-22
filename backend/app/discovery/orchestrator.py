import uuid
from sqlalchemy import text

from app.config import DEMO_SCHEMA
from app.db.connection import get_engine
from app.db.migrate import run_migrations
from app.discovery.idempotency import schema_hash, should_skip, start_run, update_step, mark_done, mark_failed, get_status
from app.discovery.introspect import get_schema_snapshot, to_hashable
from app.discovery.profiler import profile_table
from app.discovery.relationships import infer_relationships
from app.discovery.llm import describe_table, describe_column
from app.discovery.embeddings import embed_and_store
from app.utils.logger import get_logger

log = get_logger(__name__)


def _existing_run_id_for_hash(engine, hash_value: str) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT run_id FROM public.discovery_runs WHERE schema_hash = :h ORDER BY started_at DESC LIMIT 1"),
            {"h": hash_value},
        ).first()
    return row[0] if row else None


def run_discovery(db_url: str, schema: str = DEMO_SCHEMA) -> str:
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

    try:
        update_step(engine, run_id, "profiling")
        profiles_by_table = {t.name: profile_table(engine, schema, t) for t in tables}

        update_step(engine, run_id, "inferring_relationships")
        infer_relationships(engine, schema, tables)  # logged; consumed by Stage 1b, not persisted here

        update_step(engine, run_id, "describing")
        for table in tables:
            profiles = profiles_by_table[table.name]
            table_desc = describe_table(table, profiles)
            column_descs = {
                col.name: describe_column(table.name, col, profiles[col.name])
                for col in table.columns if col.name in profiles
            }

            update_step(engine, run_id, f"embedding:{table.name}")
            embed_and_store(engine, table.name, table_desc, column_descs)

        mark_done(engine, run_id)
    except Exception as e:
        mark_failed(engine, run_id, str(e))
        raise

    return run_id


def get_discovery_status(run_id: str) -> dict | None:
    engine = get_engine()
    return get_status(engine, run_id)
