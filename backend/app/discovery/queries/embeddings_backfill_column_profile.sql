UPDATE public.column_embeddings SET profile = CAST(:profile AS jsonb)
WHERE table_name = :t AND column_name = :c
