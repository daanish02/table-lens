CREATE TABLE IF NOT EXISTS public.discovery_runs (
    run_id       TEXT PRIMARY KEY,
    schema_hash  TEXT NOT NULL,
    status       TEXT NOT NULL,
    step         TEXT,
    error        TEXT,
    started_at   TIMESTAMPTZ DEFAULT NOW(),
    finished_at  TIMESTAMPTZ
);
