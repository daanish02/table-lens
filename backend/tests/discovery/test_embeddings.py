import os
import pytest
from unittest.mock import patch, MagicMock

from app.discovery.embeddings import embed_and_store
from app.discovery.profiler import ColumnProfile

requires_db = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="live network test — set RUN_LIVE_TESTS=1 to run",
)


@requires_db
def test_embed_and_store_writes_table_and_column_rows():
    from app.db.connection import get_engine
    from sqlalchemy import text

    engine = get_engine()
    with patch("app.discovery.embeddings.get_embeddings") as mock_get_emb:
        mock_emb = MagicMock()
        # embed_and_store batches table + column descriptions into one
        # embed_documents() call — return one vector per input text.
        mock_emb.embed_documents.side_effect = lambda texts: [[0.01] * 768 for _ in texts]
        mock_get_emb.return_value = mock_emb

        profile = ColumnProfile(row_count=42, null_rate=0.1, distinct_count=5, mean_value=3.2)
        embed_and_store(
            engine,
            table_name="__test_table",
            table_description="A test table.",
            column_descriptions={"col_a": "A test column."},
            profiles={"col_a": profile},
            row_count=42,
        )

    with engine.connect() as conn:
        table_row = conn.execute(
            text("SELECT description, row_count, column_count FROM public.table_embeddings WHERE table_name = :t"),
            {"t": "__test_table"},
        ).first()
        col_row = conn.execute(
            text("SELECT description, profile FROM public.column_embeddings WHERE table_name = :t AND column_name = :c"),
            {"t": "__test_table", "c": "col_a"},
        ).first()
        conn.execute(text("DELETE FROM public.table_embeddings WHERE table_name = :t"), {"t": "__test_table"})
        conn.execute(text("DELETE FROM public.column_embeddings WHERE table_name = :t"), {"t": "__test_table"})
        conn.commit()

    assert table_row[0] == "A test table."
    assert table_row[1] == 42
    assert table_row[2] == 1
    assert col_row[0] == "A test column."
    assert col_row[1]["distinct_count"] == 5
    assert col_row[1]["mean_value"] == 3.2
