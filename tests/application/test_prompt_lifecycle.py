from __future__ import annotations

import sqlite3

import pytest

from eval_lab.application.prompts import (
    WorkflowError,
    approve_prompt_version,
    create_prompt_v2_after_dev,
    create_prompt_version,
    freeze_prompt_version,
)
from eval_lab.application.runs import (
    assert_runs_comparable,
    close_run,
    create_evaluation_run,
)
from eval_lab.domain.task_pack import TASK_PACK_CONTRACT, canonical_json_hash
from eval_lab.repositories.sqlite import (
    connect,
    get_evaluation_run,
    initialize_database,
    insert_evaluation_result,
    insert_grader_condition,
    insert_task_pack,
    insert_test_case,
)


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

    with pytest.raises(WorkflowError, match="owner-approved"):
        freeze_prompt_version(conn, v2_id, NOW)
    approve_prompt_version(conn, v2_id, NOW)
    freeze_prompt_version(conn, v2_id, NOW)
    create_evaluation_run(conn, v2_id, "HOLDOUT-COMP-01", "holdout", METADATA)
    assert conn.execute("SELECT frozen_at FROM prompt_versions WHERE id = ?", (v2_id,)).fetchone()[0] == NOW


def test_create_prompt_v2_requires_closed_dev_run_results_and_change_reason(
    conn: sqlite3.Connection,
) -> None:
    v1_id = create_prompt_version(conn, "baseline", "v1", "baseline")
    dev_run_id = create_evaluation_run(conn, v1_id, "DEV-COMP-01", "dev", METADATA)

    with pytest.raises(WorkflowError, match="closed"):
        create_prompt_v2_after_dev(conn, dev_run_id, "revised", "dev failures")

    close_run(conn, dev_run_id)
    with pytest.raises(WorkflowError, match="evaluation_results"):
        create_prompt_v2_after_dev(conn, dev_run_id, "revised", "dev failures")
    with pytest.raises(WorkflowError, match="change_reason"):
        create_prompt_v2_after_dev(conn, dev_run_id, "revised", "")

    _record_completed_evaluation_result(conn, dev_run_id)
    v2_id = create_prompt_v2_after_dev(conn, dev_run_id, "revised", "dev failures")
    v2 = conn.execute("SELECT * FROM prompt_versions WHERE id = ?", (v2_id,)).fetchone()
    assert v2["version_label"] == "v2"
    assert v2["status"] == "draft"
    assert v2["owner_approved_at"] is None


def _record_completed_evaluation_result(conn: sqlite3.Connection, run_id: int) -> None:
    pack_id = insert_task_pack(
        conn,
        {
            "pack_key": TASK_PACK_CONTRACT["pack_key"],
            "contract_version": TASK_PACK_CONTRACT["contract_version"],
            "contract_hash": canonical_json_hash(TASK_PACK_CONTRACT),
            "language": TASK_PACK_CONTRACT["language"],
            "title_min_chars": TASK_PACK_CONTRACT["title_min_chars"],
            "title_max_chars": TASK_PACK_CONTRACT["title_max_chars"],
            "summary_min_chars": TASK_PACK_CONTRACT["summary_min_chars"],
            "summary_max_chars": TASK_PACK_CONTRACT["summary_max_chars"],
            "key_points_count": TASK_PACK_CONTRACT["key_points_count"],
            "key_point_min_chars": TASK_PACK_CONTRACT["key_point_min_chars"],
            "key_point_max_chars": TASK_PACK_CONTRACT["key_point_max_chars"],
            "created_at": NOW,
            "updated_at": NOW,
        },
    )
    case_data = {
        "case_key": "dev-v1-case",
        "revision": 1,
        "split": "dev",
        "source_material": "来源事实。",
        "source_facts": [{"fact_id": "F01", "text": "来源事实。"}],
        "required_fact_ids": ["F01"],
        "explicit_forbidden_claims": [],
        "task_notes": "包含来源事实。",
        "feasibility_qa_status": "pass",
    }
    case_id = insert_test_case(
        conn,
        {
            **case_data,
            "task_pack_id": pack_id,
            "content_hash": canonical_json_hash(case_data),
            "created_at": NOW,
            "updated_at": NOW,
        },
    )
    output_id = conn.execute(
        """
        INSERT INTO model_outputs (
            evaluation_run_id, test_case_id, candidate_id, generation_packet_version,
            generation_packet_hash, raw_response, output_hash, generated_at,
            technical_retry_count, technical_retry_reasons_json, created_at, updated_at
        ) VALUES (?, ?, 'candidate-1', '1.0', ?, '{}', ?, ?, 0, '[]', ?, ?)
        """,
        (run_id, case_id, "a" * 64, "b" * 64, NOW, NOW, NOW),
    ).lastrowid
    condition_id = insert_grader_condition(
        conn,
        {
            "grader_product": "manual",
            "grader_visible_model": "not_visible",
            "grader_prompt": "grader prompt",
            "grader_prompt_hash": "a" * 64,
            "grader_prompt_version_label": "v1",
            "rubric": "rubric",
            "rubric_hash": "b" * 64,
            "rubric_version_label": "v1",
            "error_taxonomy": "taxonomy",
            "error_taxonomy_hash": "c" * 64,
            "error_taxonomy_version_label": "v1",
            "owner_approved_at": NOW,
            "created_at": NOW,
        },
    )
    insert_evaluation_result(
        conn,
        {
            "model_output_id": output_id,
            "grader_result_id": None,
            "grader_condition_id": condition_id,
            "aggregation_rule_version": "1.0",
            "calculated_status": "indeterminate",
            "blocking_reasons": ["grader missing"],
            "calculated_at": NOW,
        },
    )


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
