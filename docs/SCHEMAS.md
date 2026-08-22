# table-lens — Schemas

## Status
Canon. Update whenever a table is added, changed, or removed. Build/rollout
progress lives in `docs/PROGRESS.md`, not here.

## Schema Separation
Generated insurance data lives in a dedicated `demo` Postgres schema — not
`public`. `public` is reserved for table-lens's own product/meta tables
(pgvector embeddings, `saved_charts`, `dashboards`). Keeps "the data being
analyzed" separate from "table-lens's own state," and mirrors a realistic
discovery-agent-profiles-a-foreign-database setup.

## Demo Database (`demo` schema, Supabase Postgres)
Populated by `backend/app/generator/`. 50 tables, insurance domain: customers
& parties, policies, claims, underwriting & risk, finance & accounting,
operations & compliance. Full DDL lives in generator source
(`backend/app/generator/schema/ddl.py`), not duplicated here — this doc
tracks product-level schema, not the synthetic seed data's internals.

## pgvector (`public` schema)
Discovery agent output. Two-level embeddings so retrieval can narrow from
table to column.

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

## Product Tables

### `saved_charts`
```sql
CREATE TABLE saved_charts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title        TEXT,
    sql          TEXT,
    chart_type   TEXT,
    chart_config JSONB,   -- axes, colours, options
    result_cache JSONB,   -- last result sample for preview
    created_at   TIMESTAMP DEFAULT NOW()
);
```

### `dashboards`
```sql
CREATE TABLE dashboards (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title      TEXT,
    layout     JSONB,   -- react-grid-layout position/size config
    chart_ids  UUID[],
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Idempotency Manifest
Not a DB table — local JSON manifest (`manifest.json`) tracking per-table (or
per-discovery-run) schema hash, row count / config fingerprint, and
timestamp, so unchanged inputs are skipped on re-run. Same pattern reused for
both the generator and the discovery agent.
