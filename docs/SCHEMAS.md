# Table Lens — Schemas

## Status
Canon. Update whenever a table is added, changed, or removed. Build/rollout
progress lives in `docs/PROGRESS.md`, not here.

## Schema Separation
Generated insurance data lives in a dedicated `demo` Postgres schema — not
`public`. `public` is reserved for Table Lens's own product/meta tables
(pgvector embeddings, `saved_charts`, `dashboards`, `discovery_runs`). Keeps
"the data being analyzed" separate from "table-lens's own state," and
mirrors a realistic discovery-agent-profiles-a-foreign-database setup.

## Demo Database (`demo` schema, Supabase Postgres)
Populated by `backend/app/generator/`. 53 tables, insurance domain: customers
& parties, policies, claims, underwriting & risk, finance & accounting,
operations & compliance. Full DDL lives in generator source
(`backend/app/generator/schema/ddl.py`), not duplicated here — this doc
tracks product-level schema, not the synthetic seed data's internals.

## pgvector (`public` schema)
Discovery agent output. Two-level embeddings so retrieval can narrow from
table to column. Embedding dimension is 768 (OpenAI's
`text-embedding-3-small`, truncated from its native 1536).

```sql
CREATE TABLE table_embeddings (
    table_name    TEXT PRIMARY KEY,
    description   TEXT,
    embedding     vector(768),
    row_count     BIGINT,
    column_count  INT
);

CREATE TABLE column_embeddings (
    table_name    TEXT,
    column_name   TEXT,
    description   TEXT,
    embedding     vector(768),
    profile       JSONB,  -- ColumnProfile stats (null_rate, distinct_count, etc.)
    content_hash  TEXT,   -- per-column change detection, gates re-describe on re-run
    PRIMARY KEY (table_name, column_name)
);
```

## Product Tables

### `discovery_runs`
Tracks each discovery run's progress and status — backs
`GET /api/discover/status/{run_id}` and `GET /api/discover/overview`.

```sql
CREATE TABLE discovery_runs (
    run_id        UUID PRIMARY KEY,
    schema_hash   TEXT,
    status        TEXT,   -- pending / running / done / failed
    step          TEXT,   -- current pipeline step, while running
    error         TEXT,   -- last error, on failure
    total_tables  INT,
    tables_done   INT,
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ
);
```

### `saved_charts`
```sql
CREATE TABLE saved_charts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title        TEXT,
    question     TEXT,   -- the NL question that produced this chart
    sql          TEXT,
    chart_type   TEXT,
    chart_config JSONB,   -- axes, colours, options
    result_cache JSONB,   -- last result sample for preview
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
```

### `dashboards`
A flat list of chart ids under a title — there is no persisted layout (no
drag-and-drop positioning; see `PRD.md`'s Dashboard Builder section).

```sql
CREATE TABLE dashboards (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title      TEXT,
    chart_ids  UUID[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Idempotency
Two separate, purpose-built mechanisms — not a shared manifest:
- **Generator:** a local JSON manifest (`manifest.json`, not a DB table)
  tracks each table's schema hash, target row count, and generation
  timestamp; a table is skipped on re-run only if its parquet file exists
  and both the schema hash and row count still match.
- **Discovery:** DB-state-driven, per-column — `column_embeddings.content_hash`
  gates re-describing a column, so only changed columns get a new LLM call
  on re-run. No local manifest involved.
