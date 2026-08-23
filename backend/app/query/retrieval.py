"""Two-layer semantic retrieval over discovery output: table-level first,
then column-level within a chosen table. Never the full schema — only
what's retrieved goes into the query agent's prompt (see docs/PRD.md,
Query Agent)."""

from sqlalchemy import text, Engine

from app.discovery.embeddings import get_embeddings
from app.query import queries
from app.utils.logger import get_logger

__all__ = ["search_tables", "search_columns"]

log = get_logger(__name__)


def search_tables(engine: Engine, query_text: str, top_k: int = 8) -> list[dict]:
    """Semantic search over table descriptions — the top_k closest tables
    to `query_text` by pgvector cosine distance."""
    vector = get_embeddings().embed_query(query_text)
    with engine.connect() as conn:
        rows = conn.execute(
            text(queries.load("search_tables")), {"query_vec": str(vector), "top_k": top_k}
        ).mappings().all()
    results = [dict(r) for r in rows]
    log.info(f"search_tables({query_text!r}): {len(results)} results, top={[r['table_name'] for r in results[:3]]}")
    return results


def search_columns(engine: Engine, table_name: str, query_text: str, top_k: int = 20) -> list[dict]:
    """Semantic search over one table's column descriptions — the top_k
    closest columns to `query_text`."""
    vector = get_embeddings().embed_query(query_text)
    with engine.connect() as conn:
        rows = conn.execute(
            text(queries.load("search_columns")),
            {"query_vec": str(vector), "table_name": table_name, "top_k": top_k},
        ).mappings().all()
    results = [dict(r) for r in rows]
    log.info(f"search_columns({table_name!r}, {query_text!r}): {len(results)} results")
    return results
