CREATE TABLE IF NOT EXISTS public.saved_charts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title        TEXT,
    question     TEXT,
    sql          TEXT,
    chart_type   TEXT,
    chart_config JSONB,
    result_cache JSONB,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.dashboards (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title      TEXT,
    chart_ids  UUID[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);
