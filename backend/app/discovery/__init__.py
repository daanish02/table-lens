"""The discovery agent — profiles an unknown Postgres schema (structure +
statistics + inferred relationships), describes it via an LLM, and embeds
the descriptions into pgvector. See docs/PRD.md for the full pipeline."""

from app.discovery.introspect import TableInfo, ColumnInfo, get_schema_snapshot, to_hashable
from app.discovery.profiler import ColumnProfile, profile_table
from app.discovery.relationships import InferredRelationship, infer_relationships
from app.discovery.llm import describe_table, describe_column
from app.discovery.embeddings import (
    embed_and_store, list_table_descriptions, get_column_descriptions, get_overview_stats,
)
from app.discovery.idempotency import get_last_run
from app.discovery.orchestrator import run_discovery, get_discovery_status

__all__ = [
    "TableInfo",
    "ColumnInfo",
    "get_schema_snapshot",
    "to_hashable",
    "ColumnProfile",
    "profile_table",
    "InferredRelationship",
    "infer_relationships",
    "describe_table",
    "describe_column",
    "embed_and_store",
    "list_table_descriptions",
    "get_column_descriptions",
    "get_overview_stats",
    "get_last_run",
    "run_discovery",
    "get_discovery_status",
]
