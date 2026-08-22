import sys
import structlog
from functools import lru_cache

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    cache_logger_on_first_use=True,
)


@lru_cache
def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name).bind(logger=name)
