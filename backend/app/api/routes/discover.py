from fastapi import APIRouter, HTTPException, Request

from app.db.connection import get_engine
from app.discovery.orchestrator import run_discovery, get_discovery_status
from app.discovery.embeddings import list_table_descriptions, get_column_descriptions
from app.api.middleware.rate_limit import limiter
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/api/discover", tags=["discover"])


@router.post("", status_code=202)
@limiter.limit("20/minute")
def discover(request: Request):
    log.info("discover request received")
    run_id = run_discovery(background=True)
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
    engine = get_engine()
    return {"tables": list_table_descriptions(engine)}


@router.get("/results/{table_name}")
@limiter.limit("20/minute")
def discover_table_columns(request: Request, table_name: str):
    engine = get_engine()
    return {"columns": get_column_descriptions(engine, table_name)}
