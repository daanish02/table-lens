"""Database connection management and schema migrations, shared by every
backend component that talks to Postgres."""

from app.db.connection import get_engine
from app.db.migrate import run_migrations
from app.db.data_browser import browse_table

__all__ = ["get_engine", "run_migrations", "browse_table"]
