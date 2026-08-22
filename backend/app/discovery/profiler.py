from pydantic import BaseModel, Field
from sqlalchemy import text, Engine

from app.config import (
    DISCOVERY_SAMPLE_PCT, DISCOVERY_LARGE_TABLE_ROWS, DISCOVERY_TOP_N_CATEGORICAL,
    DISCOVERY_PROFILE_BATCH_SIZE, DISCOVERY_HISTOGRAM_MAX_BUCKETS,
)
from app.discovery import queries
from app.discovery.introspect import TableInfo
from app.utils.logger import get_logger

log = get_logger(__name__)

NUMERIC_TYPES = {"integer", "bigint", "smallint", "numeric", "real", "double precision", "money"}
DATE_TYPES = {"date", "timestamp without time zone", "timestamp with time zone", "time without time zone", "time with time zone"}


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
    histogram: list[tuple] = Field(default_factory=list)  # numeric only: (bucket_min_value, count)


def _source(schema: str, table: str, row_count: int) -> str:
    if row_count > DISCOVERY_LARGE_TABLE_ROWS:
        return f"(SELECT * FROM {schema}.{table} TABLESAMPLE BERNOULLI({DISCOVERY_SAMPLE_PCT})) sampled"
    return f"{schema}.{table}"


def _row_count(conn, schema: str, table: str) -> int:
    return conn.execute(text(queries.load("profiler_row_count").format(schema=schema, table=table))).scalar()


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _profile_batch(conn, source: str, row_count: int, cols: list) -> dict[str, ColumnProfile]:
    """One SELECT covering null_rate + distinct_count + type-specific stats
    (numeric min/max/mean/p50/p95, or date min/max) for every column in this
    batch — replaces what used to be 1-2 separate round-trips PER COLUMN,
    the dominant cost across a wide schema (thousands of columns)."""
    expressions = []
    layout = []  # (col, kind), same order/index as the expressions above
    for idx, col in enumerate(cols):
        expressions.append(queries.load("profiler_batch_null_distinct_expr").format(column=col.name, idx=idx))
        if col.data_type in NUMERIC_TYPES:
            expressions.append(queries.load("profiler_batch_numeric_expr").format(column=col.name, idx=idx))
            layout.append((col, "numeric"))
        elif col.data_type in DATE_TYPES:
            expressions.append(queries.load("profiler_batch_date_expr").format(column=col.name, idx=idx))
            layout.append((col, "date"))
        else:
            layout.append((col, "categorical"))

    sql = queries.load("profiler_batch_select").format(expressions=", ".join(expressions), source=source)
    row = conn.execute(text(sql)).mappings().first()

    profiles = {}
    for idx, (col, kind) in enumerate(layout):
        profile = ColumnProfile(
            row_count=row_count,
            null_rate=float(row[f"c{idx}_null"] or 0.0),
            distinct_count=int(row[f"c{idx}_distinct"] or 0),
        )
        if kind == "numeric":
            profile.min_value = row[f"c{idx}_min"]
            profile.max_value = row[f"c{idx}_max"]
            mean, p50, p95 = row[f"c{idx}_mean"], row[f"c{idx}_p50"], row[f"c{idx}_p95"]
            profile.mean_value = float(mean) if mean is not None else None
            profile.p50 = float(p50) if p50 is not None else None
            profile.p95 = float(p95) if p95 is not None else None
        elif kind == "date":
            profile.min_value = row[f"c{idx}_min"]
            profile.max_value = row[f"c{idx}_max"]
        profiles[col.name] = profile

    return profiles


def profile_table(engine: Engine, schema: str, table: TableInfo) -> dict:
    log.info(f"profiling table: {table.name}")
    profiles: dict[str, ColumnProfile] = {}

    with engine.connect() as conn:
        row_count = _row_count(conn, schema, table.name)
        source = _source(schema, table.name, row_count)

        for batch in _chunks(table.columns, DISCOVERY_PROFILE_BATCH_SIZE):
            profiles.update(_profile_batch(conn, source, row_count, batch))

    # Top-N categorical values need their own GROUP BY per column — can't be
    # flattened into the batched aggregate query above. A wide table can
    # have hundreds of these. One connection per column paid full connection
    # setup cost every time (dominated the runtime); one connection for the
    # whole table risked the pooler killing it mid-run (seen in practice on
    # a 300+ column table). A connection per small chunk bounds lifetime
    # while amortizing setup cost across several columns.
    categorical_cols = [c for c in table.columns if c.data_type not in NUMERIC_TYPES and c.data_type not in DATE_TYPES]
    for chunk in _chunks(categorical_cols, DISCOVERY_PROFILE_BATCH_SIZE):
        with engine.connect() as conn:
            for col in chunk:
                rows = conn.execute(text(
                    queries.load("profiler_top_values").format(
                        column=col.name, source=source, limit=DISCOVERY_TOP_N_CATEGORICAL
                    )
                )).all()
                profiles[col.name].top_values = [(r[0], r[1]) for r in rows]

    # Histogram buckets for numeric columns — same connection-chunking
    # rationale as the categorical loop above. Skipped for columns with
    # <=1 distinct value (nothing to bucket) or an equal min/max (would
    # divide by zero in width_bucket).
    numeric_cols = [c for c in table.columns if c.data_type in NUMERIC_TYPES]
    for chunk in _chunks(numeric_cols, DISCOVERY_PROFILE_BATCH_SIZE):
        with engine.connect() as conn:
            for col in chunk:
                profile = profiles[col.name]
                if profile.distinct_count <= 1 or profile.min_value is None or profile.max_value == profile.min_value:
                    continue
                buckets = min(DISCOVERY_HISTOGRAM_MAX_BUCKETS, profile.distinct_count)
                rows = conn.execute(text(
                    queries.load("profiler_histogram").format(
                        column=col.name, source=source,
                        min_val=profile.min_value, max_val=profile.max_value, buckets=buckets,
                    )
                )).all()
                profile.histogram = [(r[2], r[1]) for r in rows]

    log.info(f"profiled table {table.name}: {len(profiles)} columns")
    return profiles
