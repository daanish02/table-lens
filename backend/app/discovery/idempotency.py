import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import text, Engine

from app.utils.logger import get_logger

log = get_logger(__name__)

_DISCOVERY_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS public.discovery_runs (
    run_id       TEXT PRIMARY KEY,
    schema_hash  TEXT NOT NULL,
    status       TEXT NOT NULL,
    step         TEXT,
    error        TEXT,
    started_at   TIMESTAMPTZ DEFAULT NOW(),
    finished_at  TIMESTAMPTZ
);
"""


def schema_hash(schema_snapshot: list[dict]) -> str:
    normalized = sorted(schema_snapshot, key=lambda t: t["table"])
    payload = json.dumps(normalized, sort_keys=True)
    return hashlib.md5(payload.encode()).hexdigest()


def ensure_runs_table(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text(_DISCOVERY_RUNS_DDL))
        conn.commit()


def should_skip(engine: Engine, hash_value: str) -> bool:
    ensure_runs_table(engine)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT 1 FROM public.discovery_runs "
                "WHERE schema_hash = :h AND status = 'done' LIMIT 1"
            ),
            {"h": hash_value},
        ).first()
    return row is not None


def start_run(engine: Engine, run_id: str, hash_value: str) -> None:
    ensure_runs_table(engine)
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO public.discovery_runs (run_id, schema_hash, status, step) "
                "VALUES (:id, :h, 'running', 'started')"
            ),
            {"id": run_id, "h": hash_value},
        )
        conn.commit()
    log.info(f"discovery run started: run_id={run_id} schema_hash={hash_value}")


def update_step(engine: Engine, run_id: str, step: str) -> None:
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE public.discovery_runs SET step = :step WHERE run_id = :id"),
            {"step": step, "id": run_id},
        )
        conn.commit()
    log.info(f"discovery run {run_id} step: {step}")


def mark_done(engine: Engine, run_id: str) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE public.discovery_runs SET status = 'done', finished_at = :now "
                "WHERE run_id = :id"
            ),
            {"now": datetime.now(timezone.utc), "id": run_id},
        )
        conn.commit()
    log.info(f"discovery run done: {run_id}")


def mark_failed(engine: Engine, run_id: str, error: str) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE public.discovery_runs SET status = 'failed', error = :err, "
                "finished_at = :now WHERE run_id = :id"
            ),
            {"err": error, "now": datetime.now(timezone.utc), "id": run_id},
        )
        conn.commit()
    log.info(f"discovery run failed: {run_id} - {error}")


def get_status(engine: Engine, run_id: str) -> dict | None:
    ensure_runs_table(engine)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT run_id, status, step, error FROM public.discovery_runs "
                "WHERE run_id = :id"
            ),
            {"id": run_id},
        ).mappings().first()
    return dict(row) if row else None
