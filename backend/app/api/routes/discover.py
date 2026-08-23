"""Discovery agent HTTP routes: trigger a run, poll its status, read back
results."""

from fastapi import APIRouter, HTTPException, Request

from app.db import get_engine
from app.discovery import (
    run_discovery, get_discovery_status, list_table_descriptions, get_column_descriptions,
    get_table_description, get_overview_stats, get_last_run, DiscoveryRunInProgress,
)
from app.api.middleware import limiter
from app.utils import get_logger

__all__ = ["router"]

log = get_logger(__name__)
router = APIRouter(prefix="/api/discover", tags=["discover"])


@router.post("", status_code=202)
# Tighter than the default 20/minute — this is by far the most expensive
# route (up to 8 concurrent paid LLM calls per table, ~50 tables), so it
# gets its own, much stingier budget rather than sharing the generic one.
@limiter.limit("5/hour")
def discover(request: Request):
    log.info("discover request received")
    try:
        run_id = run_discovery(background=True)
    except DiscoveryRunInProgress as e:
        raise HTTPException(status_code=409, detail={"message": "a discovery run is already in progress", "run_id": e.run_id})
    return {"run_id": run_id}


@router.get("/status/{run_id}")
@limiter.limit("20/minute")
def discover_status(request: Request, run_id: str):
    status = get_discovery_status(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="run_id not found")
    return status


@router.get("/results")
@limiter.limit("20/minute")
def discover_results(request: Request):
    engine = get_engine(readonly=True)
    return {"tables": list_table_descriptions(engine)}


@router.get("/results/{table_name}")
@limiter.limit("20/minute")
def discover_table_columns(request: Request, table_name: str):
    engine = get_engine(readonly=True)
    return {"table": get_table_description(engine, table_name), "columns": get_column_descriptions(engine, table_name)}


@router.get("/overview")
@limiter.limit("20/minute")
def discover_overview(request: Request):
    # get_last_run() calls ensure_runs_table() internally (self-healing
    # CREATE TABLE IF NOT EXISTS on public.discovery_runs) — a genuinely
    # read-only DB role correctly rejects that DDL, so this one call needs
    # the write engine. get_overview_stats() is a plain read, stays readonly.
    return {"stats": get_overview_stats(get_engine(readonly=True)), "last_run": get_last_run(get_engine())}
