"""FastAPI middleware — currently just IP-based rate limiting."""

from app.api.middleware.rate_limit import limiter

__all__ = ["limiter"]
