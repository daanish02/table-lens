"""Raw data browser HTTP routes: paginated read-only row access to the
demo schema. No filtering or sorting for v1."""

from fastapi import APIRouter, HTTPException, Request

from app.db import get_engine, browse_table
from app.api.middleware import limiter
from app.utils import get_logger

__all__ = ["router"]

log = get_logger(__name__)
router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/{table_name}")
@limiter.limit("20/minute")
def data_browse(request: Request, table_name: str, page: int = 1, page_size: int = 50):
    engine = get_engine()
    try:
        return browse_table(engine, table_name, page, page_size)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
