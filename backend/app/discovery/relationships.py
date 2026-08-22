from dataclasses import dataclass
from sqlalchemy import text, Engine

from app.config import DISCOVERY_FK_OVERLAP_SAMPLE, DISCOVERY_FK_OVERLAP_THRESHOLD
from app.discovery.introspect import TableInfo
from app.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class InferredRelationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    overlap_pct: float


def _candidate_columns(tables: list[TableInfo]) -> list[tuple[str, str]]:
    """Columns named like a foreign key (ends in _id, isn't its own table's PK,
    and has no declared FK) are candidates for overlap testing."""
    candidates = []
    for table in tables:
        for col in table.columns:
            if col.is_fk:
                continue
            if col.name.endswith("_id") and not (col.is_pk and col.name == f"{table.name[:-1]}_id"):
                candidates.append((table.name, col.name))
    return candidates


def _target_table_guess(column_name: str, tables: list[TableInfo]) -> str | None:
    stem = column_name[: -len("_id")]
    for plural_suffix in ("s", "es", ""):
        guess = f"{stem}{plural_suffix}"
        if any(t.name == guess for t in tables):
            return guess
    return None


def infer_relationships(engine: Engine, schema: str, tables: list[TableInfo]) -> list[InferredRelationship]:
    log.info(f"inferring relationships for schema: {schema}")
    results = []
    table_names = {t.name for t in tables}
    pk_by_table = {
        t.name: next((c.name for c in t.columns if c.is_pk), None) for t in tables
    }

    with engine.connect() as conn:
        for from_table, from_col in _candidate_columns(tables):
            target = _target_table_guess(from_col, tables)
            if not target or target not in table_names:
                continue
            to_col = pk_by_table.get(target)
            if not to_col:
                continue

            sample = conn.execute(text(
                f"SELECT {from_col} FROM {schema}.{from_table} "
                f"WHERE {from_col} IS NOT NULL ORDER BY random() "
                f"LIMIT {DISCOVERY_FK_OVERLAP_SAMPLE}"
            )).scalars().all()
            if not sample:
                continue

            found = conn.execute(text(
                f"SELECT COUNT(*) FROM {schema}.{target} WHERE {to_col} = ANY(:vals)"
            ), {"vals": list(sample)}).scalar()

            overlap_pct = found / len(sample)
            if overlap_pct >= DISCOVERY_FK_OVERLAP_THRESHOLD:
                results.append(InferredRelationship(
                    from_table=from_table, from_column=from_col,
                    to_table=target, to_column=to_col,
                    overlap_pct=overlap_pct,
                ))

    log.info(f"relationships inferred for {schema}: {len(results)} found")
    return results
