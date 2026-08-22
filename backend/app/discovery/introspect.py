from dataclasses import dataclass
from sqlalchemy import text, Engine

from app.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_pk: bool
    is_fk: bool
    fk_table: str | None
    fk_column: str | None


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo]


_COLUMNS_SQL = """
SELECT c.column_name, c.data_type
FROM information_schema.columns c
WHERE c.table_schema = :schema AND c.table_name = :table
ORDER BY c.ordinal_position
"""

_PK_SQL = """
SELECT kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
WHERE tc.table_schema = :schema AND tc.table_name = :table
  AND tc.constraint_type = 'PRIMARY KEY'
"""

_FK_SQL = """
SELECT kcu.column_name, ccu.table_name AS fk_table, ccu.column_name AS fk_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
WHERE tc.table_schema = :schema AND tc.table_name = :table
  AND tc.constraint_type = 'FOREIGN KEY'
"""

_TABLES_SQL = """
SELECT table_name FROM information_schema.tables
WHERE table_schema = :schema AND table_type = 'BASE TABLE'
ORDER BY table_name
"""


def get_schema_snapshot(engine: Engine, schema: str) -> list[TableInfo]:
    log.info(f"introspecting schema: {schema}")
    with engine.connect() as conn:
        table_names = [r[0] for r in conn.execute(text(_TABLES_SQL), {"schema": schema})]

        tables = []
        for table_name in table_names:
            pk_cols = {r[0] for r in conn.execute(text(_PK_SQL), {"schema": schema, "table": table_name})}
            fk_rows = {
                r[0]: (r[1], r[2])
                for r in conn.execute(text(_FK_SQL), {"schema": schema, "table": table_name})
            }
            columns = []
            for col_name, data_type in conn.execute(text(_COLUMNS_SQL), {"schema": schema, "table": table_name}):
                fk_table, fk_column = fk_rows.get(col_name, (None, None))
                columns.append(ColumnInfo(
                    name=col_name,
                    data_type=data_type,
                    is_pk=col_name in pk_cols,
                    is_fk=col_name in fk_rows,
                    fk_table=fk_table,
                    fk_column=fk_column,
                ))
            tables.append(TableInfo(name=table_name, columns=columns))

    log.info(f"introspected schema {schema}: {len(tables)} tables")
    return tables


def to_hashable(tables: list[TableInfo]) -> list[dict]:
    return [
        {"table": t.name, "columns": sorted(c.name for c in t.columns)}
        for t in tables
    ]
