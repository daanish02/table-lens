# table-lens — Foundation + Stage 1a (Discovery Agent) Design

## Status
Draft — pending user review.

## Purpose
Establish the project's backend/frontend split and build Stage 1a: an autonomous
discovery agent that profiles an unknown PostgreSQL database (schema + statistics +
inferred relationships), generates plain-English descriptions via an LLM, and embeds
them into pgvector for later retrieval by the query agent (Stage 1b, separate spec).

This is the first of several sub-project specs for table-lens (an AI-native
conversational BI product). Stage 1b (query agent), Stage 2 (chat+chart UI),
Stage 3 (dashboard builder) each get their own spec once the prior stage is
verified working. Stage 4 (RBAC/multi-tenant) is out of scope indefinitely.

## Product Context
table-lens: users ask natural-language questions, an agent queries Postgres,
returns results, generates visualizations, and persists charts/dashboards.
Demo/showcase deployment — no auth required initially. Full product roadmap
lives in `docs/PRD.md` (written as part of this spec).

## Decisions Made This Spec

1. **Repo layout — flat, not nested under `packages/`.** Full target layout
   (see `docs/PRD.md` for the canonical copy); this spec builds everything
   marked BUILD, scaffolds everything marked SCAFFOLD, leaves everything else
   as an empty/absent directory for a later spec:
   ```
   table-lens/
   ├── backend/
   │   ├── app/
   │   │   ├── generator/          # BUILD — relocated, logic+output frozen
   │   │   ├── discovery/          # BUILD — Stage 1a agent
   │   │   ├── query/               # not created this spec
   │   │   ├── db/                  # BUILD — connection + pgvector migrations
   │   │   ├── api/                 # BUILD — routes/, middleware/
   │   │   ├── logging/             # BUILD — structlog setup
   │   │   ├── config.py            # BUILD — cross-cutting tunables
   │   │   └── main.py              # BUILD — FastAPI entrypoint
   │   ├── tests/                    # BUILD — scaffold + tests for this spec's code
   │   ├── pyproject.toml
   │   └── uv.lock
   ├── frontend/                     # SCAFFOLD — Next.js 14 App Router, no pages yet
   │   ├── app/                      # SCAFFOLD — layout.tsx, page.tsx placeholder
   │   ├── lib/
   │   │   └── logger.ts             # BUILD — console wrapper, dev/prod aware
   │   ├── package.json
   │   ├── tsconfig.json
   │   └── next.config.js
   ├── docs/                         # BUILD — see Documentation section
   ├── docs/diagrams/                # BUILD — excalidraw
   └── specs/
   ```

2. **Frontend framework: Next.js 14 (App Router).** Chosen over plain
   React+Vite because Stage 3 dashboards are shareable by link with no auth —
   SSR gives fast first load and real OG previews for shared links. Adds
   server/client component split complexity but matches Vercel deploy target
   already decided. Not built out in this spec — scaffold only, since no UI
   work happens until Stage 2.

3. **LLM and embeddings access via LangChain, both routed through
   OpenRouter — not a hardcoded provider SDK call.** Discovery's description
   generation and embeddings both use LangChain's OpenAI-compatible client
   pointed at OpenRouter's endpoint (model is a `config.py` string, e.g.
   `anthropic/claude-sonnet-4.6` for chat, `openai/text-embedding-3-small`
   for embeddings) — swapping model or provider is a config change, not a
   code change. One API key for both.

4. **Config convention (applies backend-wide, not just generator):**
   - Cross-cutting tunables that matter project-wide → `config.py` (or
     `config/<name>.py` per module, only if a module accumulates many
     tunables of its own).
   - Local constants with low impact / no cross-file relevance → declared as
     constants at the top of the file that uses them, not promoted to
     `config.py`.
   - This gives explicit control over what's "tunable surface" vs. what's an
     implementation detail.

5. **Generator relocation is structure-only.** `sql-agent-data/*` moves into
   `backend/app/generator/`. File names, file boundaries (merge or split),
   and internal organization are free to change. `RANDOM_SEED`, `ROW_COUNTS`,
   business-logic constants, and all generation logic must NOT change —
   output must be byte-identical (verified by checksum diff, see Testing).
   Keep generator's footprint proportionate to the rest of the backend — it
   exists only to produce synthetic seed data, not to become the largest
   subsystem.

6. **Discovery is the only agent in this spec.** No query agent (Stage 1b)
   code. `POST /api/discover` and `GET /api/discover/status` are the only
   endpoints built here.

7. **Documentation is canon.** Everything written to `docs/` in this spec is
   the source of truth going forward — future questions get answered from
   these docs, and they must be updated whenever the implementation they
   describe changes. Stale docs are a bug.

8. **DB schema separation: generated insurance data lives in a dedicated
   `demo` schema, not `public`.** `public` is reserved for table-lens's own
   product/meta tables (`table_embeddings`, `column_embeddings`,
   `saved_charts`, `dashboards`). Mirrors a realistic "discovery agent
   profiles a foreign database" setup and avoids name collisions. Requires
   `backend/app/generator/schema/ddl.py` and `connector/loader.py` to take a
   schema parameter (currently create tables unqualified, defaulting to
   `public`) — in scope for this spec since the generator move already
   touches this code path.

9. **Logging: structlog (backend), console wrapper (frontend).** Backend:
   `backend/app/logging/logger.py` — structlog, JSON output, one shared
   config used by every backend component (generator, discovery, api). No
   bare `print`/ad-hoc logging calls in new code. Frontend:
   `frontend/lib/logger.ts` — thin wrapper over `console.*` with levels,
   dev/prod aware, no external error-tracking service (matches no-auth
   showcase scope, can be added later if needed).

## Architecture

### Backend components (`backend/app/`)
- `generator/` — relocated synthetic data generator (insurance domain, 50
  tables). Unchanged logic/output.
- `discovery/` — Stage 1a agent:
  - schema introspection (`information_schema` — tables, columns, types,
    PKs, FKs)
  - statistical profiler (`TABLESAMPLE BERNOULLI(2)` on large tables — row
    count, null rate, distinct count, numeric min/max/mean/p50/p95,
    categorical top-10, date min/max)
  - relationship inference (column name pattern matching + value-overlap
    sampling: 1000 random values from candidate FK column, % found in
    candidate PK table)
  - `llm.py` — LangChain LLM wrapper, generates table/column descriptions
    and flags redundant concepts across tables
  - `embeddings.py` — LangChain embeddings wrapper, writes to pgvector
- `db/` — Supabase/Postgres connection (read-only role at connection level,
  not just prompt-enforced), pgvector schema migrations
- `api/` — FastAPI routes: `POST /discover`, `GET /discover/status`
- `logging/` — structlog setup (JSON output), shared across all components
- `config.py` — sample sizes, LLM/embedding model choice, retry counts, etc.

### Frontend scaffold (`frontend/`)
Next.js 14 App Router skeleton — no chat/dashboard pages built yet. Includes
`lib/logger.ts` (console wrapper) and `lib/api-client.ts` stub for calling
the backend once Stage 1b exists.

### pgvector schema
```sql
CREATE TABLE table_embeddings (
    table_name   TEXT PRIMARY KEY,
    description  TEXT,
    embedding    vector(1536)
);

CREATE TABLE column_embeddings (
    table_name   TEXT,
    column_name  TEXT,
    description  TEXT,
    embedding    vector(1536),
    PRIMARY KEY (table_name, column_name)
);
```

## Data Flow

1. `POST /discover {db_url}` → check schema hash against manifest (same
   idempotency pattern as the generator) → skip if unchanged, else proceed.
2. Pull full schema from `information_schema`.
3. Profile every column via sampled queries.
4. Infer undeclared relationships (pattern match + overlap sampling).
5. Send structural + statistical profile to LLM (via LangChain) → generate
   plain-English table/column descriptions (what it's for, when to use it,
   gotchas, null behavior).
6. Detect redundant concepts stored in multiple tables, flag which to prefer.
7. Embed descriptions (via LangChain) → write to `table_embeddings` /
   `column_embeddings`.
8. Mark discovery run complete in manifest (hash-checked).
9. `GET /discover/status` polls progress/state throughout.

### Error handling
DB connection failure, LLM call failure, or embedding write failure at any
step: log the failure, surface current state via `/discover/status`, no
silent partial state. Retry resumes from the last completed step, not a full
restart.

## Documentation (this spec writes/updates)

All under `docs/`, treated as canon per Decision 7. HLD docs describe the
**entire project as one coherent whole** (all stages) — no stage/status tags
scattered through them. Build/rollout status lives solely in `PROGRESS.md`.
This spec only happens to be the first to write these files; every later
spec updates them rather than creating stage-scoped copies.

- `PRD.md` — full product vision and design, no stage tags
- `ARCHITECTURE.md` — full target system architecture, all components
- `SCHEMAS.md` — full data model (pgvector tables, generator's DB schema,
  `saved_charts`, `dashboards`, etc.)
- `APIS.md` — full API surface across the whole product
- `PROGRESS.md` — the ONLY place stage/build status lives: a table of
  stages and their status, updated as work lands

`docs/diagrams/` (Excalidraw, generic names, shallow nesting — 0th/1st level
only, 2nd level rare, never past 3rd):
- Technical architecture (infra + components, for technical readers)
- Business/non-technical architecture (for non-technical readers)
- User/data flow diagram
- Roadmap (stage timeline — this one IS status, linked from `PROGRESS.md`)

Explicitly deferred (add when the stage that needs them arrives):
SECURITY.md, DEPLOYMENT.md, RUNBOOK.md, THIRD-PARTY-SERVICES.md, UI.md.

## Testing / Verification

- **Generator move:** checksum-diff parquet output before and after
  relocation into `backend/app/generator/` — must match exactly.
- **Discovery agent:** run against the synthetic insurance DB (generator
  output loaded to Supabase). Verify schema pull correctness. Spot-check
  statistical profiles against a known table (e.g. `claims`, 30k rows).
  Verify relationship inference catches at least the obvious FK-like columns
  that lack a declared FK.
- **Embeddings:** manually query 5-10 sample questions against
  `table_embeddings`, confirm top-5 relevant tables returned sensibly.
- **Idempotency:** re-run discovery with unchanged schema → confirm skip.
  Change one column → confirm re-profile triggers for the affected table.
- **Logging:** confirm structlog emits JSON with request/run context (not
  plain `print`) for at least one path in each of generator, discovery, api.
  Confirm frontend logger wrapper is dev/prod aware (verbose in dev, quiet in
  prod).

## Out of Scope (this spec)
- Stage 1b query agent
- Any frontend pages/components (scaffold only)
- Auth, deployment, rate limiting, monitoring/runbook docs
