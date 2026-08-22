"""SQL query loader for backend/app/db/ — same pattern as
app.discovery.queries, kept separate since db/ and discovery/ are distinct
modules and shouldn't import from one another for something this small."""

from functools import lru_cache
from pathlib import Path

_QUERIES_DIR = Path(__file__).parent

__all__ = ["load"]


@lru_cache
def load(name: str) -> str:
    return (_QUERIES_DIR / f"{name}.sql").read_text()
