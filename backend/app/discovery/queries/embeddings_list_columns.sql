SELECT column_name, description, profile FROM public.column_embeddings
WHERE table_name = :t
ORDER BY column_name
