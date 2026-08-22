-- Raw profile stats (null_rate, distinct_count, min/max/mean/p50/p95,
-- histogram buckets, top-N categorical values) were computed during
-- discovery but discarded after building the LLM prompt — only the
-- free-text description + embedding survived. A data-overview page needs
-- the numbers themselves, so persist them alongside.
ALTER TABLE public.column_embeddings ADD COLUMN IF NOT EXISTS profile JSONB;
ALTER TABLE public.table_embeddings ADD COLUMN IF NOT EXISTS row_count BIGINT;
ALTER TABLE public.table_embeddings ADD COLUMN IF NOT EXISTS column_count INT;
