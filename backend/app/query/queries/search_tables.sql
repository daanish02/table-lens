SELECT table_name, description, row_count, column_count,
       1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
FROM public.table_embeddings
WHERE embedding IS NOT NULL
ORDER BY embedding <=> CAST(:query_vec AS vector)
LIMIT :top_k
