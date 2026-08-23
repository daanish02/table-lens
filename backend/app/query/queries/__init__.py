"""SQL query loader for backend/app/query/ — same pattern as
app.discovery.queries and app.db.queries."""

from functools import lru_cache
from pathlib import Path

_QUERIES_DIR = Path(__file__).parent

__all__ = ["load"]


@lru_cache
def load(name: str) -> str:
    """Reads a .sql file by name (no extension) from this directory."""
    return (_QUERIES_DIR / f"{name}.sql").read_text()
