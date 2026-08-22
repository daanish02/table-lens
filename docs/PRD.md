# table-lens — Product Requirements

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
demo environment. Generates 50 tables (5 deep with 200k-500k rows, 10 wide
with 200-350 columns, 35 normal) with realistic distributions — log-normal
monetary values, seasonality, categorical imbalance, sparse legacy nulls,
deliberate denormalization. Output saved as Parquet locally, loaded to
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
   check % existing in candidate PK table)
4. Pass structural + statistical profile to an LLM (via LangChain, model
   pluggable) → generate plain-English descriptions per table/column — what
   it's for, when to use it, gotchas, null behavior
5. Detect redundancy — same concept stored in multiple tables, flag which to
   prefer for which query type
6. Embed all descriptions into Supabase pgvector at two levels: table-level
   and column-level

Discovery output is stored and reused. Re-runs only if schema changes
(hash-checked, same idempotency pattern as the data generator).

## Query Agent
Uses discovery output to answer user questions.

Schema retrieval is two-layer:
- Layer 1: semantic search on table embeddings → top 5-8 relevant tables
- Layer 2: for each retrieved table, semantic search on column embeddings →
  top 15-20 relevant columns per table

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

Retry loop: generate SQL → sqlglot validation → execute → on error, feed
error + message back to the LLM → regenerate → max 3 retries → if still
failing, tell the user gracefully.

After successful execution:
- Return results as a dataframe → offer CSV download
- Second LLM call with a sample of results (first 20 rows + column names) →
  generate a 1-2 sentence plain-English headline summarizing the key finding

Multi-turn memory: windowed conversation memory (k=10), with retrieved schema
context included so follow-up questions resolve correctly.

Endpoints:
```
POST /api/discover          # trigger discovery agent on connected DB
GET  /api/discover/status   # check discovery progress
POST /api/query             # submit NL question, returns SQL + results + headline
GET  /api/query/{id}/csv    # download results as CSV
POST /api/query/{id}/retry  # retry with user feedback
```

Rate limiting: IP-based throttle on all endpoints, 20 requests/minute per IP.
No auth needed for showcase.

## Chat + Chart UI
- Split-screen UI: chat panel left, visualization panel right (Next.js 14)
- Auto chart type selection based on result shape:
  - Time series → line chart
  - Category vs metric → bar chart
  - Two metrics → scatter
  - Part of whole → pie/donut
  - Distribution → histogram
  - Geographic (state column detected) → choropleth
- Charts rendered with ECharts or Plotly.js, fully interactive (zoom, hover,
  filter)
- "Save chart" persists to Supabase (`saved_charts` — see `SCHEMAS.md`)

## Dashboard Builder
- Compose saved charts into dashboards via natural language ("add my claims
  chart and premium trends to a new dashboard called Q4 Review")
- Drag-and-drop layout via react-grid-layout
- Layout stored as JSON (`dashboards` — see `SCHEMAS.md`)
- Dashboards refresh on demand
- Shareable by link (no auth — anyone with the link can view, not edit)

## Out of Scope
RBAC, organizations, multi-tenant, audit logs, link expiry. Not scheduled.

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
5. **Idempotency everywhere** — discovery re-runs check schema hash before
   re-profiling. Same pattern as the data generator.
6. **LLM access via LangChain, routed through OpenRouter** (its
   OpenAI-compatible endpoint), never a hardcoded provider SDK call — model
   is a config-level swap, not a code change. Embeddings go direct to OpenAI
   (OpenRouter has no embeddings endpoint).
7. **Showcase deployment = no auth.** Single shared instance. Rate limiting
   only.

## Environment Variables Needed
```
OPENROUTER_API_KEY=          # LLM access via LangChain's OpenAI-compatible client, model is a config swap
OPENAI_API_KEY=               # embeddings (text-embedding-3-small) — OpenRouter has no embeddings endpoint
SUPABASE_DB_URL=postgres://...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=
```

## Stack
- Backend: Python + FastAPI
- Agent framework: LangChain (LLM/embeddings provider pluggable)
- Database: Supabase (Postgres + pgvector)
- Frontend: Next.js 14 (App Router)
- Charts: Apache ECharts or Plotly.js
- Dashboard layout: react-grid-layout
- Package manager: uv (Python), npm (frontend)
- Deployment target: Vercel (frontend) + Railway or Render (backend)

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
│   │   ├── query/               # query agent (NL -> SQL)
│   │   ├── db/
│   │   │   ├── connection.py
│   │   │   └── migrations/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   └── middleware/
│   │   ├── logging/
│   │   │   └── logger.py       # structlog setup, shared across app
│   │   ├── config.py            # cross-cutting tunables
│   │   └── main.py              # FastAPI entrypoint
│   ├── tests/
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/                     # Next.js 14, App Router
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── chat/                 # chat + chart UI
│   │   └── dashboards/           # dashboard builder
│   ├── components/
│   ├── lib/
│   │   ├── api-client.ts
│   │   └── logger.ts             # console wrapper, dev/prod aware
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.js
├── docs/                          # canon docs (this file and siblings)
├── docs/diagrams/                 # excalidraw
└── specs/                         # per-increment design specs
```
