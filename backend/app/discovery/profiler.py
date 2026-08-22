from pydantic import BaseModel, Field
from sqlalchemy import text, Engine

from app.config import DISCOVERY_SAMPLE_PCT, DISCOVERY_LARGE_TABLE_ROWS, DISCOVERY_TOP_N_CATEGORICAL
from app.discovery import queries
from app.discovery.introspect import TableInfo
from app.utils.logger import get_logger

log = get_logger(__name__)

NUMERIC_TYPES = {"integer", "bigint", "smallint", "numeric", "real", "double precision"}
DATE_TYPES = {"date", "timestamp without time zone", "timestamp with time zone"}


class ColumnProfile(BaseModel):
    # Not frozen — fields below are filled in progressively after
    # construction as different stats queries complete (see profile_table).
    row_count: int
    null_rate: float
    distinct_count: int
    min_value: object = None
    max_value: object = None
    mean_value: float | None = None
    p50: float | None = None
    p95: float | None = None
    top_values: list[tuple] = Field(default_factory=list)


def _source(schema: str, table: str, row_count: int) -> str:
    if row_count > DISCOVERY_LARGE_TABLE_ROWS:
        return f"(SELECT * FROM {schema}.{table} TABLESAMPLE BERNOULLI({DISCOVERY_SAMPLE_PCT})) sampled"
    return f"{schema}.{table}"


def _row_count(conn, schema: str, table: str) -> int:
    return conn.execute(text(queries.load("profiler_row_count").format(schema=schema, table=table))).scalar()


def profile_table(engine: Engine, schema: str, table: TableInfo) -> dict:
    log.info(f"profiling table: {table.name}")
    profiles: dict[str, ColumnProfile] = {}
    with engine.connect() as conn:
        row_count = _row_count(conn, schema, table.name)
        source = _source(schema, table.name, row_count)

        for col in table.columns:
            null_rate, distinct_count = conn.execute(text(
                queries.load("profiler_null_distinct").format(column=col.name, source=source)
            )).first()

            profile = ColumnProfile(
                row_count=row_count,
                null_rate=float(null_rate or 0.0),
                distinct_count=int(distinct_count or 0),
            )

            if col.data_type in NUMERIC_TYPES:
                stats = conn.execute(text(
                    queries.load("profiler_numeric_stats").format(column=col.name, source=source)
                )).first()
                profile.min_value, profile.max_value, mean, p50, p95 = stats
                profile.mean_value = float(mean) if mean is not None else None
                profile.p50 = float(p50) if p50 is not None else None
                profile.p95 = float(p95) if p95 is not None else None
            elif col.data_type in DATE_TYPES:
                min_v, max_v = conn.execute(text(
                    queries.load("profiler_date_range").format(column=col.name, source=source)
                )).first()
                profile.min_value, profile.max_value = min_v, max_v
            else:
                rows = conn.execute(text(
                    queries.load("profiler_top_values").format(
                        column=col.name, source=source, limit=DISCOVERY_TOP_N_CATEGORICAL
                    )
                )).all()
                profile.top_values = [(r[0], r[1]) for r in rows]

            profiles[col.name] = profile

    log.info(f"profiled table {table.name}: {len(profiles)} columns")
    return profiles
