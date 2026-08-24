"""Cross-cutting tunables for the backend. Local, low-impact constants stay
in the file that uses them instead of being promoted here."""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Database ──────────────────────────────────────────────────────────────
DB_URL = os.getenv("SUPABASE_DB_URL", "")
DEMO_SCHEMA = "demo"           # generated insurance data
PRODUCT_SCHEMA = "public"      # Table Lens's own tables (pgvector, saved_charts, dashboards)

# ── Discovery ─────────────────────────────────────────────────────────────
DISCOVERY_SAMPLE_PCT = 2.0             # TABLESAMPLE BERNOULLI(%) for large tables
DISCOVERY_LARGE_TABLE_ROWS = 50_000    # tables above this row count get sampled, not scanned
DISCOVERY_TOP_N_CATEGORICAL = 10       # top-N values captured per categorical column
DISCOVERY_FK_OVERLAP_SAMPLE = 1000     # rows sampled for FK-overlap inference
DISCOVERY_FK_OVERLAP_THRESHOLD = 0.90  # % overlap required to infer a relationship
DISCOVERY_DESCRIBE_CONCURRENCY = 8     # concurrent column-description LLM calls per table
DISCOVERY_PROFILE_CONCURRENCY = 4      # concurrent tables profiled at once (DB-bound, not LLM-bound).
                                        # Each concurrently-profiling thread holds one DB connection at
                                        # a time — must stay <= the engine's pool capacity (pool_size=4,
                                        # max_overflow=1 = 5 total, see db/connection.py) or profiling
                                        # deterministically exhausts the pool under any real latency
                                        # (seen in prod: "QueuePool limit of size 4 overflow 1 reached").
                                        # Left one connection of headroom under that cap on purpose.
DISCOVERY_PROFILE_BATCH_SIZE = 40      # columns per mega-query — keeps a single SELECT's expression
                                        # list bounded even for the widest tables (300+ columns)
DISCOVERY_HISTOGRAM_MAX_BUCKETS = 20   # numeric-column histograms use min(this, distinct_count)
                                        # buckets — a column with 5 distinct values gets 5 buckets
                                        # (exact), not 20 mostly-empty ones
DISCOVERY_STALE_RUN_MINUTES = 60       # a 'running' row older than this with no path left to call
                                        # mark_failed (process crashed/redeployed mid-run) is treated
                                        # as orphaned, not genuinely active — otherwise it blocks every
                                        # future run forever with a 409

# ── LLM / embeddings (LangChain — provider is a config swap, never hardcoded) ─
# Both LLM and embeddings go through OpenRouter's OpenAI-compatible endpoint —
# one API key, one base URL, model is just a string swap.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = "deepseek/deepseek-v4-flash-0731"       # OpenRouter model slug
LLM_MAX_RETRIES = 3
LLM_MAX_TOKENS = 6000                                # deepseek-v4-flash spends a variable amount on
                                                     # internal reasoning before any answer text — a
                                                     # truncated call (empty output) wastes the whole
                                                     # request and needs a retry, which costs more than
                                                     # generous headroom on a cheap model. The old
                                                     # unbounded default (65536) ran fine per-call; this
                                                     # just caps a single pathological runaway, not the
                                                     # normal case.
EMBEDDING_MODEL = "openai/text-embedding-3-small"   # OpenRouter model slug
EMBEDDING_DIM = 768                                 # truncated via dimensions= (native is 1536)

# ── API ───────────────────────────────────────────────────────────────────
RATE_LIMIT = "20/minute"
# Comma-separated in prod (e.g. "https://tablelens.yourdomain.com"). Falls
# back to local dev ports when unset.
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()
]
