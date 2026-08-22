from functools import lru_cache
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import text, Engine

from app.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, EMBEDDING_MODEL, EMBEDDING_DIM
from app.discovery import queries
from app.utils.logger import get_logger

log = get_logger(__name__)


@lru_cache
def _get_embeddings():
    # OpenRouter also exposes an embeddings route via its OpenAI-compatible
    # endpoint — same key/base_url as the LLM, no separate provider needed.
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        dimensions=EMBEDDING_DIM,
    )


def embed_and_store(
    engine: Engine,
    table_name: str,
    table_description: str,
    column_descriptions: dict[str, str],
) -> None:
    embedder = _get_embeddings()

    # One batched API call for the table description + every column
    # description, instead of one call per description — cuts what was
    # N+1 sequential embedding round-trips per table down to 1.
    col_names = list(column_descriptions.keys())
    texts = [table_description] + [column_descriptions[c] for c in col_names]
    vectors = embedder.embed_documents(texts)
    table_vec, *col_vecs = vectors
    log.info(f"embedding table + {len(col_names)} columns: {table_name}")

    with engine.connect() as conn:
        conn.execute(
            text(queries.load("embeddings_upsert_table")),
            {"t": table_name, "d": table_description, "e": str(table_vec)},
        )

        for col_name, col_vec in zip(col_names, col_vecs):
            conn.execute(
                text(queries.load("embeddings_upsert_column")),
                {"t": table_name, "c": col_name, "d": column_descriptions[col_name], "e": str(col_vec)},
            )
        conn.commit()

    log.info(f"embeddings written for {table_name}: {len(column_descriptions)} columns")


def is_table_described(engine: Engine, table_name: str) -> bool:
    """A table already having an embedding entry means a prior run
    (possibly one that later failed on a different table) already
    finished it — used to resume without redoing completed work."""
    with engine.connect() as conn:
        row = conn.execute(text(queries.load("embeddings_table_exists")), {"t": table_name}).first()
    return row is not None


def list_table_descriptions(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(queries.load("embeddings_list_tables"))).mappings().all()
    return [dict(r) for r in rows]


def get_column_descriptions(engine: Engine, table_name: str) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(queries.load("embeddings_list_columns")), {"t": table_name}).mappings().all()
    return [dict(r) for r in rows]
