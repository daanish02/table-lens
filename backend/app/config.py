"""Cross-cutting tunables for the backend. Local, low-impact constants stay
in the file that uses them instead of being promoted here."""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Database ──────────────────────────────────────────────────────────────
DB_URL = os.getenv("SUPABASE_DB_URL", "")
DEMO_SCHEMA = "demo"           # generated insurance data
PRODUCT_SCHEMA = "public"      # table-lens's own tables (pgvector, saved_charts, dashboards)

# ── Discovery ─────────────────────────────────────────────────────────────
DISCOVERY_SAMPLE_PCT = 2.0             # TABLESAMPLE BERNOULLI(%) for large tables
DISCOVERY_LARGE_TABLE_ROWS = 50_000    # tables above this row count get sampled, not scanned
DISCOVERY_TOP_N_CATEGORICAL = 10       # top-N values captured per categorical column
DISCOVERY_FK_OVERLAP_SAMPLE = 1000     # rows sampled for FK-overlap inference
DISCOVERY_FK_OVERLAP_THRESHOLD = 0.90  # % overlap required to infer a relationship

# ── LLM / embeddings (LangChain — provider is a config swap, never hardcoded) ─
# LLM goes through OpenRouter's OpenAI-compatible endpoint; embeddings go
# direct to OpenAI (OpenRouter has no embeddings endpoint).
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = "anthropic/claude-sonnet-4.6"   # OpenRouter model slug
LLM_MAX_RETRIES = 3
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# ── API ───────────────────────────────────────────────────────────────────
RATE_LIMIT = "20/minute"
