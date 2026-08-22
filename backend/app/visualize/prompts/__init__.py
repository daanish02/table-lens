"""Prompt template loader for backend/app/visualize/ — prompt wording
lives as plain .txt files here, not inline in Python."""

from functools import lru_cache
from pathlib import Path

__all__ = ["load"]

_PROMPTS_DIR = Path(__file__).parent


@lru_cache
def load(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.txt").read_text()
