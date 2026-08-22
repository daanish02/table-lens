import os
from functools import lru_cache
from sqlalchemy import create_engine, Engine

from app.config import DB_URL
from app.utils.logger import get_logger

log = get_logger(__name__)

READONLY_DB_URL = os.getenv("SUPABASE_DB_URL_READONLY", DB_URL)


def _normalize(url: str) -> str:
    """Supabase issues postgres:// URLs; SQLAlchemy + psycopg3 need the
    explicit postgresql+psycopg:// scheme."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@lru_cache
def get_engine(readonly: bool = False) -> Engine:
    url = READONLY_DB_URL if readonly else DB_URL
    if not url:
        raise RuntimeError("SUPABASE_DB_URL is not set")
    log.info(f"creating DB engine (readonly={readonly})")
    # Explicit, modest pool size — Supabase's session-mode pooler caps at 15
    # total connections; SQLAlchemy's default (5 + 10 overflow = 15) leaves
    # zero headroom for anything else hitting the same pooler concurrently.
    return create_engine(_normalize(url), pool_pre_ping=True, pool_size=6, max_overflow=2)
