UPDATE public.column_embeddings SET profile = CAST(:profile AS jsonb), content_hash = :hash
WHERE table_name = :t AND column_name = :c
