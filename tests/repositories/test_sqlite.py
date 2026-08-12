import sqlite3
from pathlib import Path

import pytest

from eval_lab.repositories.sqlite import (
    SchemaInitializationError,
    connect,
    initialize_database,
    table_names,
    transaction,
)


APPROVED_TABLES = {
    "task_packs",
    "test_cases",
    "prompt_versions",
    "evaluation_runs",
    "model_outputs",
    "rule_results",
    "grader_conditions",
    "grader_results",
    "grader_fact_results",
    "evaluation_results",
    "human_reviews",
}


@pytest.fixture
def initialized_connection(temporary_db_path: Path, repo_root: Path):
    conn = connect(temporary_db_path)
    initialize_database(conn, repo_root / "db" / "schema.sql")
    yield conn
    conn.close()


def test_connect_enables_foreign_keys(temporary_db_path: Path) -> None:
    conn = connect(temporary_db_path)
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_initialize_database_creates_only_approved_tables(
    initialized_connection: sqlite3.Connection,
) -> None:
    assert table_names(initialized_connection) == APPROVED_TABLES


def test_foreign_key_violation_is_rejected(initialized_connection: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        initialized_connection.execute(
            """
            INSERT INTO test_cases (
                task_pack_id, case_key, revision, split, source_material,
                source_facts_json, required_fact_ids_json,
                explicit_forbidden_claims_json, task_notes,
                feasibility_qa_status, content_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                999,
                "case-001",
                1,
                "dev",
                "source",
                "[]",
                "[]",
                "[]",
                "notes",
                "pending",
                "hash",
                "2026-08-13T00:00:00Z",
                "2026-08-13T00:00:00Z",
            ),
        )


def test_transaction_rolls_back_rows_when_an_exception_occurs(
    initialized_connection: sqlite3.Connection,
) -> None:
    with pytest.raises(RuntimeError, match="stop"):
        with transaction(initialized_connection):
            initialized_connection.execute(
                """
                INSERT INTO task_packs (
                    pack_key, contract_version, contract_hash, language,
                    title_min_chars, title_max_chars, summary_min_chars,
                    summary_max_chars, key_points_count,
                    key_point_min_chars, key_point_max_chars, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "grounded-brief",
                    "1.0",
                    "hash",
                    "zh-CN",
                    4,
                    20,
                    60,
                    120,
                    3,
                    10,
                    30,
                    "2026-08-13T00:00:00Z",
                    "2026-08-13T00:00:00Z",
                ),
            )
            raise RuntimeError("stop")

    assert initialized_connection.execute("SELECT COUNT(*) FROM task_packs").fetchone()[0] == 0


def test_broken_schema_rolls_back_all_previously_created_tables(
    temporary_db_path: Path, tmp_path: Path
) -> None:
    broken_schema_path = tmp_path / "broken_schema.sql"
    broken_schema_path.write_text(
        "CREATE TABLE valid_table (id INTEGER PRIMARY KEY);\nCREATE TABLE broken (\n",
        encoding="utf-8",
    )
    conn = connect(temporary_db_path)
    try:
        with pytest.raises(SchemaInitializationError):
            initialize_database(conn, broken_schema_path)

        assert table_names(conn) == set()
    finally:
        conn.close()
