"""Lightweight schema sync for local SQLite when models gain new columns."""

import logging

from sqlalchemy import inspect, text

from app.db import Base

logger = logging.getLogger(__name__)


def _default_sql(col) -> str:
    if col.server_default is not None:
        return ""
    default = col.default
    if default is None or not hasattr(default, "arg"):
        return ""
    val = default.arg
    if callable(val):
        try:
            val = val()
        except TypeError:
            return ""
    if isinstance(val, bool):
        return f" DEFAULT {1 if val else 0}"
    if isinstance(val, (int, float)):
        return f" DEFAULT {val}"
    if isinstance(val, str):
        return f" DEFAULT '{val}'"
    return ""


def sync_missing_columns(connection) -> None:
    """Add columns that exist in models but not in the database (SQLite-safe)."""
    dialect_name = connection.dialect.name
    if dialect_name != "sqlite":
        return

    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing_cols:
                continue
            col_type = col.type.compile(dialect=connection.dialect)
            default_clause = _default_sql(col)
            # SQLite: new NOT NULL columns need a DEFAULT when table has rows.
            if not col.nullable and not default_clause:
                default_clause = " DEFAULT NULL"
                nullable = "NULL"
            else:
                nullable = "NULL" if col.nullable else "NOT NULL"
            ddl = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}{default_clause} {nullable}"
            logger.info("schema_migrate", extra={"extra_fields": {"ddl": ddl}})
            connection.execute(text(ddl))
        inspector = inspect(connection)
