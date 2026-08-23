"""Shared slowapi rate limiter, keyed per-IP. Individual routes apply this
default via @limiter.limit(...) or override it with a tighter one."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import RATE_LIMIT

limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT])
