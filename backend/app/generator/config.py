"""
Central configuration for data generation.
Adjust ROW_COUNTS to scale up/down within Supabase free tier (~500MB).
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
OUTPUT_DIR  = BASE_DIR / "output"
MANIFEST    = BASE_DIR / "manifest.json"

OUTPUT_DIR.mkdir(exist_ok=True)

# ── Reproducibility ────────────────────────────────────────────────────────
RANDOM_SEED = 42

# ── Row counts ─────────────────────────────────────────────────────────────
# Deep tables: high row count, narrower
# Wide tables: lower row count, many columns (300-500)
# Normal tables: moderate row count, standard width
#
# Tuned to stay within Supabase free tier 500MB limit.

ROW_COUNTS = {

    # ── CUSTOMERS & PARTIES ────────────────────────────────────────────────
    "customers":                  80_000,   # WIDE
    "customer_addresses":        120_000,   # normal (intentional redundancy)
    "customer_contacts":          80_000,   # normal
    "beneficiaries":              60_000,   # normal
    "agents":                      2_000,   # normal (small lookup)
    "agent_performance":         300_000,   # DEEP
    "third_parties":              30_000,   # normal
    "employers":                  10_000,   # normal

    # ── POLICIES ──────────────────────────────────────────────────────────
    "policies":                   50_000,   # WIDE
    "policy_versions":           350_000,   # DEEP (every change = row)
    "policy_endorsements":        40_000,   # normal
    "policy_documents":           90_000,   # normal
    "policy_payments":           400_000,   # DEEP
    "policy_cancellations":       15_000,   # normal
    "policy_renewals":            35_000,   # normal
    "coverage_details":           50_000,   # WIDE
    "products":                      150,   # normal (small catalog)
    "product_pricing_rules":       5_000,   # normal

    # ── CLAIMS ────────────────────────────────────────────────────────────
    "claims":                     30_000,   # WIDE
    "claim_events":              500_000,   # DEEP (deepest table)
    "claim_payments":            200_000,   # DEEP
    "claim_documents":            80_000,   # normal
    "claim_assessments":          30_000,   # normal
    "claim_fraud_flags":           8_000,   # normal
    "claim_litigations":           3_000,   # normal
    "repair_shops":                2_000,   # normal (lookup)
    "claim_repairs":              25_000,   # normal
    "medical_reports":            12_000,   # normal

    # ── UNDERWRITING & RISK ───────────────────────────────────────────────
    "underwriting_assessments":   50_000,   # WIDE
    "risk_scores":               450_000,   # DEEP (score logged over time)
    "quote_attempts":            200_000,   # DEEP (most abandoned)
    "credit_checks":              60_000,   # normal
    "inspection_reports":         20_000,   # normal
    "exclusions":                 40_000,   # normal
    "reinsurance_treaties":          500,   # normal (small)
    "reinsurance_claims":          8_000,   # normal

    # ── FINANCE & ACCOUNTING ──────────────────────────────────────────────
    "general_ledger":            500_000,   # DEEP (every posting)
    "invoices":                   55_000,   # normal
    "refunds":                    10_000,   # normal
    "commissions":               150_000,   # DEEP
    "tax_records":                50_000,   # normal
    "reserve_estimates":          30_000,   # normal
    "financial_periods":             120,   # normal (lookup ~10 years monthly)

    # ── OPERATIONS & COMPLIANCE ───────────────────────────────────────────
    "audit_logs":                500_000,   # DEEP
    "complaints":                  8_000,   # normal
    "regulatory_filings":          3_000,   # normal
    "compliance_checks":          70_000,   # normal
    "call_center_interactions":  300_000,   # DEEP
    "notifications":             200_000,   # normal
    "system_config":               2_000,   # WIDE (wide config/legacy table)
}

# ── Wide table column counts ───────────────────────────────────────────────
# How many extra generated columns each "wide" table gets on top of its core cols
WIDE_EXTRA_COLUMNS = {
    "customers":                  200,
    "policies":                   250,
    "coverage_details":           300,
    "underwriting_assessments":   280,
    "claims":                     220,
    "system_config":              350,
}

# ── Locale & fake data ─────────────────────────────────────────────────────
FAKER_LOCALE = "en_US"

# ── Business logic constants ───────────────────────────────────────────────
CLAIM_RATE          = 0.38   # ~38% of policies ever have a claim
FRAUD_RATE          = 0.03   # ~3% of claims flagged
CANCELLATION_RATE   = 0.18   # ~18% of policies cancelled before expiry
RENEWAL_RATE        = 0.72   # ~72% of eligible policies renew
QUOTE_CONVERSION    = 0.25   # ~25% of quotes convert to policies

# Date range for all generated data
DATA_START_YEAR = 2015
DATA_END_YEAR   = 2024

# ── Connector (filled when Supabase is ready) ──────────────────────────────
SUPABASE_URL      = ""   # e.g. https://xxxx.supabase.co
SUPABASE_DB_URL   = ""   # postgres://postgres:password@db.xxxx.supabase.co:5432/postgres
BATCH_SIZE        = 5_000   # rows per insert batch to Supabase
DEMO_SCHEMA       = "demo"  # Postgres schema the generated insurance data loads into
