from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import ContextManager


class SchemaInitializationError(RuntimeError):
    """Raised when schema initialization cannot complete atomically."""


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _complete_statements(schema_sql: str) -> Iterator[str]:
    statement = ""
    for line in schema_sql.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            complete_statement = statement.strip()
            if complete_statement:
                yield complete_statement
            statement = ""

    if statement.strip():
        raise ValueError("schema contains an incomplete SQL statement")


def initialize_database(conn: sqlite3.Connection, schema_path: str | Path) -> None:
    try:
        schema_sql = Path(schema_path).read_text(encoding="utf-8")
        conn.execute("BEGIN")
        for statement in _complete_statements(schema_sql):
            conn.execute(statement)
        conn.execute("COMMIT")
    except (OSError, sqlite3.Error, ValueError) as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise SchemaInitializationError("database schema initialization failed") from exc


@contextmanager
def transaction(conn: sqlite3.Connection) -> ContextManager[sqlite3.Connection]:
    conn.execute("BEGIN")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )
    return {row[0] for row in rows}
