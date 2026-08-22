SELECT
    COUNT(*) AS table_count,
    COALESCE(SUM(column_count), 0) AS column_count,
    COALESCE(SUM(row_count), 0) AS row_count
FROM public.table_embeddings
