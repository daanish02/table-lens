from collections import defaultdict
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text, Engine

from app.discovery import queries
from app.utils.logger import get_logger

log = get_logger(__name__)


class ColumnInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    data_type: str
    is_pk: bool
    is_fk: bool
    fk_table: str | None
    fk_column: str | None


class TableInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    columns: list[ColumnInfo]


def get_schema_snapshot(engine: Engine, schema: str) -> list[TableInfo]:
    log.info(f"introspecting schema: {schema}")
    with engine.connect() as conn:
        table_names = [r[0] for r in conn.execute(text(queries.load("introspect_tables")), {"schema": schema})]

        pk_by_table: dict[str, set[str]] = defaultdict(set)
        for table_name, col_name in conn.execute(text(queries.load("introspect_primary_keys")), {"schema": schema}):
            pk_by_table[table_name].add(col_name)

        fk_by_table: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
        for table_name, col_name, fk_table, fk_column in conn.execute(text(queries.load("introspect_foreign_keys")), {"schema": schema}):
            fk_by_table[table_name][col_name] = (fk_table, fk_column)

        columns_by_table: dict[str, list[ColumnInfo]] = defaultdict(list)
        for table_name, col_name, data_type in conn.execute(text(queries.load("introspect_columns")), {"schema": schema}):
            fk_table, fk_column = fk_by_table[table_name].get(col_name, (None, None))
            columns_by_table[table_name].append(ColumnInfo(
                name=col_name,
                data_type=data_type,
                is_pk=col_name in pk_by_table[table_name],
                is_fk=col_name in fk_by_table[table_name],
                fk_table=fk_table,
                fk_column=fk_column,
            ))

        tables = [TableInfo(name=t, columns=columns_by_table[t]) for t in table_names]

    log.info(f"introspected schema {schema}: {len(tables)} tables")
    return tables


def to_hashable(tables: list[TableInfo]) -> list[dict]:
    return [
        {"table": t.name, "columns": sorted((c.name, c.data_type) for c in t.columns)}
        for t in tables
    ]
