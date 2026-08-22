from fastapi import APIRouter, HTTPException, Request

from app.discovery.orchestrator import run_discovery, get_discovery_status
from app.api.middleware.rate_limit import limiter
from app.logging.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/api/discover", tags=["discover"])


@router.post("", status_code=202)
@limiter.limit("20/minute")
def discover(request: Request, body: dict):
    db_url = body["db_url"]
    log.info("api.discover.request", db_url_present=bool(db_url))
    run_id = run_discovery(db_url)
    return {"run_id": run_id}


@router.get("/status/{run_id}")
@limiter.limit("20/minute")
def discover_status(request: Request, run_id: str):
    status = get_discovery_status(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="run_id not found")
    return status
