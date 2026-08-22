# table-lens — Architecture

## Status
Canon. Update whenever a component is added, replaced, or its role changes.
Build/rollout progress lives in `docs/PROGRESS.md`, not here.

## System Overview
```
                         ┌─────────────────────┐
                         │   Frontend (Next.js) │
                         │  chat + chart panels │
                         └──────────┬───────────┘
                                    │ HTTP
                         ┌──────────▼───────────┐
                         │   Backend (FastAPI)   │
                         │  ┌─────────────────┐  │
                         │  │  discovery/     │  │
                         │  │  (schema profile│  │
                         │  │   + embeddings) │  │
                         │  └────────┬────────┘  │
                         │           │            │
                         │  ┌────────▼────────┐  │
                         │  │  query agent    │  │
                         │  │  (NL → SQL)     │  │
                         │  └────────┬────────┘  │
                         │           │            │
                         │  ┌────────▼────────┐  │
                         │  │  generator/     │  │
                         │  │  (synthetic     │  │
                         │  │   seed data)    │  │
                         │  └─────────────────┘  │
                         └──────────┬────────────┘
                                    │
                         ┌──────────▼───────────┐
                         │  Supabase (Postgres   │
                         │  + pgvector)          │
                         └───────────────────────┘
```

## Components

### `backend/app/generator/`
Synthetic insurance database generator. Produces 50 tables of realistic fake
data as Parquet, loaded to Supabase via a connector. Deterministic (fixed
seed) — pure function of `config.py` inputs. Not agent logic; exists only to
seed the demo database. Config split per project-wide convention: real
cross-cutting tunables (row counts, seed, business rates) live in
`config.py`; low-impact local constants stay at the top of the file that
uses them.

### `backend/app/discovery/`
Profiles an unknown database once per connection. Sub-components:
- schema introspection (`information_schema` reads)
- statistical profiler (sampled queries via `TABLESAMPLE`)
- relationship inference (name pattern + value-overlap sampling)
- `llm.py` — LangChain LLM wrapper, routed through OpenRouter (model is a
  config swap, never hardcoded)
- `prompts/` — prompt templates as plain `.txt` files (`table_description.txt`,
  `column_description.txt`), loaded and `.format()`-filled by `llm.py` —
  kept out of the code file so prompt wording can be edited without
  touching Python
- `embeddings.py` — LangChain embeddings wrapper, routed through OpenRouter (same key/base_url as `llm.py`), writes to pgvector
- `queries/` — SQL as plain `.sql` files, not inline in Python. Bind
  parameters (`:name`) stay as-is; identifier placeholders (table/column
  names, which SQL can't bind as parameters) use `{name}` and are filled
  via `.format()` before execution

Output is stored (not recomputed per query) and consumed by the query agent.
Idempotent: schema-hash-checked re-runs, same pattern as the generator.

### `backend/app/query/`
Two-layer retrieval (table embeddings → column embeddings within retrieved
tables) narrows what schema context reaches the LLM prompt — full schema is
never sent. Generates SQL (PostgreSQL 15, SELECT-only, CTEs, LIMIT enforced),
validates with sqlglot, executes against a read-only DB role, retries on
error (max 3), and produces a plain-English headline from actual results.

### `backend/app/db/`
Supabase/Postgres connection management. Enforces read-only access at the
connection level (dedicated Postgres role), not just via prompt instructions.
Owns pgvector schema migrations.

### `backend/app/api/`
FastAPI route layer. Thin — delegates to `discovery/` and `query/`. Rate
limiting (IP-based, 20 req/min) applied here.

### `backend/app/logging/`
Structured logging (structlog over stdlib logging), shared config used by
every backend component — generator, discovery, query, api. JSON output to
both stdout and a rotating file (`backend/logs/app.log`, not committed) —
one place to change format/level rather than per-module `print`/ad-hoc
logging calls. Frontend logging stays console-only (`frontend/lib/logger.ts`)
since browser JS has no filesystem access — there is no frontend equivalent
of `backend/logs/`.

### `frontend/`
Next.js 14, App Router. Split-screen chat + visualization UI. SSR chosen
over a plain SPA because dashboards are shareable by link with no auth —
server rendering gives fast first load and real link previews.
`frontend/lib/logger.ts` — thin wrapper over `console.*` with levels,
dev/prod aware. No external logging service — matches no-auth showcase
scope.

## Data Stores
- **Postgres (Supabase):** the demo insurance database itself (generator
  output), plus product tables (`saved_charts`, `dashboards`).
- **pgvector:** `table_embeddings`, `column_embeddings` — discovery agent
  output, consumed by the query agent's retrieval layer.

## Cross-Cutting Decisions
- **LangChain everywhere an LLM is called** — no direct provider SDK usage,
  so the model is a config swap, not a code change.
- **Read-only enforcement is structural**, not just instructional — a
  read-only DB role backs every SELECT-only rule in the system prompt.
- **No auth** — single shared showcase instance, rate limiting is the only
  access control.
