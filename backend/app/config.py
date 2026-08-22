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
DISCOVERY_PROFILE_CONCURRENCY = 6      # concurrent tables profiled at once (DB-bound, not LLM-bound)
DISCOVERY_PROFILE_BATCH_SIZE = 40      # columns per mega-query — keeps a single SELECT's expression
                                        # list bounded even for the widest tables (300+ columns)

# ── LLM / embeddings (LangChain — provider is a config swap, never hardcoded) ─
# Both LLM and embeddings go through OpenRouter's OpenAI-compatible endpoint —
# one API key, one base URL, model is just a string swap.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = "deepseek/deepseek-v4-flash-0731"       # OpenRouter model slug
LLM_MAX_RETRIES = 3
LLM_MAX_TOKENS = 4000                               # deepseek-v4-flash spends a variable amount on
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
