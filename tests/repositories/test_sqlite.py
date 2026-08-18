import sqlite3
from pathlib import Path

import pytest

from eval_lab.repositories.sqlite import (
    SchemaInitializationError,
    SchemaMigrationError,
    apply_migration,
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
    "human_review_corrections",
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


def test_migration_rolls_back_partial_changes_on_failure(
    temporary_db_path: Path, tmp_path: Path
) -> None:
    conn = connect(temporary_db_path)
    initialize_database(conn, Path(__file__).resolve().parents[2] / "db" / "schema.sql")
    migration_path = tmp_path / "broken_migration.sql"
    migration_path.write_text(
        "CREATE TABLE migration_partial (id INTEGER PRIMARY KEY);\n"
        "CREATE TABLE migration_broken (\n",
        encoding="utf-8",
    )
    try:
        with pytest.raises(SchemaMigrationError):
            apply_migration(conn, migration_path)
        assert "migration_partial" not in table_names(conn)
    finally:
        conn.close()


def test_human_review_correction_migration_is_atomic_and_idempotent(
    temporary_db_path: Path, repo_root: Path, tmp_path: Path
) -> None:
    full_schema = (repo_root / "db" / "schema.sql").read_text(encoding="utf-8")
    legacy_schema_path = tmp_path / "legacy_schema.sql"
    legacy_schema_path.write_text(
        full_schema.split("CREATE TABLE human_review_corrections", 1)[0].rstrip() + "\n",
        encoding="utf-8",
    )
    conn = connect(temporary_db_path)
    try:
        initialize_database(conn, legacy_schema_path)
        assert "human_review_corrections" not in table_names(conn)
        migration = repo_root / "db" / "migrations" / "001_human_review_corrections.sql"
        apply_migration(conn, migration)
        apply_migration(conn, migration)
        assert "human_review_corrections" in table_names(conn)
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'human_review_corrections_%'"
        ).fetchone()[0] == 3
    finally:
        conn.close()
