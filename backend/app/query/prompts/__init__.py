"""Prompt template loader for backend/app/query/ — prompt wording lives as
plain .txt files here, not inline in Python."""

from functools import lru_cache
from pathlib import Path

__all__ = ["load"]

_PROMPTS_DIR = Path(__file__).parent


@lru_cache
def load(name: str) -> str:
    """Load a prompt template by filename (without extension) from this
    directory. Templates use plain str.format() placeholders."""
    return (_PROMPTS_DIR / f"{name}.txt").read_text()
