"""Backend-wide utilities not specific to any one component (currently
just logging)."""

from app.utils.logger import get_logger

__all__ = ["get_logger"]
