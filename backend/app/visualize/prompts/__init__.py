"""Prompt template loader for backend/app/visualize/ — prompt wording
lives as plain .md files here, not inline in Python."""

from functools import lru_cache
from pathlib import Path

__all__ = ["load"]

_PROMPTS_DIR = Path(__file__).parent


@lru_cache
def load(name: str) -> str:
    """Reads a .md prompt template by name (no extension) from this directory."""
    return (_PROMPTS_DIR / f"{name}.md").read_text()
