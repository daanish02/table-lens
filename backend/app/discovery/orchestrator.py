"""Drives the discovery pipeline end to end: profile every table, infer
relationships, then describe+embed only what actually changed (per-column
content-hash caching — see signature.py). Runs in a background thread per
call so the triggering HTTP request returns immediately."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from app.config import DEMO_SCHEMA, DISCOVERY_DESCRIBE_CONCURRENCY, DISCOVERY_PROFILE_CONCURRENCY
from app.db.connection import get_engine
from app.db.migrate import run_migrations
from app.discovery.idempotency import (
    schema_hash, start_run, update_step, mark_done, mark_failed, get_status,
    set_progress_total, increment_tables_done, get_active_run,
)
from app.discovery.introspect import get_schema_snapshot, to_hashable
from app.discovery.profiler import profile_table
from app.discovery.relationships import infer_relationships
from app.discovery.llm import describe_table, describe_column
from app.discovery.embeddings import embed_and_store, is_table_described, get_column_hashes, refresh_profiles
from app.discovery.signature import column_signature
from app.utils.logger import get_logger

log = get_logger(__name__)


class DiscoveryRunInProgress(Exception):
    """Raised by run_discovery() when another run is already pending/running
    — without this, an unauthenticated caller could trigger unbounded
    concurrent runs, each paying real LLM/embedding cost per table."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"discovery run already in progress: {run_id}")


def _describe_column_safe(table_name: str, col, profile) -> tuple[str, str | None]:
    """One column's LLM call failing shouldn't take the rest of the table
    down with it. Caller filters out None results before embedding."""
    try:
        return col.name, describe_column(table_name, col, profile)
    except Exception as e:
        log.error(f"describing column {table_name}.{col.name} failed: {e}")
        return col.name, None


def _process_table(engine, run_id: str, schema: str, table, profiles: dict, all_table_names: list[str]) -> None:
    """Refreshes one table's stats unconditionally, then describes+embeds
    it only if at least one column's content actually changed since last
    run (or it's never been described)."""
    # Every column's profile.row_count is the same table-level value —
    # any one of them works.
    row_count = next(iter(profiles.values())).row_count if profiles else None

    stored_hashes = get_column_hashes(engine, table.name)
    fresh_hashes = {c.name: column_signature(c, profiles[c.name]) for c in table.columns if c.name in profiles}
    changed_cols = [c for c in table.columns if c.name in fresh_hashes and fresh_hashes[c.name] != stored_hashes.get(c.name)]

    # Always refresh stats for every profiled column — cheap, DB-only, keeps
    # /data's histograms/counts current every run regardless of whether any
    # description actually changes below.
    update_step(engine, run_id, f"refreshing:{table.name}")
    refresh_profiles(engine, table.name, profiles, row_count, fresh_hashes)

    if not changed_cols and is_table_described(engine, table.name):
        # Nothing about this table changed since it was last (fully)
        # described — skip the LLM/embedding calls entirely.
        update_step(engine, run_id, f"table_done:{table.name}:{len(profiles)}")
        increment_tables_done(engine, run_id)
        return

    update_step(engine, run_id, f"describing:{table.name}")
    # A handful of sibling table names gives the LLM enough context to infer
    # the database's domain — without this, an ambiguously-named table (e.g.
    # "agents" in an insurance schema) tends to get a generic/wrong guess.
    sibling_tables = sorted(n for n in all_table_names if n != table.name)[:15]
    table_desc = describe_table(table, profiles, sibling_tables=sibling_tables)

    # Column descriptions are independent LLM calls — run them concurrently
    # instead of one at a time. Only columns whose content actually changed
    # (or are brand new) get re-described; everything else keeps its prior
    # description/embedding untouched.
    with ThreadPoolExecutor(max_workers=DISCOVERY_DESCRIBE_CONCURRENCY) as pool:
        results = pool.map(lambda c: _describe_column_safe(table.name, c, profiles[c.name]), changed_cols)
    column_descs = {name: desc for name, desc in results if desc is not None}

    failed = len(changed_cols) - len(column_descs)
    if failed:
        log.error(f"{table.name}: {failed} of {len(changed_cols)} changed columns failed to describe, skipping them")

    update_step(engine, run_id, f"embedding:{table.name}")
    embed_and_store(
        engine, table.name, table_desc, column_descs,
        profiles={n: profiles[n] for n in column_descs}, row_count=row_count,
        column_count=len(profiles), content_hashes={n: fresh_hashes[n] for n in column_descs},
    )
    # Distinct "done" marker (not just "embedding:X") so the frontend can
    # tell a table's work actually finished, and how many columns it got —
    # "embedding:X" alone doesn't say whether it's still in flight or done.
    update_step(engine, run_id, f"table_done:{table.name}:{len(profiles)}")
    increment_tables_done(engine, run_id)


def _run_pipeline(engine, run_id: str, schema: str, tables) -> None:
    """Profiles every table, infers relationships, then processes each
    table (see _process_table). Marks the run done/failed at the end."""
    # Every table is always (re-)profiled — profiling is DB-bound and cheap
    # after the batched-query rewrite, and it's the only way to know whether
    # a table's columns actually changed. What's expensive (LLM + embedding
    # calls) is gated per-column inside _process_table via content_hash, not
    # by skipping whole tables here.
    remaining = tables

    def _profile_one(t):
        try:
            return t.name, profile_table(engine, schema, t), None
        except Exception as e:
            return t.name, None, str(e)

    try:
        # Moved inside the try (was called before it started) — a failure
        # here used to propagate uncaught out of _run_pipeline (this runs on
        # a daemon thread, so the exception just prints to stderr) leaving
        # the run stuck at status='running' forever with no mark_failed call.
        set_progress_total(engine, run_id, total=len(tables), done_already=0)
        update_step(engine, run_id, "profiling")
        # Profiling is DB-bound (SQL round-trips), not LLM-bound — tables
        # are independent, so profile several concurrently instead of one
        # at a time. This was the actual bottleneck behind "profiling takes
        # an hour": schema introspection was optimized earlier, but the
        # per-column statistics queries (the expensive part) never were.
        profiles_by_table = {}
        profile_failed: list[str] = []
        with ThreadPoolExecutor(max_workers=DISCOVERY_PROFILE_CONCURRENCY) as pool:
            for name, profile, err in pool.map(_profile_one, remaining):
                if err is not None:
                    log.error(f"profiling {name} failed: {err}")
                    profile_failed.append(name)
                else:
                    profiles_by_table[name] = profile
                update_step(engine, run_id, f"profiling:{name}")

        if profile_failed:
            remaining = [t for t in remaining if t.name not in profile_failed]

        update_step(engine, run_id, "inferring_relationships")
        infer_relationships(engine, schema, tables)  # logged; consumed by Stage 1b, not persisted here
    except Exception as e:
        # Schema-wide failure (not a single table) — nothing downstream can
        # proceed without it.
        mark_failed(engine, run_id, f"profiling/relationships failed: {e}")
        return

    # One table's failure (e.g. its embedding batch call fails outright)
    # doesn't stop the rest — each remaining table gets a chance, so a
    # single run makes maximum forward progress. Only mark_failed if
    # something is genuinely still incomplete at the end; resume then
    # retries just the failures, not everything.
    all_table_names = [t.name for t in tables]
    table_failures: list[str] = list(profile_failed)
    for table in remaining:
        try:
            _process_table(engine, run_id, schema, table, profiles_by_table[table.name], all_table_names)
        except Exception as e:
            log.error(f"table {table.name} failed: {e}")
            table_failures.append(table.name)

    if table_failures:
        mark_failed(engine, run_id, f"{len(table_failures)} table(s) failed: {', '.join(table_failures)}")
    else:
        mark_done(engine, run_id)


def run_discovery(db_url: str = "", schema: str = DEMO_SCHEMA, background: bool = False) -> str:
    """Starts a new discovery run, returns its run_id.

    Args:
        background: If True, runs the pipeline on a daemon thread and
            returns immediately (the HTTP API path). If False, runs
            synchronously (tests/scripts).

    Raises:
        DiscoveryRunInProgress: if a run is already pending/running.
    """
    # No whole-run short-circuit: every run always executes, since the
    # per-column content_hash check in _process_table is what actually
    # decides whether LLM/embedding cost is paid (schema_hash is still
    # recorded on the run for visibility, just doesn't gate execution
    # anymore — see docs/PRD.md, discovery re-run caching).
    engine = get_engine()
    run_migrations(engine)

    # Without this, an unauthenticated caller could trigger unbounded
    # concurrent runs — each one pays real LLM/embedding cost per table.
    active = get_active_run(engine)
    if active is not None:
        raise DiscoveryRunInProgress(active["run_id"])

    tables = get_schema_snapshot(engine, schema)
    hash_value = schema_hash(to_hashable(tables))

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
    """One run's current status, or None if run_id is unknown."""
    engine = get_engine()
    return get_status(engine, run_id)
