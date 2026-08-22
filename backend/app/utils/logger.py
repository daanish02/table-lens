"""Stdlib logging setup shared by every backend component. JSON-free,
plain readable lines: timestamp | level | module:func | message."""

import logging
import logging.handlers
import sys
from pathlib import Path

__all__ = ["get_logger"]

LOG_DIR = Path(__file__).parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s | %(message)s"
_formatter = logging.Formatter(_FORMAT)

_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(_formatter)

_file_handler = logging.handlers.TimedRotatingFileHandler(
    LOG_DIR / "app.log", when="midnight", interval=1, backupCount=3
)
_file_handler.setFormatter(_formatter)

_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_root_logger.handlers = [_stream_handler, _file_handler]  # pytest pre-configures root handlers; basicConfig() would silently no-op


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
