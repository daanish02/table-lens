# Table Lens

An AI-native conversational BI tool. Ask a question in plain English, an
agent queries a Postgres database, returns results, and (eventually)
generates charts and dashboards. Built as a demo/showcase — no auth.

Full product vision, architecture, schemas, and API surface live in
[`docs/`](docs/) — this file is just enough to get the project running
locally. `docs/PRD.md` is the canonical description of what this is and
where it's going; `docs/PROGRESS.md` tracks what's actually built so far.

## Stack

- **Backend:** Python (FastAPI), `uv` for packages, one shared venv for
  the API, discovery agent, and the synthetic data generator
- **Agent:** LangChain, routed through OpenRouter (model is a config swap)
- **Database:** Supabase (Postgres + pgvector)
- **Frontend:** Next.js 14 (App Router), `bun` for packages
- **Generator:** synthetic insurance dataset (50 tables, ~5.3M rows) that
  seeds the demo database

## Repo Layout

```
table-lens/
├── backend/
│   └── app/
│       ├── generator/    # synthetic data generator (frozen output — see docs/PRD.md)
│       ├── discovery/    # discovery agent: profile schema, describe via LLM, embed
│       ├── db/           # connection, migrations
│       ├── api/          # FastAPI routes
│       ├── utils/        # logging
│       └── config.py
├── frontend/              # Next.js 14
├── docs/                  # canon: PRD, ARCHITECTURE, SCHEMAS, APIS, PROGRESS
├── docs/diagrams/          # excalidraw
└── specs/                  # per-increment design specs
```

## Setup

Copy `.env.example` to `.env` and fill in:

```
OPENROUTER_API_KEY=      # LLM + embeddings
SUPABASE_DB_URL=         # Supabase connection string (pooler, session mode)
SUPABASE_DB_URL_READONLY=  # a read-only Postgres role — see docs/PRD.md
SUPABASE_URL=
SUPABASE_ANON_KEY=
```

### Backend

```bash
cd backend
uv sync
uv run pytest            # fast suite; add -m slow for real end-to-end LLM tests
uv run uvicorn app.main:app --reload --port 8001
```

### Generator (populate the demo database)

Only needed once, or after resetting the demo schema:

```bash
cd backend/app/generator
uv run generate.py               # writes parquet locally
uv run connector/loader.py       # loads into Supabase's `demo` schema
```

### Frontend

```bash
cd frontend
bun install
bun run dev               # http://localhost:3000
```

Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` if the backend
isn't on `http://localhost:8001`.

## Discovery Agent

Click "run discovery" in the frontend (or `POST /api/discover`) to profile
the demo schema and generate table/column descriptions via the LLM. This
makes real, paid API calls — it's gated behind an explicit trigger on
purpose, not run automatically. A full run is idempotent and resumable: if
it's interrupted partway (rate limit, low credits), re-running only
processes what's left.
