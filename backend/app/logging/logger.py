import logging
import logging.handlers
import sys
from pathlib import Path
from functools import lru_cache

import structlog

LOG_DIR = Path(__file__).parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)

_stream_handler = logging.StreamHandler(sys.stdout)
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "app.log", maxBytes=10_000_000, backupCount=5
)

_formatter = structlog.stdlib.ProcessorFormatter(processor=structlog.processors.JSONRenderer())
_stream_handler.setFormatter(_formatter)
_file_handler.setFormatter(_formatter)

_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_root_logger.handlers = [_stream_handler, _file_handler]  # pytest pre-configures root handlers; basicConfig() would silently no-op

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


@lru_cache
def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name).bind(logger=name)
