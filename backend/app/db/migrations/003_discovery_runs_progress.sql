-- discovery_runs is normally created lazily (idempotency.ensure_runs_table,
-- called on first use, after migrations run) — so on a fresh DB it may not
-- exist yet here. CREATE handles that case; ALTER handles the case where it
-- already existed before these columns did.
CREATE TABLE IF NOT EXISTS public.discovery_runs (
    run_id        TEXT PRIMARY KEY,
    schema_hash   TEXT NOT NULL,
    status        TEXT NOT NULL,
    step          TEXT,
    error         TEXT,
    total_tables  INT,
    tables_done   INT DEFAULT 0,
    started_at    TIMESTAMPTZ DEFAULT NOW(),
    finished_at   TIMESTAMPTZ
);

ALTER TABLE public.discovery_runs ADD COLUMN IF NOT EXISTS total_tables INT;
ALTER TABLE public.discovery_runs ADD COLUMN IF NOT EXISTS tables_done INT DEFAULT 0;
