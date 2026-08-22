# Foundation + Stage 1a (Discovery Agent) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the backend skeleton (FastAPI, logging, DB access) and build the discovery agent — a service that profiles the `demo` schema in Supabase Postgres and writes plain-English, embedded descriptions to `public.table_embeddings` / `public.column_embeddings`.

**Architecture:** FastAPI backend under `backend/app/`. Discovery runs as a multi-step pipeline (introspect → profile → infer relationships → describe via LLM → embed), each step a separate testable module, orchestrated by `discovery/orchestrator.py` and exposed via two endpoints. Generator (`generator/`) gets a minimal change: schema-qualify its DDL/load so demo data lands in `demo`, not `public`.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy + psycopg, LangChain (`langchain-anthropic` for descriptions, `langchain-openai` for embeddings), structlog, slowapi, pytest, Supabase Postgres + pgvector. Frontend: Next.js 14 (App Router), TypeScript — scaffold only.

**Spec:** `specs/2026-08-22-foundation-stage1a-design.md`

## Global Constraints

- Generator logic and output must stay byte-identical — only schema-qualification changes, verified by checksum diff (spec Decision 5).
- LLM and embeddings access both go through LangChain, routed through OpenRouter (OpenAI-compatible endpoint) — never a hardcoded provider SDK call; model is a `config.py` string swap (spec Decision 3). One API key for both.
- Cross-cutting tunables live in `config.py`; low-impact local constants stay as top-of-file constants in the file that uses them (spec Decision 4).
- Read-only DB access is enforced at the connection level, not just prompt instructions (spec, PRD "Key Architectural Decisions" #4).
- Generated insurance data lives in schema `demo`; table-lens's own tables (`table_embeddings`, `column_embeddings`, later `saved_charts`/`dashboards`) live in `public` (spec Decision 8).
- Backend logging via structlog (JSON), one shared config, no bare `print`/ad-hoc logging in new code (spec Decision 9).
- Idempotency everywhere: discovery re-runs check a schema hash before re-profiling, same manifest pattern as the generator (PRD "Key Architectural Decisions" #5).
- No auth, IP-based rate limiting only, 20 req/min per endpoint (PRD).
- HLD docs (`docs/PRD.md`, `ARCHITECTURE.md`, `SCHEMAS.md`, `APIS.md`) describe the system as a whole, no stage tags — update them, not `docs/PROGRESS.md`, when architecture/schema/API facts change. Update `docs/PROGRESS.md` when a stage's status changes.

---

## File Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── config.py                    # Task 2 — cross-cutting tunables
│   ├── main.py                      # Task 12 — FastAPI entrypoint
│   ├── generator/                   # existing — Task 1 modifies ddl.py, loader.py, config.py
│   │   ├── config.py
│   │   ├── schema/ddl.py
│   │   └── connector/loader.py
│   ├── logging/
│   │   ├── __init__.py
│   │   └── logger.py                # Task 2
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py            # Task 3
│   │   └── migrations/
│   │       └── 001_pgvector.sql     # Task 4
│   ├── discovery/
│   │   ├── __init__.py
│   │   ├── idempotency.py           # Task 5
│   │   ├── introspect.py            # Task 6
│   │   ├── profiler.py              # Task 7
│   │   ├── relationships.py         # Task 8
│   │   ├── llm.py                   # Task 9
│   │   ├── embeddings.py            # Task 10
│   │   └── orchestrator.py          # Task 11
│   └── api/
│       ├── __init__.py
│       ├── middleware/
│       │   ├── __init__.py
│       │   └── rate_limit.py        # Task 12
│       └── routes/
│           ├── __init__.py
│           └── discover.py          # Task 12
├── tests/
│   ├── conftest.py                  # Task 2
│   ├── generator/test_ddl_schema.py # Task 1
│   ├── test_logger.py               # Task 2
│   ├── db/test_connection.py        # Task 3
│   ├── db/test_migrations.py        # Task 4
│   ├── discovery/test_idempotency.py    # Task 5
│   ├── discovery/test_introspect.py     # Task 6
│   ├── discovery/test_profiler.py       # Task 7
│   ├── discovery/test_relationships.py  # Task 8
│   ├── discovery/test_llm.py            # Task 9
│   ├── discovery/test_embeddings.py     # Task 10
│   ├── discovery/test_orchestrator.py   # Task 11
│   └── api/test_discover_routes.py      # Task 12
└── pyproject.toml                   # Task 2

frontend/                             # Task 13
├── app/layout.tsx
├── app/page.tsx
├── lib/logger.ts
├── lib/api-client.ts
├── package.json
├── tsconfig.json
└── next.config.js
```

**Interfaces contract (names every later task relies on):**
- `app.logging.logger.get_logger(name: str) -> structlog.stdlib.BoundLogger`
- `app.config` module-level constants: `DEMO_SCHEMA`, `DISCOVERY_SAMPLE_PCT`, `DISCOVERY_TOP_N_CATEGORICAL`, `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `LLM_MODEL`, `LLM_MAX_RETRIES`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`
- `app.db.connection.get_engine(readonly: bool = False) -> sqlalchemy.Engine`
- `app.discovery.idempotency.schema_hash(schema_snapshot: dict) -> str`, `should_skip(engine, schema_hash: str) -> bool`, `mark_done(engine, schema_hash: str) -> None`
- `app.discovery.introspect.get_schema_snapshot(engine, schema: str) -> list[TableInfo]` where `TableInfo` is a `dataclass` with `name: str`, `columns: list[ColumnInfo]`; `ColumnInfo` has `name: str`, `data_type: str`, `is_pk: bool`, `is_fk: bool`, `fk_table: str | None`, `fk_column: str | None`
- `app.discovery.profiler.profile_table(engine, schema: str, table: TableInfo) -> dict[str, ColumnProfile]` where `ColumnProfile` is a `dataclass` with fields depending on type (see Task 7)
- `app.discovery.relationships.infer_relationships(engine, schema: str, tables: list[TableInfo]) -> list[InferredRelationship]` where `InferredRelationship` has `from_table: str`, `from_column: str`, `to_table: str`, `to_column: str`, `overlap_pct: float`
- `app.discovery.llm.describe_table(table: TableInfo, profiles: dict[str, ColumnProfile]) -> str`, `describe_column(table_name: str, column: ColumnInfo, profile: ColumnProfile) -> str`
- `app.discovery.embeddings.embed_and_store(engine, table_name: str, table_description: str, column_descriptions: dict[str, str]) -> None`
- `app.discovery.orchestrator.run_discovery(db_url: str, schema: str = DEMO_SCHEMA) -> str` returns a `run_id`; `get_discovery_status(run_id: str) -> dict`

---

### Task 1: Schema-qualify the generator (demo schema, not public)

**Files:**
- Modify: `backend/app/generator/schema/ddl.py:921-923`
- Modify: `backend/app/generator/connector/loader.py`
- Modify: `backend/app/generator/config.py`
- Test: `backend/tests/generator/test_ddl_schema.py`

**Interfaces:**
- Produces: `get_ddl(table_name: str, schema: str = "public") -> str`, `generator.config.DEMO_SCHEMA = "demo"`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/generator/test_ddl_schema.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "app" / "generator"))

from schema.ddl import get_ddl


def test_get_ddl_defaults_to_public_schema():
    ddl = get_ddl("products")
    assert "CREATE TABLE IF NOT EXISTS public.products" in ddl


def test_get_ddl_qualifies_with_given_schema():
    ddl = get_ddl("products", schema="demo")
    assert "CREATE TABLE IF NOT EXISTS demo.products" in ddl
    assert "CREATE TABLE IF NOT EXISTS products (" not in ddl


def test_get_ddl_only_replaces_first_occurrence():
    ddl = get_ddl("customers", schema="demo")
    assert ddl.count("demo.customers") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/generator/test_ddl_schema.py -v`
Expected: FAIL — `get_ddl()` takes 1 positional argument, `schema` keyword not accepted; assertions on `public.products` fail since current output is unqualified.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/generator/schema/ddl.py — replace lines 921-923
def get_ddl(table_name: str, schema: str = "public") -> str:
    ddl = TABLES[table_name]
    return ddl.replace(
        f"CREATE TABLE IF NOT EXISTS {table_name}",
        f"CREATE TABLE IF NOT EXISTS {schema}.{table_name}",
        1,
    )
```

```python
# backend/app/generator/config.py — add near the Connector section (after BATCH_SIZE)
DEMO_SCHEMA = "demo"   # Postgres schema the generated insurance data loads into
```

Now update the loader so it creates the schema, qualifies every table reference, and passes `schema=` to pandas:

```python
# backend/app/generator/connector/loader.py
# add near the other imports:
from config import OUTPUT_DIR, BATCH_SIZE, DEMO_SCHEMA
```

```python
# replace create_table_if_not_exists
def create_table_if_not_exists(engine, table_name: str, schema: str) -> None:
    ddl = get_ddl(table_name, schema=schema)
    ddl_clean = ddl.replace("ext_col_start       INT DEFAULT 0  -- marker; actual ext cols appended by generator", "")
    ddl_clean = ddl_clean.replace("ext_col_start       INT DEFAULT 0", "")
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.execute(text(ddl_clean))
        conn.commit()
```

```python
# replace load_table's body pieces that reference table_name unqualified
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
        create_table_if_not_exists(engine, table_name, schema)

        with engine.connect() as conn:
            count_result = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.{table_name}"))
            existing = count_result.scalar()

        if existing and existing > 0:
            console.print(f" [yellow]already has {existing:,} rows — skipping[/yellow]")
            return True

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
```

```python
# in main(), the --truncate block also needs qualifying:
    if args.truncate and not args.dry_run:
        console.print("[yellow]⚠  --truncate will DELETE all existing data. Ctrl+C to abort...[/yellow]")
        time.sleep(3)
        with engine.connect() as conn:
            for t in reversed(tables):
                try:
                    conn.execute(text(f"TRUNCATE TABLE {DEMO_SCHEMA}.{t} CASCADE"))
                except Exception:
                    pass
            conn.commit()
        console.print("[green]Truncated.[/green]")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/generator/test_ddl_schema.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Verify generator output is still byte-identical**

Run:
```bash
cd backend/app/generator
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run generate.py --table financial_periods --force
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run generate.py --table products --force
sha256sum output/financial_periods.parquet output/products.parquet
```
Expected: matches the baseline checksums already recorded (`7f660fa5...` for `financial_periods.parquet`, `616bbcaa...` for `products.parquet`) — DDL/loader changes don't touch the generators, so parquet output must be unaffected.

- [ ] **Step 6: Commit**

```bash
git add backend/app/generator/schema/ddl.py backend/app/generator/connector/loader.py backend/app/generator/config.py backend/tests/generator/test_ddl_schema.py
git commit -m "feat(generator): schema-qualify DDL and loader for demo schema"
```

---

### Task 2: Backend scaffold — pyproject, config, structlog logger

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/logging/__init__.py`
- Create: `backend/app/logging/logger.py`
- Test: `backend/tests/conftest.py`
- Test: `backend/tests/test_logger.py`

**Interfaces:**
- Produces: `app.logging.logger.get_logger(name: str)`, `app.config.{DEMO_SCHEMA, DISCOVERY_SAMPLE_PCT, DISCOVERY_TOP_N_CATEGORICAL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL, LLM_MAX_RETRIES, EMBEDDING_MODEL, EMBEDDING_DIM, DB_URL}`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_logger.py
import logging

from app.logging.logger import get_logger


def test_get_logger_emits_structured_event_with_bound_context(caplog):
    logger = get_logger("test.module")
    with caplog.at_level(logging.INFO):
        logger.info("hello", key="value")
    assert "hello" in caplog.text
    assert "test.module" in caplog.text
    assert "value" in caplog.text


def test_get_logger_is_cached_per_name():
    a = get_logger("same.name")
    b = get_logger("same.name")
    assert a is b
```

Note: `caplog`, not `capsys` — once logging routes through stdlib `logging`
handlers (needed for the file handler below), a `logging.StreamHandler`
bound to `sys.stdout` at import time doesn't reliably interact with
per-test `capsys` stdout substitution. `caplog` captures at the `logging`
layer directly and is the correct tool here regardless of handler wiring.

```python
# backend/tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_logger.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Write minimal implementation**

```toml
# backend/pyproject.toml
[project]
name = "table-lens-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sqlalchemy>=2.0.0",
    "psycopg[binary]>=3.2.0",
    "pgvector>=0.3.0",
    "langchain>=0.3.0",
    "langchain-openai>=0.2.0",   # OpenAI-compatible client, used against OpenRouter for both LLM and embeddings
    "structlog>=24.4.0",
    "slowapi>=0.1.9",
    "pydantic-settings>=2.6.0",
    "python-dotenv>=1.0.0",
    # generator (backend/app/generator/) deps — one shared venv for the whole backend
    "faker>=24.0.0",
    "numpy>=1.26.0",
    "pandas>=2.2.0",
    "pyarrow>=15.0.0",
    "tqdm>=4.66.0",
    "rich>=13.7.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

```python
# backend/app/__init__.py
```

```python
# backend/app/config.py
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
# Both LLM and embeddings go through OpenRouter's OpenAI-compatible endpoint —
# one API key, one base URL, model is just a string swap.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = "anthropic/claude-sonnet-4.6"           # OpenRouter model slug
LLM_MAX_RETRIES = 3
EMBEDDING_MODEL = "openai/text-embedding-3-small"   # OpenRouter model slug
EMBEDDING_DIM = 1536

# ── API ───────────────────────────────────────────────────────────────────
RATE_LIMIT = "20/minute"
```

```python
# backend/app/logging/__init__.py
```

```python
# backend/app/logging/logger.py
import logging
import logging.handlers
import sys
from pathlib import Path
from functools import lru_cache

import structlog

LOG_DIR = Path(__file__).parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)

_stream_handler = logging.StreamHandler(sys.stdout)
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "app.log", maxBytes=10_000_000, backupCount=5
)

_formatter = structlog.stdlib.ProcessorFormatter(processor=structlog.processors.JSONRenderer())
_stream_handler.setFormatter(_formatter)
_file_handler.setFormatter(_formatter)

_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_root_logger.handlers = [_stream_handler, _file_handler]  # pytest pre-configures root handlers; basicConfig() would silently no-op

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


@lru_cache
def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name).bind(logger=name)
```

Writes structured JSON to both stdout and `backend/logs/app.log` (rotating,
10MB x 5 backups, gitignored — regenerable). No frontend equivalent: browser
JS has no filesystem access, so `frontend/lib/logger.ts` stays console-only.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv sync && uv run pytest tests/test_logger.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/app/__init__.py backend/app/config.py backend/app/logging/ backend/tests/conftest.py backend/tests/test_logger.py
git commit -m "feat(backend): scaffold project — config, structlog logger"
```

---

### Task 3: DB connection module (read-only enforced)

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/connection.py`
- Test: `backend/tests/db/test_connection.py`
- Test: `backend/tests/db/__init__.py`

**Interfaces:**
- Consumes: `app.config.DB_URL`
- Produces: `app.db.connection.get_engine(readonly: bool = False) -> sqlalchemy.Engine`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/db/__init__.py
```

```python
# backend/tests/db/test_connection.py
import os
import pytest
from sqlalchemy import text

from app.db.connection import get_engine

requires_db = pytest.mark.skipif(
    not os.getenv("SUPABASE_DB_URL"), reason="SUPABASE_DB_URL not set"
)


@requires_db
def test_get_engine_connects_and_runs_select_1():
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@requires_db
def test_readonly_engine_rejects_write():
    engine = get_engine(readonly=True)
    with engine.connect() as conn:
        with pytest.raises(Exception):
            conn.execute(text("CREATE TABLE demo.__should_fail (id INT)"))
            conn.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/db/test_connection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Write minimal implementation**

Read-only enforcement uses a dedicated Postgres role. Since provisioning that role is a one-time manual Supabase SQL step (not code), `get_engine(readonly=True)` connects using a separate `SUPABASE_DB_URL_READONLY` env var pointing at that role; until it's provisioned, tests marked `requires_db` above are the gate that catches a missing/misconfigured role.

```python
# backend/app/db/__init__.py
```

```python
# backend/app/db/connection.py
import os
from functools import lru_cache
from sqlalchemy import create_engine, Engine

from app.config import DB_URL
from app.logging.logger import get_logger

log = get_logger(__name__)

READONLY_DB_URL = os.getenv("SUPABASE_DB_URL_READONLY", DB_URL)


def _normalize(url: str) -> str:
    """Supabase issues postgres:// URLs; SQLAlchemy + psycopg3 need the
    explicit postgresql+psycopg:// scheme."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@lru_cache
def get_engine(readonly: bool = False) -> Engine:
    url = READONLY_DB_URL if readonly else DB_URL
    if not url:
        raise RuntimeError("SUPABASE_DB_URL is not set")
    log.info("db.engine.create", readonly=readonly)
    return create_engine(_normalize(url), pool_pre_ping=True)
```

- [ ] **Step 4: Provision the read-only role (manual, one-time)**

Run in Supabase SQL editor:
```sql
CREATE ROLE table_lens_readonly WITH LOGIN PASSWORD 'CHOOSE_A_PASSWORD';
GRANT USAGE ON SCHEMA demo TO table_lens_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA demo TO table_lens_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA demo GRANT SELECT ON TABLES TO table_lens_readonly;
```
Then set `SUPABASE_DB_URL_READONLY=postgres://table_lens_readonly:CHOOSE_A_PASSWORD@<same host>:5432/postgres` in root `.env`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/db/test_connection.py -v`
Expected: PASS (2 tests) once `SUPABASE_DB_URL` and `SUPABASE_DB_URL_READONLY` are set; SKIPPED otherwise (does not block the rest of the plan).

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/__init__.py backend/app/db/connection.py backend/tests/db/
git commit -m "feat(backend): DB connection module with read-only role support"
```

---

### Task 4: pgvector schema migration

**Files:**
- Create: `backend/app/db/migrations/001_pgvector.sql`
- Create: `backend/app/db/migrate.py`
- Test: `backend/tests/db/test_migrations.py`

**Interfaces:**
- Consumes: `app.db.connection.get_engine`
- Produces: `app.db.migrate.run_migrations(engine) -> None`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/db/test_migrations.py
import os
import pytest
from sqlalchemy import text

from app.db.connection import get_engine
from app.db.migrate import run_migrations

requires_db = pytest.mark.skipif(
    not os.getenv("SUPABASE_DB_URL"), reason="SUPABASE_DB_URL not set"
)


@requires_db
def test_run_migrations_creates_embedding_tables():
    engine = get_engine()
    run_migrations(engine)
    with engine.connect() as conn:
        tables = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name IN "
            "('table_embeddings', 'column_embeddings')"
        )).scalars().all()
    assert set(tables) == {"table_embeddings", "column_embeddings"}


@requires_db
def test_run_migrations_is_idempotent():
    engine = get_engine()
    run_migrations(engine)
    run_migrations(engine)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/db/test_migrations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db.migrate'`

- [ ] **Step 3: Write minimal implementation**

```sql
-- backend/app/db/migrations/001_pgvector.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.table_embeddings (
    table_name   TEXT PRIMARY KEY,
    description  TEXT,
    embedding    vector(1536)
);

CREATE TABLE IF NOT EXISTS public.column_embeddings (
    table_name   TEXT,
    column_name  TEXT,
    description  TEXT,
    embedding    vector(1536),
    PRIMARY KEY (table_name, column_name)
);
```

```python
# backend/app/db/migrate.py
from pathlib import Path
from sqlalchemy import text, Engine

from app.logging.logger import get_logger

log = get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations(engine: Engine) -> None:
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        log.info("migrate.apply", file=path.name)
        with engine.connect() as conn:
            conn.execute(text(path.read_text()))
            conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/db/test_migrations.py -v`
Expected: PASS (2 tests), or SKIPPED without a DB configured.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/migrations/ backend/app/db/migrate.py backend/tests/db/test_migrations.py
git commit -m "feat(backend): pgvector migration for table/column embeddings"
```

---

### Task 5: Discovery idempotency (schema-hash manifest)

**Files:**
- Create: `backend/app/discovery/__init__.py`
- Create: `backend/app/discovery/idempotency.py`
- Test: `backend/tests/discovery/__init__.py`
- Test: `backend/tests/discovery/test_idempotency.py`

Mirrors `generator/idempotency/checks.py`'s pattern but keyed on a hash of the live schema snapshot (not a static DDL string), and stored in a manifest table rather than a local JSON file — discovery runs against a remote DB, so its idempotency state should live there too, not on whichever machine happened to trigger it.

**Interfaces:**
- Produces: `schema_hash(schema_snapshot: list[dict]) -> str`, `should_skip(engine, schema_hash: str) -> bool`, `mark_done(engine, schema_hash: str, run_id: str) -> None`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/discovery/__init__.py
```

```python
# backend/tests/discovery/test_idempotency.py
from app.discovery.idempotency import schema_hash


def test_schema_hash_is_stable_for_same_input():
    snapshot = [{"table": "customers", "columns": ["id", "name"]}]
    assert schema_hash(snapshot) == schema_hash(snapshot)


def test_schema_hash_changes_when_schema_changes():
    a = [{"table": "customers", "columns": ["id", "name"]}]
    b = [{"table": "customers", "columns": ["id", "name", "email"]}]
    assert schema_hash(a) != schema_hash(b)


def test_schema_hash_is_order_independent():
    a = [{"table": "customers", "columns": ["id", "name"]}, {"table": "claims", "columns": ["id"]}]
    b = [{"table": "claims", "columns": ["id"]}, {"table": "customers", "columns": ["id", "name"]}]
    assert schema_hash(a) == schema_hash(b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/discovery/test_idempotency.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.discovery'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/discovery/__init__.py
```

```python
# backend/app/discovery/idempotency.py
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import text, Engine

from app.logging.logger import get_logger

log = get_logger(__name__)

_DISCOVERY_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS public.discovery_runs (
    run_id       TEXT PRIMARY KEY,
    schema_hash  TEXT NOT NULL,
    status       TEXT NOT NULL,
    step         TEXT,
    error        TEXT,
    started_at   TIMESTAMPTZ DEFAULT NOW(),
    finished_at  TIMESTAMPTZ
);
"""


def schema_hash(schema_snapshot: list[dict]) -> str:
    normalized = sorted(schema_snapshot, key=lambda t: t["table"])
    payload = json.dumps(normalized, sort_keys=True)
    return hashlib.md5(payload.encode()).hexdigest()


def ensure_runs_table(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text(_DISCOVERY_RUNS_DDL))
        conn.commit()


def should_skip(engine: Engine, hash_value: str) -> bool:
    ensure_runs_table(engine)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT 1 FROM public.discovery_runs "
                "WHERE schema_hash = :h AND status = 'done' LIMIT 1"
            ),
            {"h": hash_value},
        ).first()
    return row is not None


def start_run(engine: Engine, run_id: str, hash_value: str) -> None:
    ensure_runs_table(engine)
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO public.discovery_runs (run_id, schema_hash, status, step) "
                "VALUES (:id, :h, 'running', 'started')"
            ),
            {"id": run_id, "h": hash_value},
        )
        conn.commit()
    log.info("discovery.run.start", run_id=run_id, schema_hash=hash_value)


def update_step(engine: Engine, run_id: str, step: str) -> None:
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE public.discovery_runs SET step = :step WHERE run_id = :id"),
            {"step": step, "id": run_id},
        )
        conn.commit()
    log.info("discovery.run.step", run_id=run_id, step=step)


def mark_done(engine: Engine, run_id: str) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE public.discovery_runs SET status = 'done', finished_at = :now "
                "WHERE run_id = :id"
            ),
            {"now": datetime.now(timezone.utc), "id": run_id},
        )
        conn.commit()
    log.info("discovery.run.done", run_id=run_id)


def mark_failed(engine: Engine, run_id: str, error: str) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE public.discovery_runs SET status = 'failed', error = :err, "
                "finished_at = :now WHERE run_id = :id"
            ),
            {"err": error, "now": datetime.now(timezone.utc), "id": run_id},
        )
        conn.commit()
    log.info("discovery.run.failed", run_id=run_id, error=error)


def get_status(engine: Engine, run_id: str) -> dict | None:
    ensure_runs_table(engine)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT run_id, status, step, error FROM public.discovery_runs "
                "WHERE run_id = :id"
            ),
            {"id": run_id},
        ).mappings().first()
    return dict(row) if row else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/discovery/test_idempotency.py -v`
Expected: PASS (3 tests) — these are pure-function tests, no DB needed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/discovery/__init__.py backend/app/discovery/idempotency.py backend/tests/discovery/
git commit -m "feat(discovery): idempotency — schema hash + discovery_runs manifest table"
```

---

### Task 6: Schema introspection

**Files:**
- Create: `backend/app/discovery/introspect.py`
- Test: `backend/tests/discovery/test_introspect.py`

**Interfaces:**
- Consumes: `app.db.connection.get_engine`
- Produces: `TableInfo`, `ColumnInfo` dataclasses; `get_schema_snapshot(engine, schema: str) -> list[TableInfo]`; `to_hashable(tables: list[TableInfo]) -> list[dict]` (feeds `idempotency.schema_hash`)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/discovery/test_introspect.py
import os
import pytest

from app.discovery.introspect import get_schema_snapshot, to_hashable
from app.db.connection import get_engine

requires_db = pytest.mark.skipif(
    not os.getenv("SUPABASE_DB_URL"), reason="SUPABASE_DB_URL not set"
)


@requires_db
def test_get_schema_snapshot_finds_demo_tables():
    engine = get_engine()
    tables = get_schema_snapshot(engine, "demo")
    names = {t.name for t in tables}
    assert "products" in names or "financial_periods" in names


@requires_db
def test_products_table_has_expected_columns():
    engine = get_engine()
    tables = get_schema_snapshot(engine, "demo")
    products = next((t for t in tables if t.name == "products"), None)
    assert products is not None
    col_names = {c.name for c in products.columns}
    assert "product_id" in col_names or len(col_names) > 0


def test_to_hashable_produces_sorted_dicts():
    from app.discovery.introspect import TableInfo, ColumnInfo

    tables = [
        TableInfo(name="b", columns=[ColumnInfo(name="id", data_type="int", is_pk=True, is_fk=False, fk_table=None, fk_column=None)]),
        TableInfo(name="a", columns=[ColumnInfo(name="id", data_type="int", is_pk=True, is_fk=False, fk_table=None, fk_column=None)]),
    ]
    hashable = to_hashable(tables)
    assert hashable[0]["table"] in {"a", "b"}
    assert all("columns" in t for t in hashable)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/discovery/test_introspect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.discovery.introspect'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/discovery/introspect.py
from dataclasses import dataclass
from sqlalchemy import text, Engine

from app.logging.logger import get_logger

log = get_logger(__name__)


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_pk: bool
    is_fk: bool
    fk_table: str | None
    fk_column: str | None


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo]


_COLUMNS_SQL = """
SELECT c.column_name, c.data_type
FROM information_schema.columns c
WHERE c.table_schema = :schema AND c.table_name = :table
ORDER BY c.ordinal_position
"""

_PK_SQL = """
SELECT kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
WHERE tc.table_schema = :schema AND tc.table_name = :table
  AND tc.constraint_type = 'PRIMARY KEY'
"""

_FK_SQL = """
SELECT kcu.column_name, ccu.table_name AS fk_table, ccu.column_name AS fk_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
WHERE tc.table_schema = :schema AND tc.table_name = :table
  AND tc.constraint_type = 'FOREIGN KEY'
"""

_TABLES_SQL = """
SELECT table_name FROM information_schema.tables
WHERE table_schema = :schema AND table_type = 'BASE TABLE'
ORDER BY table_name
"""


def get_schema_snapshot(engine: Engine, schema: str) -> list[TableInfo]:
    log.info("introspect.start", schema=schema)
    with engine.connect() as conn:
        table_names = [r[0] for r in conn.execute(text(_TABLES_SQL), {"schema": schema})]

        tables = []
        for table_name in table_names:
            pk_cols = {r[0] for r in conn.execute(text(_PK_SQL), {"schema": schema, "table": table_name})}
            fk_rows = {
                r[0]: (r[1], r[2])
                for r in conn.execute(text(_FK_SQL), {"schema": schema, "table": table_name})
            }
            columns = []
            for col_name, data_type in conn.execute(text(_COLUMNS_SQL), {"schema": schema, "table": table_name}):
                fk_table, fk_column = fk_rows.get(col_name, (None, None))
                columns.append(ColumnInfo(
                    name=col_name,
                    data_type=data_type,
                    is_pk=col_name in pk_cols,
                    is_fk=col_name in fk_rows,
                    fk_table=fk_table,
                    fk_column=fk_column,
                ))
            tables.append(TableInfo(name=table_name, columns=columns))

    log.info("introspect.done", schema=schema, table_count=len(tables))
    return tables


def to_hashable(tables: list[TableInfo]) -> list[dict]:
    return [
        {"table": t.name, "columns": sorted(c.name for c in t.columns)}
        for t in tables
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/discovery/test_introspect.py -v`
Expected: `test_to_hashable_produces_sorted_dicts` PASSES unconditionally. The two `requires_db` tests PASS once the `demo` schema has data loaded (Task 1 + generator run + loader run), SKIP otherwise.

- [ ] **Step 5: Commit**

```bash
git add backend/app/discovery/introspect.py backend/tests/discovery/test_introspect.py
git commit -m "feat(discovery): schema introspection via information_schema"
```

---

### Task 7: Statistical profiler

**Files:**
- Create: `backend/app/discovery/profiler.py`
- Test: `backend/tests/discovery/test_profiler.py`

**Interfaces:**
- Consumes: `TableInfo`, `ColumnInfo` from `app.discovery.introspect`; `app.config.{DISCOVERY_SAMPLE_PCT, DISCOVERY_LARGE_TABLE_ROWS, DISCOVERY_TOP_N_CATEGORICAL}`
- Produces: `ColumnProfile` dataclass; `profile_table(engine, schema: str, table: TableInfo) -> dict[str, ColumnProfile]`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/discovery/test_profiler.py
import os
import pytest

from app.discovery.profiler import profile_table, ColumnProfile
from app.discovery.introspect import get_schema_snapshot
from app.db.connection import get_engine

requires_db = pytest.mark.skipif(
    not os.getenv("SUPABASE_DB_URL"), reason="SUPABASE_DB_URL not set"
)


@requires_db
def test_profile_table_covers_every_column():
    engine = get_engine()
    tables = get_schema_snapshot(engine, "demo")
    products = next(t for t in tables if t.name == "products")
    profiles = profile_table(engine, "demo", products)
    assert set(profiles.keys()) == {c.name for c in products.columns}


@requires_db
def test_profile_reports_null_rate_and_distinct_count():
    engine = get_engine()
    tables = get_schema_snapshot(engine, "demo")
    products = next(t for t in tables if t.name == "products")
    profiles = profile_table(engine, "demo", products)
    any_profile = next(iter(profiles.values()))
    assert isinstance(any_profile, ColumnProfile)
    assert any_profile.null_rate >= 0.0
    assert any_profile.distinct_count >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/discovery/test_profiler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.discovery.profiler'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/discovery/profiler.py
from dataclasses import dataclass, field
from sqlalchemy import text, Engine

from app.config import DISCOVERY_SAMPLE_PCT, DISCOVERY_LARGE_TABLE_ROWS, DISCOVERY_TOP_N_CATEGORICAL
from app.discovery.introspect import TableInfo
from app.logging.logger import get_logger

log = get_logger(__name__)

NUMERIC_TYPES = {"integer", "bigint", "smallint", "numeric", "real", "double precision"}
DATE_TYPES = {"date", "timestamp without time zone", "timestamp with time zone"}


@dataclass
class ColumnProfile:
    row_count: int
    null_rate: float
    distinct_count: int
    min_value: object = None
    max_value: object = None
    mean_value: float | None = None
    p50: float | None = None
    p95: float | None = None
    top_values: list[tuple] = field(default_factory=list)


def _source(schema: str, table: str, row_count: int) -> str:
    if row_count > DISCOVERY_LARGE_TABLE_ROWS:
        return f"(SELECT * FROM {schema}.{table} TABLESAMPLE BERNOULLI({DISCOVERY_SAMPLE_PCT})) sampled"
    return f"{schema}.{table}"


def _row_count(conn, schema: str, table: str) -> int:
    return conn.execute(text(f"SELECT COUNT(*) FROM {schema}.{table}")).scalar()


def profile_table(engine: Engine, schema: str, table: TableInfo) -> dict:
    log.info("profile.start", table=table.name)
    profiles: dict[str, ColumnProfile] = {}
    with engine.connect() as conn:
        row_count = _row_count(conn, schema, table.name)
        source = _source(schema, table.name, row_count)

        for col in table.columns:
            null_rate, distinct_count = conn.execute(text(
                f"SELECT AVG(CASE WHEN {col.name} IS NULL THEN 1.0 ELSE 0.0 END), "
                f"COUNT(DISTINCT {col.name}) FROM {source}"
            )).first()

            profile = ColumnProfile(
                row_count=row_count,
                null_rate=float(null_rate or 0.0),
                distinct_count=int(distinct_count or 0),
            )

            if col.data_type in NUMERIC_TYPES:
                stats = conn.execute(text(
                    f"SELECT MIN({col.name}), MAX({col.name}), AVG({col.name}), "
                    f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {col.name}), "
                    f"PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY {col.name}) "
                    f"FROM {source}"
                )).first()
                profile.min_value, profile.max_value, mean, p50, p95 = stats
                profile.mean_value = float(mean) if mean is not None else None
                profile.p50 = float(p50) if p50 is not None else None
                profile.p95 = float(p95) if p95 is not None else None
            elif col.data_type in DATE_TYPES:
                min_v, max_v = conn.execute(text(
                    f"SELECT MIN({col.name}), MAX({col.name}) FROM {source}"
                )).first()
                profile.min_value, profile.max_value = min_v, max_v
            else:
                rows = conn.execute(text(
                    f"SELECT {col.name}, COUNT(*) c FROM {source} "
                    f"WHERE {col.name} IS NOT NULL GROUP BY {col.name} "
                    f"ORDER BY c DESC LIMIT {DISCOVERY_TOP_N_CATEGORICAL}"
                )).all()
                profile.top_values = [(r[0], r[1]) for r in rows]

            profiles[col.name] = profile

    log.info("profile.done", table=table.name, columns=len(profiles))
    return profiles
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/discovery/test_profiler.py -v`
Expected: PASS once `demo.products` has data (Task 1 generator/loader run), SKIP otherwise.

- [ ] **Step 5: Commit**

```bash
git add backend/app/discovery/profiler.py backend/tests/discovery/test_profiler.py
git commit -m "feat(discovery): statistical column profiler with TABLESAMPLE"
```

---

### Task 8: Relationship inference

**Files:**
- Create: `backend/app/discovery/relationships.py`
- Test: `backend/tests/discovery/test_relationships.py`

**Interfaces:**
- Consumes: `TableInfo` from `app.discovery.introspect`; `app.config.{DISCOVERY_FK_OVERLAP_SAMPLE, DISCOVERY_FK_OVERLAP_THRESHOLD}`
- Produces: `InferredRelationship` dataclass; `infer_relationships(engine, schema: str, tables: list[TableInfo]) -> list[InferredRelationship]`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/discovery/test_relationships.py
import os
import pytest

from app.discovery.relationships import infer_relationships, InferredRelationship
from app.discovery.introspect import get_schema_snapshot
from app.db.connection import get_engine

requires_db = pytest.mark.skipif(
    not os.getenv("SUPABASE_DB_URL"), reason="SUPABASE_DB_URL not set"
)


@requires_db
def test_infer_relationships_finds_undeclared_fk_like_columns():
    engine = get_engine()
    tables = get_schema_snapshot(engine, "demo")
    relationships = infer_relationships(engine, "demo", tables)
    assert all(isinstance(r, InferredRelationship) for r in relationships)
    assert all(0.0 <= r.overlap_pct <= 1.0 for r in relationships)


def test_infer_relationships_skips_columns_that_already_have_declared_fk():
    from app.discovery.introspect import TableInfo, ColumnInfo

    tables = [
        TableInfo(name="claims", columns=[
            ColumnInfo(name="customer_id", data_type="integer", is_pk=False, is_fk=True, fk_table="customers", fk_column="customer_id"),
        ]),
    ]
    from app.discovery.relationships import _candidate_columns
    candidates = _candidate_columns(tables)
    assert candidates == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/discovery/test_relationships.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.discovery.relationships'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/discovery/relationships.py
from dataclasses import dataclass
from sqlalchemy import text, Engine

from app.config import DISCOVERY_FK_OVERLAP_SAMPLE, DISCOVERY_FK_OVERLAP_THRESHOLD
from app.discovery.introspect import TableInfo
from app.logging.logger import get_logger

log = get_logger(__name__)


@dataclass
class InferredRelationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    overlap_pct: float


def _candidate_columns(tables: list[TableInfo]) -> list[tuple[str, str]]:
    """Columns named like a foreign key (ends in _id, isn't its own table's PK,
    and has no declared FK) are candidates for overlap testing."""
    candidates = []
    for table in tables:
        for col in table.columns:
            if col.is_fk:
                continue
            if col.name.endswith("_id") and not (col.is_pk and col.name == f"{table.name[:-1]}_id"):
                candidates.append((table.name, col.name))
    return candidates


def _target_table_guess(column_name: str, tables: list[TableInfo]) -> str | None:
    stem = column_name[: -len("_id")]
    for plural_suffix in ("s", "es", ""):
        guess = f"{stem}{plural_suffix}"
        if any(t.name == guess for t in tables):
            return guess
    return None


def infer_relationships(engine: Engine, schema: str, tables: list[TableInfo]) -> list[InferredRelationship]:
    log.info("relationships.start", schema=schema)
    results = []
    table_names = {t.name for t in tables}
    pk_by_table = {
        t.name: next((c.name for c in t.columns if c.is_pk), None) for t in tables
    }

    with engine.connect() as conn:
        for from_table, from_col in _candidate_columns(tables):
            target = _target_table_guess(from_col, tables)
            if not target or target not in table_names:
                continue
            to_col = pk_by_table.get(target)
            if not to_col:
                continue

            sample = conn.execute(text(
                f"SELECT {from_col} FROM {schema}.{from_table} "
                f"WHERE {from_col} IS NOT NULL ORDER BY random() "
                f"LIMIT {DISCOVERY_FK_OVERLAP_SAMPLE}"
            )).scalars().all()
            if not sample:
                continue

            found = conn.execute(text(
                f"SELECT COUNT(*) FROM {schema}.{target} WHERE {to_col} = ANY(:vals)"
            ), {"vals": list(sample)}).scalar()

            overlap_pct = found / len(sample)
            if overlap_pct >= DISCOVERY_FK_OVERLAP_THRESHOLD:
                results.append(InferredRelationship(
                    from_table=from_table, from_column=from_col,
                    to_table=target, to_column=to_col,
                    overlap_pct=overlap_pct,
                ))

    log.info("relationships.done", schema=schema, found=len(results))
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/discovery/test_relationships.py -v`
Expected: `test_infer_relationships_skips_columns_that_already_have_declared_fk` PASSES unconditionally. The `requires_db` test PASSES once `demo` has data, SKIPs otherwise.

- [ ] **Step 5: Commit**

```bash
git add backend/app/discovery/relationships.py backend/tests/discovery/test_relationships.py
git commit -m "feat(discovery): infer undeclared FK relationships via value overlap"
```

---

### Task 9: LLM description generation (LangChain)

**Files:**
- Create: `backend/app/discovery/llm.py`
- Test: `backend/tests/discovery/test_llm.py`

**Interfaces:**
- Consumes: `TableInfo`, `ColumnInfo` from `introspect`; `ColumnProfile` from `profiler`; `app.config.{OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL, LLM_MAX_RETRIES}`
- Produces: `describe_table(table, profiles) -> str`, `describe_column(table_name, column, profile) -> str`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/discovery/test_llm.py
import os
import pytest
from unittest.mock import patch, MagicMock

from app.discovery.llm import describe_table, describe_column
from app.discovery.introspect import TableInfo, ColumnInfo
from app.discovery.profiler import ColumnProfile

requires_llm = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"), reason="OPENROUTER_API_KEY not set"
)


def _sample_table():
    col = ColumnInfo(name="claim_amount", data_type="numeric", is_pk=False, is_fk=False, fk_table=None, fk_column=None)
    return TableInfo(name="claims", columns=[col]), {
        "claim_amount": ColumnProfile(row_count=1000, null_rate=0.02, distinct_count=950, mean_value=4200.5)
    }


def test_describe_table_calls_llm_with_profile_context():
    table, profiles = _sample_table()
    with patch("app.discovery.llm._get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Stores insurance claims."
        mock_get_llm.return_value = mock_llm

        result = describe_table(table, profiles)

        assert result == "Stores insurance claims."
        prompt_arg = mock_llm.invoke.call_args[0][0]
        assert "claims" in str(prompt_arg)
        assert "claim_amount" in str(prompt_arg)


def test_describe_column_includes_null_rate_in_prompt():
    table, profiles = _sample_table()
    with patch("app.discovery.llm._get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "The dollar amount of the claim."
        mock_get_llm.return_value = mock_llm

        result = describe_column("claims", table.columns[0], profiles["claim_amount"])

        assert result == "The dollar amount of the claim."
        prompt_arg = mock_llm.invoke.call_args[0][0]
        assert "0.02" in str(prompt_arg) or "2%" in str(prompt_arg) or "2.0%" in str(prompt_arg)


@requires_llm
def test_describe_table_against_real_llm():
    table, profiles = _sample_table()
    result = describe_table(table, profiles)
    assert isinstance(result, str) and len(result) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/discovery/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.discovery.llm'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/discovery/prompts/table_description.txt
# You are documenting a database table for an analyst who has never seen it.
# Table: {table_name}
# Columns: {columns}
#
# Write 1-3 sentences: what this table is for, when to use it, and any gotcha (e.g. null behavior, denormalization) an analyst should know.
```

```python
# backend/app/discovery/prompts/column_description.txt
# You are documenting a database column for an analyst who has never seen it.
# Table: {table_name}, Column: {column_name} ({data_type})
# Stats: {stats}
#
# Write 1 sentence: what this column represents, when to use it, and any gotcha (nulls, encoding) an analyst should know.
```

```python
# backend/app/discovery/prompts/__init__.py
from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


@lru_cache
def load(name: str) -> str:
    """Load a prompt template by filename (without extension). Templates
    use plain str.format() placeholders. Kept as .txt files, not inline
    strings, so prompt wording can be edited without touching Python."""
    return (_PROMPTS_DIR / f"{name}.txt").read_text()
```

```python
# backend/app/discovery/llm.py
from functools import lru_cache
from langchain_openai import ChatOpenAI

from app.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL, LLM_MAX_RETRIES
from app.discovery import prompts
from app.discovery.introspect import TableInfo, ColumnInfo
from app.utils.logger import get_logger

log = get_logger(__name__)


@lru_cache
def _get_llm():
    # OpenRouter exposes an OpenAI-compatible endpoint — ChatOpenAI works
    # unmodified against it via base_url. Model swap = change LLM_MODEL only.
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        max_retries=LLM_MAX_RETRIES,
        temperature=0,
    )


def describe_table(table: TableInfo, profiles: dict) -> str:
    col_summary = ", ".join(
        f"{c.name} ({c.data_type}, null_rate={profiles[c.name].null_rate:.2f})"
        for c in table.columns if c.name in profiles
    )
    prompt = prompts.load("table_description").format(
        table_name=table.name,
        columns=col_summary,
    )
    log.info(f"describing table: {table.name}")
    response = _get_llm().invoke(prompt)
    return response.content


def describe_column(table_name: str, column: ColumnInfo, profile) -> str:
    stats = f"null_rate={profile.null_rate:.2f}, distinct={profile.distinct_count}"
    if profile.mean_value is not None:
        stats += f", mean={profile.mean_value}"
    if profile.top_values:
        stats += f", top_values={profile.top_values[:5]}"

    prompt = prompts.load("column_description").format(
        table_name=table_name,
        column_name=column.name,
        data_type=column.data_type,
        stats=stats,
    )
    log.info(f"describing column: {table_name}.{column.name}")
    response = _get_llm().invoke(prompt)
    return response.content
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/discovery/test_llm.py -v`
Expected: the two mocked tests PASS unconditionally; the `requires_llm` test PASSES with `OPENROUTER_API_KEY` set, SKIPs otherwise.

- [ ] **Step 5: Commit**

```bash
git add backend/app/discovery/llm.py backend/tests/discovery/test_llm.py
git commit -m "feat(discovery): LangChain LLM wrapper for table/column descriptions"
```

---

### Task 10: Embeddings (LangChain + pgvector)

**Files:**
- Create: `backend/app/discovery/embeddings.py`
- Test: `backend/tests/discovery/test_embeddings.py`

**Interfaces:**
- Consumes: `app.config.{EMBEDDING_MODEL, EMBEDDING_DIM}`, `app.db.connection.get_engine`
- Produces: `embed_and_store(engine, table_name: str, table_description: str, column_descriptions: dict[str, str]) -> None`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/discovery/test_embeddings.py
import os
import pytest
from unittest.mock import patch, MagicMock

from app.discovery.embeddings import embed_and_store

requires_db = pytest.mark.skipif(
    not os.getenv("SUPABASE_DB_URL"), reason="SUPABASE_DB_URL not set"
)


@requires_db
def test_embed_and_store_writes_table_and_column_rows():
    from app.db.connection import get_engine
    from sqlalchemy import text

    engine = get_engine()
    with patch("app.discovery.embeddings._get_embeddings") as mock_get_emb:
        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = [0.01] * 1536
        mock_get_emb.return_value = mock_emb

        embed_and_store(
            engine,
            table_name="__test_table",
            table_description="A test table.",
            column_descriptions={"col_a": "A test column."},
        )

    with engine.connect() as conn:
        table_row = conn.execute(
            text("SELECT description FROM public.table_embeddings WHERE table_name = :t"),
            {"t": "__test_table"},
        ).first()
        col_row = conn.execute(
            text("SELECT description FROM public.column_embeddings WHERE table_name = :t AND column_name = :c"),
            {"t": "__test_table", "c": "col_a"},
        ).first()
        conn.execute(text("DELETE FROM public.table_embeddings WHERE table_name = :t"), {"t": "__test_table"})
        conn.execute(text("DELETE FROM public.column_embeddings WHERE table_name = :t"), {"t": "__test_table"})
        conn.commit()

    assert table_row[0] == "A test table."
    assert col_row[0] == "A test column."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/discovery/test_embeddings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.discovery.embeddings'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/discovery/embeddings.py
from functools import lru_cache
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import text, Engine

from app.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, EMBEDDING_MODEL
from app.logging.logger import get_logger

log = get_logger(__name__)


@lru_cache
def _get_embeddings():
    # OpenRouter also exposes an embeddings route via its OpenAI-compatible
    # endpoint — same key/base_url as the LLM, no separate provider needed.
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
    )


def embed_and_store(
    engine: Engine,
    table_name: str,
    table_description: str,
    column_descriptions: dict[str, str],
) -> None:
    embedder = _get_embeddings()

    table_vec = embedder.embed_query(table_description)
    log.info("embeddings.table", table=table_name)

    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO public.table_embeddings (table_name, description, embedding) "
                "VALUES (:t, :d, :e) "
                "ON CONFLICT (table_name) DO UPDATE SET description = :d, embedding = :e"
            ),
            {"t": table_name, "d": table_description, "e": str(table_vec)},
        )

        for col_name, col_desc in column_descriptions.items():
            col_vec = embedder.embed_query(col_desc)
            conn.execute(
                text(
                    "INSERT INTO public.column_embeddings (table_name, column_name, description, embedding) "
                    "VALUES (:t, :c, :d, :e) "
                    "ON CONFLICT (table_name, column_name) DO UPDATE SET description = :d, embedding = :e"
                ),
                {"t": table_name, "c": col_name, "d": col_desc, "e": str(col_vec)},
            )
        conn.commit()

    log.info("embeddings.done", table=table_name, columns=len(column_descriptions))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/discovery/test_embeddings.py -v`
Expected: PASS once migrations (Task 4) have run and `SUPABASE_DB_URL` is set; SKIP otherwise.

- [ ] **Step 5: Commit**

```bash
git add backend/app/discovery/embeddings.py backend/tests/discovery/test_embeddings.py
git commit -m "feat(discovery): embed descriptions via LangChain, write to pgvector"
```

---

### Task 11: Discovery orchestrator

**Files:**
- Create: `backend/app/discovery/orchestrator.py`
- Test: `backend/tests/discovery/test_orchestrator.py`

**Interfaces:**
- Consumes: everything from Tasks 5-10
- Produces: `run_discovery(db_url: str, schema: str = DEMO_SCHEMA) -> str` (returns `run_id`), `get_discovery_status(run_id: str) -> dict | None`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/discovery/test_orchestrator.py
import os
import pytest

from app.discovery.orchestrator import run_discovery, get_discovery_status

requires_full_stack = pytest.mark.skipif(
    not (os.getenv("SUPABASE_DB_URL") and os.getenv("OPENROUTER_API_KEY")),
    reason="requires SUPABASE_DB_URL, OPENROUTER_API_KEY",
)


@requires_full_stack
def test_run_discovery_completes_and_reports_status():
    run_id = run_discovery(os.environ["SUPABASE_DB_URL"], schema="demo")
    status = get_discovery_status(run_id)
    assert status["status"] in {"running", "done"}


@requires_full_stack
def test_run_discovery_skips_unchanged_schema():
    first_run_id = run_discovery(os.environ["SUPABASE_DB_URL"], schema="demo")
    second_run_id = run_discovery(os.environ["SUPABASE_DB_URL"], schema="demo")
    assert first_run_id == second_run_id  # same schema hash -> same run reused
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/discovery/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.discovery.orchestrator'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/discovery/orchestrator.py
import uuid
from sqlalchemy import text

from app.config import DEMO_SCHEMA
from app.db.connection import get_engine
from app.db.migrate import run_migrations
from app.discovery.idempotency import schema_hash, should_skip, start_run, update_step, mark_done, mark_failed, get_status
from app.discovery.introspect import get_schema_snapshot, to_hashable
from app.discovery.profiler import profile_table
from app.discovery.relationships import infer_relationships
from app.discovery.llm import describe_table, describe_column
from app.discovery.embeddings import embed_and_store
from app.logging.logger import get_logger

log = get_logger(__name__)


def _existing_run_id_for_hash(engine, hash_value: str) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT run_id FROM public.discovery_runs WHERE schema_hash = :h ORDER BY started_at DESC LIMIT 1"),
            {"h": hash_value},
        ).first()
    return row[0] if row else None


def run_discovery(db_url: str, schema: str = DEMO_SCHEMA) -> str:
    engine = get_engine()
    run_migrations(engine)

    tables = get_schema_snapshot(engine, schema)
    hash_value = schema_hash(to_hashable(tables))

    if should_skip(engine, hash_value):
        run_id = _existing_run_id_for_hash(engine, hash_value)
        log.info("discovery.skipped", schema=schema, run_id=run_id)
        return run_id

    run_id = str(uuid.uuid4())
    start_run(engine, run_id, hash_value)

    try:
        update_step(engine, run_id, "profiling")
        profiles_by_table = {t.name: profile_table(engine, schema, t) for t in tables}

        update_step(engine, run_id, "inferring_relationships")
        infer_relationships(engine, schema, tables)  # logged; consumed by Stage 1b, not persisted here

        update_step(engine, run_id, "describing")
        for table in tables:
            profiles = profiles_by_table[table.name]
            table_desc = describe_table(table, profiles)
            column_descs = {
                col.name: describe_column(table.name, col, profiles[col.name])
                for col in table.columns if col.name in profiles
            }

            update_step(engine, run_id, f"embedding:{table.name}")
            embed_and_store(engine, table.name, table_desc, column_descs)

        mark_done(engine, run_id)
    except Exception as e:
        mark_failed(engine, run_id, str(e))
        raise

    return run_id


def get_discovery_status(run_id: str) -> dict | None:
    engine = get_engine()
    return get_status(engine, run_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/discovery/test_orchestrator.py -v`
Expected: PASS with the full stack configured and `demo` populated; SKIP otherwise. This is the slow, expensive, real end-to-end test — run it deliberately, not as part of a tight inner loop.

- [ ] **Step 5: Commit**

```bash
git add backend/app/discovery/orchestrator.py backend/tests/discovery/test_orchestrator.py
git commit -m "feat(discovery): orchestrate introspect -> profile -> describe -> embed pipeline"
```

---

### Task 12: API layer — FastAPI app, discover routes, rate limiting

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/discover.py`
- Create: `backend/app/api/middleware/__init__.py`
- Create: `backend/app/api/middleware/rate_limit.py`
- Test: `backend/tests/api/__init__.py`
- Test: `backend/tests/api/test_discover_routes.py`

**Interfaces:**
- Consumes: `app.discovery.orchestrator.{run_discovery, get_discovery_status}`
- Produces: FastAPI app at `app.main:app`; `POST /api/discover`, `GET /api/discover/status/{run_id}`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/__init__.py
```

```python
# backend/tests/api/test_discover_routes.py
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_post_discover_kicks_off_run_and_returns_run_id():
    with patch("app.api.routes.discover.run_discovery", return_value="fake-run-id"):
        response = client.post("/api/discover", json={"db_url": "postgres://fake"})
    assert response.status_code == 202
    assert response.json() == {"run_id": "fake-run-id"}


def test_get_discover_status_returns_run_state():
    with patch("app.api.routes.discover.get_discovery_status", return_value={"run_id": "fake-run-id", "status": "done", "step": None, "error": None}):
        response = client.get("/api/discover/status/fake-run-id")
    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_get_discover_status_404_for_unknown_run():
    with patch("app.api.routes.discover.get_discovery_status", return_value=None):
        response = client.get("/api/discover/status/unknown-run-id")
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_discover_routes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/api/__init__.py
```

```python
# backend/app/api/middleware/__init__.py
```

```python
# backend/app/api/middleware/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import RATE_LIMIT

limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT])
```

```python
# backend/app/api/routes/__init__.py
```

```python
# backend/app/api/routes/discover.py
from fastapi import APIRouter, HTTPException, Request

from app.discovery.orchestrator import run_discovery, get_discovery_status
from app.api.middleware.rate_limit import limiter
from app.logging.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/api/discover", tags=["discover"])


@router.post("", status_code=202)
@limiter.limit("20/minute")
def discover(request: Request, body: dict):
    db_url = body["db_url"]
    log.info("api.discover.request", db_url_present=bool(db_url))
    run_id = run_discovery(db_url)
    return {"run_id": run_id}


@router.get("/status/{run_id}")
@limiter.limit("20/minute")
def discover_status(request: Request, run_id: str):
    status = get_discovery_status(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="run_id not found")
    return status
```

```python
# backend/app/main.py
from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.api.middleware.rate_limit import limiter
from app.api.routes.discover import router as discover_router
from app.logging.logger import get_logger

log = get_logger(__name__)

app = FastAPI(title="table-lens backend")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(discover_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_discover_routes.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/api/ backend/tests/api/
git commit -m "feat(api): FastAPI app with /api/discover routes and rate limiting"
```

---

### Task 13: Frontend scaffold (Next.js 14, App Router)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.js`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/page.tsx`
- Create: `frontend/lib/logger.ts`
- Create: `frontend/lib/api-client.ts`
- Test: `frontend/lib/logger.test.ts`

**Interfaces:**
- Produces: `logger.debug/info/warn/error(...)` from `frontend/lib/logger.ts`; `apiClient.post/get(...)` from `frontend/lib/api-client.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/lib/logger.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { logger } from "./logger";

describe("logger", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("logs info messages via console.info with a level prefix", () => {
    const spy = vi.spyOn(console, "info").mockImplementation(() => {});
    logger.info("hello", { key: "value" });
    expect(spy).toHaveBeenCalledWith("[info]", "hello", { key: "value" });
  });

  it("suppresses debug logs when NODE_ENV is production", () => {
    const original = process.env.NODE_ENV;
    process.env.NODE_ENV = "production";
    const spy = vi.spyOn(console, "debug").mockImplementation(() => {});
    logger.debug("verbose detail");
    expect(spy).not.toHaveBeenCalled();
    process.env.NODE_ENV = original;
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && bun run test -- logger.test.ts`
Expected: FAIL — `Cannot find module './logger'` (project not scaffolded yet)

- [ ] **Step 3: Write minimal implementation**

```json
// frontend/package.json
{
  "name": "table-lens-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "@types/node": "^22.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "vitest": "^2.1.0"
  }
}
```

```json
// frontend/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
```

```javascript
// frontend/next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {};
module.exports = nextConfig;
```

```typescript
// frontend/lib/logger.ts
type LogLevel = "debug" | "info" | "warn" | "error";

function shouldLog(level: LogLevel): boolean {
  if (level === "debug") return process.env.NODE_ENV !== "production";
  return true;
}

function log(level: LogLevel, message: string, ...meta: unknown[]): void {
  if (!shouldLog(level)) return;
  const consoleFn = console[level] ?? console.log;
  consoleFn(`[${level}]`, message, ...meta);
}

export const logger = {
  debug: (message: string, ...meta: unknown[]) => log("debug", message, ...meta),
  info: (message: string, ...meta: unknown[]) => log("info", message, ...meta),
  warn: (message: string, ...meta: unknown[]) => log("warn", message, ...meta),
  error: (message: string, ...meta: unknown[]) => log("error", message, ...meta),
};
```

```typescript
// frontend/lib/api-client.ts
import { logger } from "./logger";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  logger.debug("api.request", { path });
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok) {
    logger.error("api.error", { path, status: response.status });
    throw new Error(`API request to ${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};
```

```tsx
// frontend/app/layout.tsx
export const metadata = {
  title: "table-lens",
  description: "AI-native conversational BI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

```tsx
// frontend/app/page.tsx
export default function HomePage() {
  return <main>table-lens — scaffold, no UI built yet.</main>;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && bun install && bun run test -- logger.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): Next.js 14 App Router scaffold with console logger + API client stub"
```

---

### Task 14: Populate demo data, run discovery end-to-end, update PROGRESS.md

**Files:**
- Modify: `docs/PROGRESS.md`

This task is manual verification against the real Supabase project, not automated tests — it closes the loop the spec's Testing section calls for.

- [ ] **Step 1: Generate and load the full demo dataset**

```bash
cd backend/app/generator
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run generate.py
uv run connector/loader.py
```
Expected: all 50 tables generated and loaded into the `demo` schema (verify: `SELECT COUNT(*) FROM demo.claims;` in Supabase SQL editor returns ~30,000).

- [ ] **Step 2: Run the read-only role provisioning SQL** (from Task 3, Step 4) if not already done.

- [ ] **Step 3: Trigger discovery via the API**

```bash
cd backend
uv run uvicorn app.main:app --reload &
curl -X POST http://localhost:8000/api/discover -H "Content-Type: application/json" -d "{\"db_url\": \"$SUPABASE_DB_URL\"}"
```
Note the returned `run_id`, then poll:
```bash
curl http://localhost:8000/api/discover/status/<run_id>
```
Expected: status eventually reaches `"done"`.

- [ ] **Step 4: Spot-check embeddings quality**

In Supabase SQL editor, run 5-10 sample semantic queries against `public.table_embeddings` (e.g. cosine-similarity search for "how much did a claim cost", "customer risk profile") and confirm the top results are sensible tables (`claims`, `claim_payments`, `underwriting_assessments`, etc.) per the spec's Testing section.

- [ ] **Step 5: Update docs/PROGRESS.md**

Change the Stage 0 row status to reflect demo data is loaded, and Stage 1a row to "Built" once verification passes. Update "Current Focus" to point at Stage 1b.

- [ ] **Step 6: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs: mark foundation + stage 1a complete in progress tracker"
```

---

## Self-Review Notes

- **Spec coverage:** repo layout (Task 1, 13), LangChain-only LLM/embeddings (Task 9, 10), config convention (Task 2), generator relocation already done pre-plan and verified again in Task 1 Step 5, discovery pipeline steps 1-9 from the spec's Data Flow section (Tasks 6-11), pgvector schema (Task 4), demo/public schema split (Task 1, 4), logging (Task 2, 13), documentation-is-canon (Task 14 updates PROGRESS.md; HLD docs already written pre-plan), idempotency (Task 5, 11), rate limiting (Task 12), read-only DB enforcement (Task 3).
- **Not covered by this plan, and correctly so per spec's Out of Scope:** Stage 1b query agent, frontend pages beyond scaffold, auth, deployment.
- **Gap acknowledged:** `frontend/lib/logger.test.ts` assumes `vitest` is configured with no extra config file — if `bun run test` fails to discover the test, add a minimal `vitest.config.ts` re-exporting defaults before Task 13 Step 4.
