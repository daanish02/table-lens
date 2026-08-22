SELECT column_name, description, profile,
       1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
FROM public.column_embeddings
WHERE table_name = :table_name AND embedding IS NOT NULL
ORDER BY embedding <=> CAST(:query_vec AS vector)
LIMIT :top_k
