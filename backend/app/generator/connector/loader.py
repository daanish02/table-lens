"""
Supabase loader.

Reads generated parquet files and loads them into Supabase (Postgres).

Usage:
    uv run connector/loader.py                     # load all tables
    uv run connector/loader.py --table customers   # load one table
    uv run connector/loader.py --dry-run           # validate without loading

Setup:
    1. Create a Supabase project at https://supabase.com
    2. Go to Project Settings → Database → Connection String → URI
    3. Set SUPABASE_DB_URL in config.py (or .env file)
"""

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import psycopg
from rich.console import Console
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

# Allow env var override
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL") or ""

# Import after env load
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import OUTPUT_DIR, BATCH_SIZE, DEMO_SCHEMA, ROW_COUNTS
from schema.ddl import get_ddl, all_table_names

console = Console()

MAX_WORKERS = 3  # concurrent table loads. Supabase's session-mode pooler caps
# at 15 total connections; each worker holds one raw psycopg connection plus
# borrows from the SQLAlchemy pool, and killed runs can leave stale
# connections lingering — keep this low to leave headroom.
_thread_local = threading.local()
_all_raw_conns = []          # every raw connection ever opened, for explicit cleanup
_all_raw_conns_lock = threading.Lock()

LOAD_ORDER = [
    "financial_periods", "products", "repair_shops", "employers", "agents",
    "reinsurance_treaties", "customers", "customer_addresses", "customer_contacts",
    "credit_checks", "compliance_checks", "risk_scores", "policies",
    "policy_versions", "policy_endorsements", "policy_documents", "policy_payments",
    "policy_cancellations", "policy_renewals", "coverage_details",
    "product_pricing_rules", "quote_attempts", "underwriting_assessments",
    "inspection_reports", "exclusions", "beneficiaries", "agent_performance",
    "claims", "claim_events", "claim_payments", "claim_documents",
    "claim_assessments", "claim_fraud_flags", "claim_litigations",
    "claim_repairs", "medical_reports", "reinsurance_claims",
    "general_ledger", "invoices", "refunds", "commissions", "tax_records",
    "reserve_estimates", "third_parties", "audit_logs", "complaints",
    "regulatory_filings", "call_center_interactions", "notifications", "system_config",
]


def _normalize(url: str) -> str:
    """Supabase issues postgres:// URLs; SQLAlchemy + psycopg3 need the
    explicit postgresql+psycopg:// scheme."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _psycopg_dsn(url: str) -> str:
    """psycopg.connect() wants a bare postgresql:// DSN, not SQLAlchemy's
    postgresql+psycopg:// driver-qualified form."""
    normalized = _normalize(url)
    return "postgresql://" + normalized[len("postgresql+psycopg://"):]


def get_engine():
    url = SUPABASE_DB_URL
    if not url:
        console.print("[red]✗ SUPABASE_DB_URL not set.[/red]")
        console.print("  Set it in config.py or as an environment variable:")
        console.print("  [cyan]export SUPABASE_DB_URL=postgres://postgres:PASSWORD@db.XXX.supabase.co:5432/postgres[/cyan]")
        sys.exit(1)
    # pool_size covers MAX_WORKERS concurrent table loads each needing a connection
    return create_engine(_normalize(url), pool_pre_ping=True, pool_size=MAX_WORKERS, max_overflow=1)


def _get_worker_raw_conn():
    """One psycopg connection per worker thread, reused across every table
    that thread processes — avoids a fresh TCP+TLS handshake to the pooler
    per table."""
    if not hasattr(_thread_local, "raw_conn") or _thread_local.raw_conn.closed:
        _thread_local.raw_conn = psycopg.connect(_psycopg_dsn(SUPABASE_DB_URL))
        with _all_raw_conns_lock:
            _all_raw_conns.append(_thread_local.raw_conn)
    return _thread_local.raw_conn


def close_all_connections(engine) -> None:
    """Explicitly close every connection this run opened — raw psycopg
    connections held by worker threads, and the SQLAlchemy pool — instead of
    leaving them for garbage collection. Matters here specifically because
    we're operating against a hard-capped connection pool (Supabase
    session-mode pooler, 15 max) and killed/crashed runs already left stale
    sessions occupying slots."""
    with _all_raw_conns_lock:
        for conn in _all_raw_conns:
            if not conn.closed:
                try:
                    conn.close()
                except Exception:
                    pass
        _all_raw_conns.clear()
    if engine is not None:
        engine.dispose()


def create_table_if_not_exists(engine, table_name: str, schema: str) -> None:
    ddl = get_ddl(table_name, schema=schema)
    # Strip the ext_col_start placeholder — actual wide cols were added dynamically.
    # Removing it can leave a dangling comma before the closing paren (invalid
    # SQL) — strip that too, regardless of what comment/blank lines sit between.
    ddl_clean = ddl.replace("ext_col_start       INT DEFAULT 0  -- marker; actual ext cols appended by generator", "")
    ddl_clean = ddl_clean.replace("ext_col_start       INT DEFAULT 0", "")
    ddl_clean = re.sub(r",(\s*(?:--[^\n]*\n\s*)*\);)", r"\1", ddl_clean)
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.execute(text(ddl_clean))
        conn.commit()


def _pg_type_for(dtype) -> str:
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "TIMESTAMP"
    if pd.api.types.is_bool_dtype(dtype):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(dtype):
        return "BIGINT"
    if pd.api.types.is_float_dtype(dtype):
        return "NUMERIC"
    return "TEXT"


def ensure_extra_columns(engine, table_name: str, schema: str, df: pd.DataFrame) -> None:
    """Wide tables' dynamically-generated extra columns (cust_score_001, etc.)
    aren't in the static DDL — only a placeholder marker is, and that gets
    stripped. Add whatever columns the DataFrame has that the table doesn't,
    inferring type from pandas dtype. No-op for narrow tables."""
    with engine.connect() as conn:
        existing_cols = set(conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        ), {"schema": schema, "table": table_name}).scalars().all())

        missing = [c for c in df.columns if c not in existing_cols]
        if missing:
            # One ALTER TABLE with all ADD COLUMN clauses, not one statement
            # per column — wide tables can have 200-300 extra columns, and
            # that many round-trips risks tripping the pooler's per-statement
            # timeout under concurrent load.
            clauses = ", ".join(
                f'ADD COLUMN IF NOT EXISTS "{col}" {_pg_type_for(df[col].dtype)}'
                for col in missing
            )
            conn.execute(text(f"ALTER TABLE {schema}.{table_name} {clauses}"))
            conn.commit()


def load_table(engine, table_name: str, dry_run: bool = False, schema: str = DEMO_SCHEMA) -> bool:
    parquet_path = OUTPUT_DIR / f"{table_name}.parquet"

    if not parquet_path.exists():
        console.print(f"  [yellow]⚠  {table_name:<40} parquet not found — run generate.py first[/yellow]")
        return False

    df = pd.read_parquet(parquet_path)
    total_rows = len(df)

    # Nullable integer columns (optional FKs, etc.) come back as float64 in
    # pandas — NaN forces the whole column to float — so "150" renders as
    # "150.0", which Postgres's strict COPY text format rejects for an
    # INTEGER column. Any float column whose non-null values are all whole
    # numbers gets promoted to pandas' nullable Int64 (preserves NaN as NA,
    # prints clean integers). A genuinely fractional numeric column never
    # matches the all-integral check, so this is a no-op for real decimals.
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            non_null = df[col].dropna()
            if len(non_null) and (non_null % 1 == 0).all():
                df[col] = df[col].astype("Int64")

    # Some date/timestamp-named columns come back as plain strings (pandas'
    # dedicated string dtype) — coerce to real datetimes. Columns holding
    # dict/list values (JSONB in the DDL) need JSON-serializing — COPY's
    # text-format wire protocol needs valid JSON text, not a Python repr.
    for col in df.columns:
        if col.endswith(("_at", "_date")):
            df[col] = pd.to_datetime(df[col], errors="coerce")
        else:
            sample = df[col].dropna()
            if len(sample) and isinstance(sample.iloc[0], (dict, list)):
                df[col] = df[col].apply(lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v)

    if dry_run:
        console.print(f"  [dim]DRY  {table_name:<40} {total_rows:>10,} rows  [{parquet_path.stat().st_size / 1024 / 1024:.1f} MB][/dim]")
        return True

    console.print(f"  [cyan]↑    {table_name:<40}[/cyan] {total_rows:,} rows...", end="")
    t0 = time.perf_counter()

    try:
        # Create table schema
        create_table_if_not_exists(engine, table_name, schema)
        ensure_extra_columns(engine, table_name, schema, df)

        # Check if already loaded. A prior interrupted run can leave a table
        # partially loaded — nonzero but short of target — which must NOT be
        # treated as done, or it's silently stuck incomplete forever.
        target = ROW_COUNTS.get(table_name, total_rows)
        with engine.connect() as conn:
            existing = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.{table_name}")).scalar()

        if existing and existing >= target:
            console.print(f" [yellow]already has {existing:,} rows — skipping[/yellow]")
            return True

        if existing and 0 < existing < target:
            console.print(f" [yellow]partial ({existing:,}/{target:,}) — truncating and reloading[/yellow]")
            with engine.connect() as conn:
                conn.execute(text(f"TRUNCATE TABLE {schema}.{table_name}"))
                conn.commit()

        # Stream via COPY rather than parameterized INSERT — no 65535
        # bind-parameter ceiling (irrelevant for wide 200+-column tables),
        # and dramatically faster over a network connection. Connection is
        # reused across this worker's tables, not reopened per table.
        df_clean = df.astype(object).where(pd.notnull(df), None)
        cols = list(df_clean.columns)
        col_list = ", ".join(f'"{c}"' for c in cols)
        raw_conn = _get_worker_raw_conn()
        with raw_conn.cursor() as cur:
            with cur.copy(f"COPY {schema}.{table_name} ({col_list}) FROM STDIN") as copy:
                for row in df_clean.itertuples(index=False, name=None):
                    copy.write_row(row)
        raw_conn.commit()

        elapsed = time.perf_counter() - t0
        rate = total_rows / elapsed
        console.print(f" [green]✓[/green] {elapsed:.1f}s  ({rate:,.0f} rows/s)")
        return True

    except Exception as e:
        # Reused connection would stay in an aborted-transaction state for
        # this worker's next table otherwise.
        if hasattr(_thread_local, "raw_conn") and not _thread_local.raw_conn.closed:
            _thread_local.raw_conn.rollback()
        elapsed = time.perf_counter() - t0
        console.print(f" [red]✗ FAILED after {elapsed:.1f}s: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Load parquet files into Supabase")
    parser.add_argument("--table",   help="Load a single table by name")
    parser.add_argument("--dry-run", action="store_true", help="Validate parquets without loading")
    parser.add_argument("--truncate", action="store_true", help="Truncate tables before loading (careful!)")
    args = parser.parse_args()

    console.rule("[bold blue]Supabase Loader[/bold blue]")

    tables = [args.table] if args.table else LOAD_ORDER
    engine = None if args.dry_run else get_engine()

    if args.truncate and not args.dry_run:
        console.print("[yellow]⚠  --truncate will DELETE all existing data. Ctrl+C to abort...[/yellow]")
        time.sleep(3)
        with engine.connect() as conn:
            for t in reversed(tables):  # reverse to respect FK order
                try:
                    conn.execute(text(f"TRUNCATE TABLE {DEMO_SCHEMA}.{t} CASCADE"))
                except Exception:
                    pass
            conn.commit()
        console.print("[green]Truncated.[/green]")

    t_start = time.perf_counter()

    console.print(f"\n[bold]Loading {len(tables)} tables → Supabase[/bold]\n")
    try:
        if args.dry_run or len(tables) == 1:
            results = [load_table(engine, t, dry_run=args.dry_run) for t in tables]
        else:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                results = list(executor.map(lambda t: load_table(engine, t, dry_run=args.dry_run), tables))
    finally:
        # Explicit cleanup, not garbage collection — we're operating against
        # a hard-capped connection pool (15 max), so every connection this
        # run opened must be released, success or failure.
        close_all_connections(engine)

    ok = sum(1 for r in results if r)
    fail = sum(1 for r in results if not r)

    elapsed = time.perf_counter() - t_start
    console.rule()
    console.print(f"\n[bold green]Done.[/bold green] {ok} loaded, {fail} failed — {elapsed:.1f}s total")


if __name__ == "__main__":
    main()
