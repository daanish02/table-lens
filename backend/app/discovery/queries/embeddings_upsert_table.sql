INSERT INTO public.table_embeddings (table_name, description, embedding)
VALUES (:t, :d, :e)
ON CONFLICT (table_name) DO UPDATE SET description = :d, embedding = :e
