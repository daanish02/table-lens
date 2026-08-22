"""SQL query loader for backend/app/discovery/ — queries live as plain
.sql files here, not inline in Python."""

from functools import lru_cache
from pathlib import Path

__all__ = ["load"]

_QUERIES_DIR = Path(__file__).parent


@lru_cache
def load(name: str) -> str:
    """Load a SQL query by filename (without extension) from this directory.
    Queries with identifier placeholders (table/column names, which can't be
    bind parameters) use plain str.format() — bind parameters (:name) pass
    through untouched since .format() only touches {} placeholders."""
    return (_QUERIES_DIR / f"{name}.sql").read_text()
