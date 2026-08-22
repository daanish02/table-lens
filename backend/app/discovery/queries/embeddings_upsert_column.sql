INSERT INTO public.column_embeddings (table_name, column_name, description, embedding, profile, content_hash)
VALUES (:t, :c, :d, :e, CAST(:profile AS jsonb), :hash)
ON CONFLICT (table_name, column_name) DO UPDATE SET
    description = :d, embedding = :e, profile = CAST(:profile AS jsonb), content_hash = :hash
