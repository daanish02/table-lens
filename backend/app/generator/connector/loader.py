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
import sys
import time
from pathlib import Path

import pandas as pd
from rich.console import Console
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

# Allow env var override
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL") or ""

# Import after env load
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import OUTPUT_DIR, BATCH_SIZE, DEMO_SCHEMA
from schema.ddl import get_ddl, all_table_names

console = Console()

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


def get_engine():
    url = SUPABASE_DB_URL
    if not url:
        console.print("[red]✗ SUPABASE_DB_URL not set.[/red]")
        console.print("  Set it in config.py or as an environment variable:")
        console.print("  [cyan]export SUPABASE_DB_URL=postgres://postgres:PASSWORD@db.XXX.supabase.co:5432/postgres[/cyan]")
        sys.exit(1)
    return create_engine(url, pool_pre_ping=True)


def create_table_if_not_exists(engine, table_name: str, schema: str) -> None:
    ddl = get_ddl(table_name, schema=schema)
    # Strip the ext_col_start placeholder — actual wide cols were added dynamically
    ddl_clean = ddl.replace("ext_col_start       INT DEFAULT 0  -- marker; actual ext cols appended by generator", "")
    ddl_clean = ddl_clean.replace("ext_col_start       INT DEFAULT 0", "")
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.execute(text(ddl_clean))
        conn.commit()


def load_table(engine, table_name: str, dry_run: bool = False, schema: str = DEMO_SCHEMA) -> bool:
    parquet_path = OUTPUT_DIR / f"{table_name}.parquet"

    if not parquet_path.exists():
        console.print(f"  [yellow]⚠  {table_name:<40} parquet not found — run generate.py first[/yellow]")
        return False

    df = pd.read_parquet(parquet_path)
    total_rows = len(df)

    if dry_run:
        console.print(f"  [dim]DRY  {table_name:<40} {total_rows:>10,} rows  [{parquet_path.stat().st_size / 1024 / 1024:.1f} MB][/dim]")
        return True

    console.print(f"  [cyan]↑    {table_name:<40}[/cyan] {total_rows:,} rows...", end="")
    t0 = time.perf_counter()

    try:
        # Create table schema
        create_table_if_not_exists(engine, table_name, schema)

        # Check if already loaded
        with engine.connect() as conn:
            count_result = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.{table_name}"))
            existing = count_result.scalar()

        if existing and existing > 0:
            console.print(f" [yellow]already has {existing:,} rows — skipping[/yellow]")
            return True

        # Load in batches
        n_batches = (total_rows + BATCH_SIZE - 1) // BATCH_SIZE
        for i in range(n_batches):
            chunk = df.iloc[i * BATCH_SIZE:(i + 1) * BATCH_SIZE]
            chunk.to_sql(
                table_name,
                engine,
                schema=schema,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=500,
            )

        elapsed = time.perf_counter() - t0
        rate = total_rows / elapsed
        console.print(f" [green]✓[/green] {elapsed:.1f}s  ({rate:,.0f} rows/s)")
        return True

    except Exception as e:
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
    ok = 0
    fail = 0

    console.print(f"\n[bold]Loading {len(tables)} tables → Supabase[/bold]\n")
    for table_name in tables:
        result = load_table(engine, table_name, dry_run=args.dry_run)
        if result:
            ok += 1
        else:
            fail += 1

    elapsed = time.perf_counter() - t_start
    console.rule()
    console.print(f"\n[bold green]Done.[/bold green] {ok} loaded, {fail} failed — {elapsed:.1f}s total")


if __name__ == "__main__":
    main()
