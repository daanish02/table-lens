"""The query agent — turns a natural-language question about the demo
schema into validated, read-only SQL using discovery output for schema
retrieval, then summarizes the result. See docs/PRD.md, Query Agent."""

from app.query.agent import ask
from app.query.sql_guard import SQLValidationError, validate_and_normalize

__all__ = ["ask", "SQLValidationError", "validate_and_normalize"]
