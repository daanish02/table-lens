"""
Idempotency layer.

Each table tracks:
  - schema_hash  : hash of the DDL string → regenerate if schema changed
  - row_count    : target row count → regenerate if config changed
  - generated_at : timestamp
  - parquet_path : where the file lives

On re-run:
  - If parquet exists AND schema_hash matches AND row_count matches → SKIP
  - Otherwise → regenerate and update manifest
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from config import MANIFEST


def _load_manifest() -> dict:
    """Reads the manifest JSON, or {} if it doesn't exist yet."""
    if MANIFEST.exists():
        with open(MANIFEST) as f:
            return json.load(f)
    return {}


def _save_manifest(manifest: dict) -> None:
    """Writes the manifest back to disk as JSON."""
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2, default=str)


def schema_hash(ddl: str) -> str:
    """Deterministic hash of a table's DDL string, for change detection."""
    return hashlib.md5(ddl.strip().encode()).hexdigest()


def should_skip(table_name: str, ddl: str, row_count: int, parquet_path: Path) -> bool:
    """Return True if the table can be skipped (already generated, unchanged)."""
    manifest = _load_manifest()

    if table_name not in manifest:
        return False

    entry = manifest[table_name]
    parquet_ok    = parquet_path.exists() and parquet_path.stat().st_size > 0
    hash_ok       = entry.get("schema_hash") == schema_hash(ddl)
    row_count_ok  = entry.get("row_count") == row_count

    return parquet_ok and hash_ok and row_count_ok


def mark_done(table_name: str, ddl: str, row_count: int, parquet_path: Path) -> None:
    """Record a completed generation in the manifest."""
    manifest = _load_manifest()
    manifest[table_name] = {
        "schema_hash":  schema_hash(ddl),
        "row_count":    row_count,
        "parquet_path": str(parquet_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_manifest(manifest)


def reset_table(table_name: str) -> None:
    """Force regeneration of a specific table on next run."""
    manifest = _load_manifest()
    if table_name in manifest:
        del manifest[table_name]
        _save_manifest(manifest)
        print(f"[idempotency] Reset '{table_name}' — will regenerate on next run.")
    else:
        print(f"[idempotency] '{table_name}' not in manifest — nothing to reset.")


def reset_all() -> None:
    """Force regeneration of everything."""
    if MANIFEST.exists():
        MANIFEST.unlink()
    print("[idempotency] Manifest cleared — full regeneration on next run.")


def status() -> dict:
    """Return current manifest for inspection."""
    return _load_manifest()
