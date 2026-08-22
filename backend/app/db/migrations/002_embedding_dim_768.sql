-- Switching embedding dimension 1536 -> 768. Existing vectors are not
-- resizable in place (different dimension = different data), so this
-- clears prior discovery output. Re-running discovery repopulates them.
TRUNCATE TABLE public.table_embeddings, public.column_embeddings;

ALTER TABLE public.table_embeddings ALTER COLUMN embedding TYPE vector(768);
ALTER TABLE public.column_embeddings ALTER COLUMN embedding TYPE vector(768);
