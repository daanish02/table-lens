"""FastAPI route modules, one per resource — currently just discovery."""

from app.api.routes.discover import router as discover_router

__all__ = ["discover_router"]
