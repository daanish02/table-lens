# Table Lens — Product Requirements

## Status
Canon. Update whenever product scope or decisions change — this file is the
source of truth, not a snapshot. Build/rollout progress lives in
`docs/PROGRESS.md`, not here.

## What This Is
An AI-native conversational BI product. Users ask questions in natural
language, an agent queries a PostgreSQL database, returns results, generates
visualizations, and persists charts and dashboards. Built for a demo/showcase
deployment — no auth required.

## Users
Demo/showcase audience — anyone exploring the product via a shared link. No
accounts, no roles, no permissions.

## Synthetic Data Generator
A synthetic insurance database generator (`backend/app/generator/`) seeds the
demo environment. Generates 50 tables (11 deep with 150k-500k rows, 6 wide
with 200-350 extra columns, 33 normal) with realistic distributions —
log-normal monetary values, seasonality, categorical imbalance, sparse legacy
nulls, deliberate denormalization. Output saved as Parquet locally, loaded to
Supabase via a connector script. Deterministic (fixed seed) — output must not
change across refactors.

## Discovery Agent
Runs once per database connection. Autonomously profiles an unknown database
the way a new data analyst would — no hardcoded schema knowledge:

1. Pull full schema from `information_schema` — tables, columns, types, PKs, FKs
2. Statistically profile every column via sampled queries
   (`TABLESAMPLE BERNOULLI(2)` for large tables): row count, null rate,
   distinct value count; numerics get min/max/mean/p50/p95; categoricals get
   top-10 by frequency; dates get min/max
3. Infer relationships where no FK is declared — column name pattern matching
   + value overlap sampling (1000 random values from candidate FK column,
   check % existing in candidate PK table). Currently computed and logged
   every run, but not yet persisted or fed into the query agent's retrieval
   — a real gap, not a design choice.
4. Pass structural + statistical profile to an LLM (via LangChain, model
   pluggable) → generate plain-English descriptions per table/column — what
   it's for, when to use it, gotchas, null behavior
5. Embed all descriptions into Supabase pgvector at two levels: table-level
   and column-level

Discovery output is stored and reused by the query agent. Re-runs are
per-column: each column's content hash is checked, and only changed columns
get re-described — a finer-grained mechanism than the generator's
whole-table idempotency check.

## Query Agent
Uses discovery output to answer user questions.

Schema retrieval is two-layer:
- Layer 1: semantic search on table embeddings → top 8 relevant tables
- Layer 2: for each retrieved table, semantic search on column embeddings →
  top 20 relevant columns per table

Only retrieved schema goes into the prompt — the LLM never sees the full
schema.

SQL generation rules (enforced in system prompt):
- PostgreSQL 15 dialect only
- SELECT only — read-only enforced at DB connection level too
- Always use CTEs over nested subqueries
- Always include LIMIT (default 1000) unless user explicitly asks for all
- Use COALESCE on high-null columns
- TABLESAMPLE for exploratory queries on large tables
- If the question is ambiguous or could hit multiple valid table paths, ask
  one clarifying question before generating SQL

The agent is a LangChain tool-calling loop (`search_tables`, `search_columns`,
`run_sql`): it generates SQL, sqlglot-validates it, executes it, and on a
SQL error gets the error fed back to retry — bounded by an overall tool-call
recursion limit rather than a fixed retry count, so it can search schema
again mid-conversation if its first guess was wrong, not just retry the same
SQL blindly.

After successful execution:
- Return results as rows, streamed to the client via SSE
- Second LLM call with a sample of results (first 20 rows + column names) →
  generate a 1-2 sentence plain-English headline summarizing the key finding

Multi-turn memory: windowed conversation memory (k=10), with retrieved schema
context included so follow-up questions resolve correctly.

Endpoints — see `APIS.md` for the full, current surface (discovery status/
results/overview, query streaming, visualize, data browsing, charts/
dashboards CRUD).

Rate limiting: IP-based, `20/minute` by default; `POST /api/discover` is
tightened to `5/hour` given its LLM cost. No auth needed for showcase.

## Chat + Chart UI
Two separate pages, not one unified split screen:
- `/ask` — chat panel paired with a raw SQL/results view (no chart)
- `/visualize` — a question box paired with a panel of accumulating chart
  cards, one per question asked in that session
- `/data` — raw table browser/overview

Chart type and axis/series mapping are chosen by a single structured LLM
call (`backend/app/visualize/agent.py`), guided by a prompt rather than
fixed deterministic rules. Supported chart types: line, bar, pie, scatter,
and `stat` (a single-value/big-number display). Rendered with ECharts, with
zoom/hover interactivity. "Save chart" persists to Supabase
(`saved_charts` — see `SCHEMAS.md`).

## Dashboard Builder
- Charts accumulate as cards in a static grid during a `/visualize` session
- "Save as dashboard" prompts for a title and persists the current set of
  chart ids (`dashboards` — see `SCHEMAS.md`)
- No drag-and-drop layout, no persisted positioning, and no natural-language
  composition command ("add my claims chart to a new dashboard...") — saving
  is a simple accumulate-then-name-it flow, not a dashboard editor
- Shareable by link (no auth — anyone with the link can view, not edit)

## Out of Scope
RBAC, organizations, multi-tenant, audit logs, link expiry. Not scheduled.
Drag-and-drop dashboard layout, NL dashboard composition, cross-table
redundancy detection, and CSV export are not built and not currently
planned — flagged here since earlier drafts of this doc described them as
in-scope.

## Key Architectural Decisions

1. **Discovery agent is separate from query agent.** Runs once, outputs are
   stored, query agent consumes stored output. Not interleaved.
2. **Two-layer retrieval.** Table-level first, then column-level within
   retrieved tables. Never full schema in prompt.
3. **Headline generation is a second LLM call** after execution, with actual
   result data — not part of the SQL generation call.
4. **Read-only DB enforced at connection level**, not just prompt
   instructions — SQLAlchemy connection string with a read-only Postgres
   role.
5. **Idempotency everywhere, but not identical mechanisms.** Discovery
   checks a per-column content hash before re-describing; the generator
   checks a per-table schema+row-count hash via a local manifest — same
   philosophy (skip unchanged work), different granularity because the two
   problems are different shapes.
6. **LLM and embeddings access via LangChain, both routed through
   OpenRouter** (its OpenAI-compatible endpoint), never a hardcoded provider
   SDK call — model is a config-level swap, not a code change. One API key
   for both.
7. **Showcase deployment = no auth.** Single shared instance. Rate limiting
   only.

## Environment Variables Needed
```
OPENROUTER_API_KEY=          # LLM + embeddings, via LangChain's OpenAI-compatible client, model is a config swap
SUPABASE_DB_URL=postgres://...
SUPABASE_DB_URL_READONLY=     # dedicated read-only role, used for discovery/query access
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_BASE_URL=     # frontend's base URL for the backend API
```
One root `.env` for the whole project (backend and frontend both read it) —
see `README.md`.

## Stack
- Backend: Python + FastAPI
- Agent framework: LangChain (LLM/embeddings provider pluggable)
- Database: Supabase (Postgres + pgvector)
- Frontend: Next.js 14 (App Router)
- Charts: Apache ECharts
- Package manager: uv (Python), bun (frontend)
- Deployment target: Vercel (frontend) + any Docker host (backend)

## Repo Layout
```
table-lens/
├── backend/
│   ├── app/
│   │   ├── generator/          # synthetic data generator
│   │   │   ├── config.py
│   │   │   ├── schema/
│   │   │   ├── generators/
│   │   │   ├── connector/
│   │   │   └── idempotency/
│   │   ├── discovery/          # discovery agent
│   │   │   ├── introspect.py
│   │   │   ├── profiler.py
│   │   │   ├── relationships.py
│   │   │   ├── llm.py          # LangChain LLM wrapper
│   │   │   └── embeddings.py   # LangChain embeddings wrapper
│   │   ├── query/              # query agent (NL -> SQL)
│   │   ├── visualize/          # visualize agent (result -> chart spec)
│   │   ├── db/
│   │   │   ├── connection.py
│   │   │   └── migrations/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   └── middleware/
│   │   ├── utils/
│   │   │   └── logger.py       # stdlib logging setup, shared across app
│   │   ├── config.py           # cross-cutting tunables
│   │   └── main.py             # FastAPI entrypoint
│   ├── tests/
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/                   # Next.js 14, App Router
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── ask/                # chat + SQL/results view
│   │   ├── visualize/          # chat + chart cards
│   │   └── data/               # raw table browser
│   ├── components/
│   ├── lib/
│   │   ├── api-client.ts
│   │   └── logger.ts           # console wrapper, dev/prod aware
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.js
├── docs/                       # canon docs (this file and siblings)
├── docs/diagrams/              # excalidraw
└── specs/                      # per-increment design specs
```
