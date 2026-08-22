INSERT INTO public.table_embeddings (table_name, description, embedding, row_count, column_count)
VALUES (:t, :d, :e, :row_count, :column_count)
ON CONFLICT (table_name) DO UPDATE SET
    description = :d, embedding = :e, row_count = :row_count, column_count = :column_count
