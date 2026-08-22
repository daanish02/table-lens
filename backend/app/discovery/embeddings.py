from functools import lru_cache
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import text, Engine

from app.config import EMBEDDING_MODEL
from app.logging.logger import get_logger

log = get_logger(__name__)


@lru_cache
def _get_embeddings():
    return OpenAIEmbeddings(model=EMBEDDING_MODEL)


def embed_and_store(
    engine: Engine,
    table_name: str,
    table_description: str,
    column_descriptions: dict[str, str],
) -> None:
    embedder = _get_embeddings()

    table_vec = embedder.embed_query(table_description)
    log.info("embeddings.table", table=table_name)

    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO public.table_embeddings (table_name, description, embedding) "
                "VALUES (:t, :d, :e) "
                "ON CONFLICT (table_name) DO UPDATE SET description = :d, embedding = :e"
            ),
            {"t": table_name, "d": table_description, "e": str(table_vec)},
        )

        for col_name, col_desc in column_descriptions.items():
            col_vec = embedder.embed_query(col_desc)
            conn.execute(
                text(
                    "INSERT INTO public.column_embeddings (table_name, column_name, description, embedding) "
                    "VALUES (:t, :c, :d, :e) "
                    "ON CONFLICT (table_name, column_name) DO UPDATE SET description = :d, embedding = :e"
                ),
                {"t": table_name, "c": col_name, "d": col_desc, "e": str(col_vec)},
            )
        conn.commit()

    log.info("embeddings.done", table=table_name, columns=len(column_descriptions))
