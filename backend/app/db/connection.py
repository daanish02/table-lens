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
    return create_engine(_normalize(url), pool_pre_ping=True)
