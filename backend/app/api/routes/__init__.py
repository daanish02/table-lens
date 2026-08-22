"""FastAPI route modules, one per resource."""

from app.api.routes.discover import router as discover_router
from app.api.routes.data import router as data_router
from app.api.routes.query import router as query_router
from app.api.routes.charts import router as charts_router
from app.api.routes.visualize import router as visualize_router

__all__ = ["discover_router", "data_router", "query_router", "charts_router", "visualize_router"]
