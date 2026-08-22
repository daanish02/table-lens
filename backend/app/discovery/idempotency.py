import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import text, Engine

from app.discovery import queries
from app.utils.logger import get_logger

log = get_logger(__name__)


def schema_hash(schema_snapshot: list[dict]) -> str:
    normalized = sorted(schema_snapshot, key=lambda t: t["table"])
    payload = json.dumps(normalized, sort_keys=True)
    return hashlib.md5(payload.encode()).hexdigest()


def ensure_runs_table(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text(queries.load("idempotency_create_runs_table")))
        conn.commit()


def should_skip(engine: Engine, hash_value: str) -> bool:
    ensure_runs_table(engine)
    with engine.connect() as conn:
        row = conn.execute(text(queries.load("idempotency_should_skip")), {"h": hash_value}).first()
    return row is not None


def start_run(engine: Engine, run_id: str, hash_value: str) -> None:
    ensure_runs_table(engine)
    with engine.connect() as conn:
        conn.execute(text(queries.load("idempotency_start_run")), {"id": run_id, "h": hash_value})
        conn.commit()
    log.info(f"discovery run started: run_id={run_id} schema_hash={hash_value}")


def update_step(engine: Engine, run_id: str, step: str) -> None:
    with engine.connect() as conn:
        conn.execute(text(queries.load("idempotency_update_step")), {"step": step, "id": run_id})
        conn.commit()
    log.info(f"discovery run {run_id} step: {step}")


def set_progress_total(engine: Engine, run_id: str, total: int, done_already: int) -> None:
    """total_tables is the whole schema; done_already accounts for tables a
    resumed run is skipping (already completed by an earlier attempt) —
    progress reflects true overall completion, not just this run's work."""
    with engine.connect() as conn:
        conn.execute(text(queries.load("idempotency_set_progress_total")), {"total": total, "done": done_already, "id": run_id})
        conn.commit()


def increment_tables_done(engine: Engine, run_id: str) -> None:
    with engine.connect() as conn:
        conn.execute(text(queries.load("idempotency_increment_tables_done")), {"id": run_id})
        conn.commit()


def mark_done(engine: Engine, run_id: str) -> None:
    with engine.connect() as conn:
        conn.execute(text(queries.load("idempotency_mark_done")), {"now": datetime.now(timezone.utc), "id": run_id})
        conn.commit()
    log.info(f"discovery run done: {run_id}")


def mark_failed(engine: Engine, run_id: str, error: str) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(queries.load("idempotency_mark_failed")),
            {"err": error, "now": datetime.now(timezone.utc), "id": run_id},
        )
        conn.commit()
    log.info(f"discovery run failed: {run_id} - {error}")


def get_status(engine: Engine, run_id: str) -> dict | None:
    ensure_runs_table(engine)
    with engine.connect() as conn:
        row = conn.execute(text(queries.load("idempotency_get_status")), {"id": run_id}).mappings().first()
    return dict(row) if row else None
