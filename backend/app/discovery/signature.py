"""Per-column content signature — lets a discovery re-run tell which
columns actually changed since the last run, so it only re-pays LLM +
embedding cost for those (see docs/PRD.md, discovery re-run caching)."""

import hashlib
import json

from app.config import DISCOVERY_LARGE_TABLE_ROWS
from app.discovery.introspect import ColumnInfo
from app.discovery.profiler import ColumnProfile

__all__ = ["column_signature"]


def _round(v: float | None, digits: int) -> float | None:
    """Rounds, passing through None — floating-point noise across runs
    shouldn't register as a "changed" column."""
    return round(v, digits) if v is not None else None


def _normalize(v: object) -> str | None:
    """Stringifies a profile value consistently regardless of whether it's
    a live Python object or already round-tripped through JSONB."""
    # A live profile's min/max can be a real datetime.date/datetime object
    # (str() renders it as "2015-01-01 00:00:00", space-separated); the same
    # value read back out of the profile JSONB column is already a plain
    # ISO-8601 string ("2015-01-01T00:00:00", 'T'-separated — how pydantic's
    # mode="json" serializes it). str() on each gives two different strings
    # for the same instant, which permanently breaks the hash match for any
    # date/datetime/time-typed column. isoformat() (when available) makes
    # both paths converge on the same 'T'-separated string; str() is only a
    # fallback for values that were never date-like (Decimal, int, ...).
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def column_signature(column: ColumnInfo, profile: ColumnProfile) -> str:
    """Deterministic hash of one column's structure + stats — two calls
    for the same underlying data (even across runs) produce the same
    hash, so a mismatch means the column genuinely changed."""
    # row_count always comes from an exact COUNT(*) (see profiler._row_count)
    # — never sampled, safe to hash unconditionally as a cheap proxy for
    # "did this table's data change at all."
    payload = {
        "name": column.name,
        "data_type": column.data_type,
        "is_pk": column.is_pk,
        "is_fk": column.is_fk,
        "row_count": profile.row_count,
    }

    # Every other stat (null_rate, distinct_count, min/max, mean/percentiles,
    # top_values, histogram) is computed from `source` in profiler.py, which
    # switches to TABLESAMPLE BERNOULLI(2%) once a table exceeds
    # DISCOVERY_LARGE_TABLE_ROWS — a *different random sample every run*.
    # Hashing those for a sampled table would make it look "changed" on
    # essentially every run regardless of whether the data moved at all, so
    # they're only trustworthy (stable across runs of unchanged data) for
    # tables profiled via a full scan.
    if profile.row_count <= DISCOVERY_LARGE_TABLE_ROWS:
        payload.update({
            "null_rate": _round(profile.null_rate, 3),
            "distinct_count": profile.distinct_count,
            "min_value": _normalize(profile.min_value),
            "max_value": _normalize(profile.max_value),
            "mean_value": _round(profile.mean_value, 2),
            "p50": _round(profile.p50, 2),
            "p95": _round(profile.p95, 2),
            "top_values": sorted(profile.top_values),
            "histogram": profile.histogram,
        })

    return hashlib.md5(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
