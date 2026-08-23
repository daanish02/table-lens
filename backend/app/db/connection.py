import os
from functools import lru_cache
from sqlalchemy import create_engine, Engine

from app.config import DB_URL
from app.utils.logger import get_logger

log = get_logger(__name__)

READONLY_DB_URL = os.getenv("SUPABASE_DB_URL_READONLY", DB_URL)
if READONLY_DB_URL == DB_URL:
    # Silently falling back to the full read-write role would undermine the
    # entire "read-only enforced at the DB level" story (see sql_guard.py)
    # with no visible signal that it happened — exactly the kind of thing
    # that gets missed on a first deploy. Loud on purpose.
    log.warning(
        "SUPABASE_DB_URL_READONLY is not set — get_engine(readonly=True) will use the "
        "full read-write DB_URL instead. SQL guard / read-only DB role protection is "
        "NOT actually enforced at the database level until this is set."
    )


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
    # total connections. get_engine() is @lru_cache'd per readonly bool, so
    # TWO independent engines exist at runtime (one per bool value) — sizing
    # has to account for their combined worst case, not just one engine's
    # own pool. 4 + 1 overflow = 5 per engine, 10 combined, leaving real
    # headroom under the 15 cap for anything else (migrations, admin access).
    return create_engine(_normalize(url), pool_pre_ping=True, pool_size=4, max_overflow=1)
