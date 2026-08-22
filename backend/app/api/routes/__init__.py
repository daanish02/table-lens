"""FastAPI route modules, one per resource."""

from app.api.routes.discover import router as discover_router
from app.api.routes.data import router as data_router

__all__ = ["discover_router", "data_router"]
