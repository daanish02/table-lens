CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.table_embeddings (
    table_name   TEXT PRIMARY KEY,
    description  TEXT,
    embedding    vector(1536)
);

CREATE TABLE IF NOT EXISTS public.column_embeddings (
    table_name   TEXT,
    column_name  TEXT,
    description  TEXT,
    embedding    vector(1536),
    PRIMARY KEY (table_name, column_name)
);
