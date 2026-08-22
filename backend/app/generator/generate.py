"""
Main entry point for data generation.

Usage:
    uv run generate.py                     # generate all tables (skips already-done)
    uv run generate.py --table customers   # regenerate one specific table
    uv run generate.py --reset-all         # clear manifest and regenerate everything
    uv run generate.py --status            # show manifest status

Idempotency:
    Each table is skipped if:
      - its parquet file already exists
      - the schema hash hasn't changed
      - the row count config hasn't changed
"""

import argparse
import sys
import time

from rich.console import Console
from rich.table import Table
from rich import print as rprint

from config import OUTPUT_DIR, ROW_COUNTS
from schema.ddl import get_ddl, all_table_names
from idempotency.checks import should_skip, mark_done, reset_all, reset_table, status
from generators.base import save_parquet

# ── Import all generators ──────────────────────────────────────────────────
from generators.customers import CUSTOMER_GENERATORS
from generators.policies import POLICY_GENERATORS
from generators.claims import CLAIM_GENERATORS
from generators.underwriting import UNDERWRITING_GENERATORS
from generators.finance_ops import FINANCE_GENERATORS, OPS_GENERATORS

ALL_GENERATORS: dict = {
    **CUSTOMER_GENERATORS,
    **POLICY_GENERATORS,
    **CLAIM_GENERATORS,
    **UNDERWRITING_GENERATORS,
    **FINANCE_GENERATORS,
    **OPS_GENERATORS,
}

console = Console()


def generate_table(table_name: str, force: bool = False) -> bool:
    """
    Generate data for one table.
    Returns True if generated, False if skipped.
    """
    if table_name not in ALL_GENERATORS:
        console.print(f"[red]✗ No generator found for '{table_name}'[/red]")
        return False

    ddl         = get_ddl(table_name)
    row_count   = ROW_COUNTS.get(table_name, 0)
    parquet_path = OUTPUT_DIR / f"{table_name}.parquet"

    if not force and should_skip(table_name, ddl, row_count, parquet_path):
        console.print(f"  [dim]↷  {table_name:<40} skipped (unchanged)[/dim]")
        return False

    console.print(f"  [cyan]⟳  {table_name:<40}[/cyan] generating {row_count:,} rows...", end="")
    t0 = time.perf_counter()

    try:
        generator = ALL_GENERATORS[table_name]
        df = generator()
        save_parquet(df, parquet_path)
        elapsed = time.perf_counter() - t0
        actual_rows = len(df)
        console.print(f" [green]✓[/green] {actual_rows:,} rows in {elapsed:.1f}s  [{parquet_path.stat().st_size / 1024 / 1024:.1f} MB]")
        mark_done(table_name, ddl, row_count, parquet_path)
        return True

    except Exception as e:
        elapsed = time.perf_counter() - t0
        console.print(f" [red]✗ FAILED after {elapsed:.1f}s: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


def show_status() -> None:
    manifest = status()
    t = Table(title="Generation Manifest", show_lines=True)
    t.add_column("Table", style="cyan")
    t.add_column("Rows", justify="right")
    t.add_column("Size", justify="right")
    t.add_column("Generated At", style="dim")
    t.add_column("Parquet", style="dim")

    for table_name in all_table_names():
        if table_name in manifest:
            entry = manifest[table_name]
            from pathlib import Path
            p = Path(entry["parquet_path"])
            size = f"{p.stat().st_size / 1024 / 1024:.1f} MB" if p.exists() else "[red]missing[/red]"
            t.add_row(
                table_name,
                f"{entry['row_count']:,}",
                size,
                entry["generated_at"][:19],
                "✓" if p.exists() else "✗",
            )
        else:
            t.add_row(table_name, str(ROW_COUNTS.get(table_name, "?")), "-", "[dim]not generated[/dim]", "")

    console.print(t)


def main() -> None:
    parser = argparse.ArgumentParser(description="Insurance synthetic data generator")
    parser.add_argument("--table",     help="Generate (or re-generate) a single table by name")
    parser.add_argument("--reset-all", action="store_true", help="Clear manifest and regenerate everything")
    parser.add_argument("--reset",     help="Reset a single table's manifest entry")
    parser.add_argument("--status",    action="store_true", help="Show manifest status")
    parser.add_argument("--force",     action="store_true", help="Force regeneration even if unchanged")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.reset_all:
        reset_all()

    if args.reset:
        reset_table(args.reset)

    console.rule("[bold blue]Insurance Data Generator[/bold blue]")

    # ── Determine generation order ─────────────────────────────────────────
    # Order matters: parent tables before child tables
    GENERATION_ORDER = [
        # Lookups / parents first
        "financial_periods",
        "products",
        "repair_shops",
        "employers",
        "agents",
        "reinsurance_treaties",
        # Core entities
        "customers",
        "customer_addresses",
        "customer_contacts",
        "credit_checks",
        "compliance_checks",
        "risk_scores",
        # Policies and related
        "policies",
        "policy_versions",
        "policy_endorsements",
        "policy_documents",
        "policy_payments",
        "policy_cancellations",
        "policy_renewals",
        "coverage_details",
        "product_pricing_rules",
        "quote_attempts",
        "underwriting_assessments",
        "inspection_reports",
        "exclusions",
        "beneficiaries",
        # Agent performance
        "agent_performance",
        # Claims and related
        "claims",
        "claim_events",
        "claim_payments",
        "claim_documents",
        "claim_assessments",
        "claim_fraud_flags",
        "claim_litigations",
        "claim_repairs",
        "medical_reports",
        "reinsurance_claims",
        # Finance
        "general_ledger",
        "invoices",
        "refunds",
        "commissions",
        "tax_records",
        "reserve_estimates",
        # Operations
        "third_parties",
        "audit_logs",
        "complaints",
        "regulatory_filings",
        "call_center_interactions",
        "notifications",
        "system_config",
    ]

    tables_to_run = [args.table] if args.table else GENERATION_ORDER

    # Validate
    for t in tables_to_run:
        if t not in ALL_GENERATORS:
            console.print(f"[red]Unknown table: '{t}'. Available:[/red]")
            for name in ALL_GENERATORS:
                console.print(f"  {name}")
            sys.exit(1)

    # ── Run ────────────────────────────────────────────────────────────────
    t_start   = time.perf_counter()
    generated = 0
    skipped   = 0
    failed    = 0

    console.print(f"\n[bold]Generating {len(tables_to_run)} tables → {OUTPUT_DIR}[/bold]\n")

    for table_name in tables_to_run:
        result = generate_table(table_name, force=args.force)
        if result is True:
            generated += 1
        elif result is False and should_skip(
            table_name, get_ddl(table_name),
            ROW_COUNTS.get(table_name, 0),
            OUTPUT_DIR / f"{table_name}.parquet"
        ):
            skipped += 1
        else:
            # May be skipped or generated — just count what printed
            pass

    total_time = time.perf_counter() - t_start

    # Summary
    console.rule()

    # Total parquet size
    total_mb = sum(
        (OUTPUT_DIR / f"{t}.parquet").stat().st_size
        for t in tables_to_run
        if (OUTPUT_DIR / f"{t}.parquet").exists()
    ) / 1024 / 1024

    console.print(f"\n[bold green]Done.[/bold green] Total time: {total_time:.1f}s | Output size: {total_mb:.1f} MB")
    console.print(f"  Parquet files: {OUTPUT_DIR}")
    console.print(f"\n[dim]Next step: set SUPABASE_DB_URL in config.py then run:[/dim]")
    console.print(f"  [cyan]uv run connector/loader.py[/cyan]")


if __name__ == "__main__":
    main()
