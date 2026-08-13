from __future__ import annotations

import sqlite3

import pytest

from eval_lab.application.prompts import create_prompt_version, freeze_prompt_version
from eval_lab.application.runs import (
    WorkflowError,
    assert_runs_comparable,
    close_run,
    create_evaluation_run,
)
from eval_lab.repositories.sqlite import connect, get_evaluation_run, initialize_database


NOW = "2026-08-13T00:00:00Z"
METADATA = {
    "case_set_hash": "case-set-hash",
    "contract_hash": "contract-hash",
    "generator_product": "ChatGPT",
    "generator_visible_model": "not_visible",
    "environment_notes": "new chat for each candidate",
    "protocol_version": "1.0",
    "created_at": NOW,
    "updated_at": NOW,
}


@pytest.fixture
def conn(temporary_db_path, repo_root):
    connection = connect(temporary_db_path)
    initialize_database(connection, repo_root / "db" / "schema.sql")
    yield connection
    connection.close()


def test_prompt_draft_freezes_and_holdout_requires_frozen_v2(conn: sqlite3.Connection) -> None:
    v1_id = create_prompt_version(conn, "baseline", "v1", "baseline")
    assert conn.execute("SELECT status FROM prompt_versions WHERE id = ?", (v1_id,)).fetchone()[0] == "draft"

    v2_id = create_prompt_version(conn, "revised", "v2", "dev evidence")
    with pytest.raises(WorkflowError, match="frozen"):
        create_evaluation_run(conn, v2_id, "HOLDOUT-COMP-01", "holdout", METADATA)

    freeze_prompt_version(conn, v2_id, NOW)
    create_evaluation_run(conn, v2_id, "HOLDOUT-COMP-01", "holdout", METADATA)
    assert conn.execute("SELECT frozen_at FROM prompt_versions WHERE id = ?", (v2_id,)).fetchone()[0] == NOW


def test_runs_require_metadata_are_comparable_and_can_close(conn: sqlite3.Connection) -> None:
    prompt_id = create_prompt_version(conn, "baseline", "v1", "baseline")
    with pytest.raises(WorkflowError, match="case_set_hash"):
        create_evaluation_run(conn, prompt_id, "DEV-COMP-01", "dev", {**METADATA, "case_set_hash": ""})

    first_id = create_evaluation_run(conn, prompt_id, "DEV-COMP-01", "dev", METADATA)
    second_id = create_evaluation_run(conn, prompt_id, "DEV-COMP-01", "dev", METADATA)
    first = get_evaluation_run(conn, first_id)
    second = get_evaluation_run(conn, second_id)
    assert first["status"] == "open"
    assert_runs_comparable(first, second)

    with pytest.raises(WorkflowError, match="comparison_group_id"):
        assert_runs_comparable(first, {**dict(second), "comparison_group_id": "OTHER"})
    with pytest.raises(WorkflowError, match="contract_hash"):
        assert_runs_comparable(first, {**dict(second), "contract_hash": "other-contract"})
    with pytest.raises(WorkflowError, match="generator_product"):
        assert_runs_comparable(first, {**dict(second), "generator_product": "Other"})

    close_run(conn, first_id)
    assert get_evaluation_run(conn, first_id)["status"] == "closed"
