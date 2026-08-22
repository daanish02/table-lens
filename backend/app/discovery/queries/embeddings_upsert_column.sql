INSERT INTO public.column_embeddings (table_name, column_name, description, embedding)
VALUES (:t, :c, :d, :e)
ON CONFLICT (table_name, column_name) DO UPDATE SET description = :d, embedding = :e
