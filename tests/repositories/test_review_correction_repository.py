from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from eval_lab.repositories.sqlite import (
    connect,
    initialize_database,
    insert_evaluation_result,
    insert_evaluation_run,
    insert_grader_condition,
    insert_grader_result,
    insert_human_review,
    insert_model_output_slot,
    insert_prompt_version,
    insert_task_pack,
    insert_test_case,
    insert_human_review_correction,
    get_human_review_correction_for_review,
    insert_human_review_correction_target,
    get_human_review_correction_target_for_review,
)


NOW = "2026-08-18T00:00:00Z"


@pytest.fixture
def conn(temporary_db_path: Path, repo_root: Path):
    connection = connect(temporary_db_path)
    initialize_database(connection, repo_root / "db" / "schema.sql")
    yield connection
    connection.close()


def _review_graph(conn: sqlite3.Connection) -> tuple[int, int]:
    pack_id = insert_task_pack(conn, {
        "pack_key": "correction-pack", "contract_version": "v1", "contract_hash": "contract",
        "language": "zh-CN", "title_min_chars": 4, "title_max_chars": 20,
        "summary_min_chars": 60, "summary_max_chars": 120, "key_points_count": 3,
        "key_point_min_chars": 6, "key_point_max_chars": 40, "created_at": NOW, "updated_at": NOW,
    })
    case_id = insert_test_case(conn, {
        "task_pack_id": pack_id, "case_key": "correction-case", "revision": 1, "split": "holdout",
        "source_material": "来源材料", "source_facts": [{"fact_id": "F01", "text": "事实"}],
        "required_fact_ids": ["F01"], "explicit_forbidden_claims": [], "task_notes": "任务说明",
        "feasibility_qa_status": "pass", "content_hash": "case", "created_at": NOW, "updated_at": NOW,
    })
    prompt_id = insert_prompt_version(conn, {
        "version_label": "v1", "prompt_text": "prompt", "change_reason": "baseline",
        "content_hash": "prompt", "status": "frozen", "owner_approved_at": NOW,
        "frozen_at": NOW, "created_at": NOW, "updated_at": NOW,
    })
    run_id = insert_evaluation_run(conn, {
        "comparison_group_id": "CORRECTION-COMP", "prompt_version_id": prompt_id, "split": "holdout",
        "case_set_hash": "cases", "contract_hash": "contract", "generator_product": "manual",
        "generator_visible_model": "not_visible", "environment_notes": "same", "protocol_version": "v1",
        "status": "open", "created_at": NOW, "updated_at": NOW,
    })
    output_id = insert_model_output_slot(conn, {
        "evaluation_run_id": run_id, "test_case_id": case_id, "candidate_id": "candidate-a1b2c3",
        "generation_packet_version": "generation-1.0", "generation_packet_hash": "a" * 64,
        "raw_response": '{"title":"回答"}', "output_hash": "b" * 64, "generated_at": NOW,
        "technical_retry_count": 0, "technical_retry_reasons": [], "created_at": NOW, "updated_at": NOW,
    })
    condition_id = insert_grader_condition(conn, {
        "grader_product": "grader", "grader_visible_model": "not_visible", "grader_prompt": "prompt",
        "grader_prompt_hash": "grader-prompt", "grader_prompt_version_label": "v1", "rubric": "rubric",
        "rubric_hash": "rubric", "rubric_version_label": "v1", "error_taxonomy": "taxonomy",
        "error_taxonomy_hash": "taxonomy", "error_taxonomy_version_label": "v1",
        "owner_approved_at": NOW, "created_at": NOW,
    })
    grader_id = insert_grader_result(conn, {
        "model_output_id": output_id, "grader_condition_id": condition_id,
        "blind_packet_version": "blind-grader-1.1", "blind_packet_hash": "c" * 64,
        "raw_payload": {}, "import_status": "valid", "normalized_semantic": {},
        "language_compliance": "pass", "readability": "pass", "primary_error_type": None,
        "secondary_error_types": [], "unsupported_claims": [], "reason": {}, "evidence": {},
        "created_at": NOW,
    })
    result_id = insert_evaluation_result(conn, {
        "model_output_id": output_id, "grader_result_id": grader_id, "grader_condition_id": condition_id,
        "aggregation_rule_version": "v1", "calculated_status": "pass", "blocking_reasons": [],
        "calculated_at": NOW,
    })
    review_id = insert_human_review(conn, {
        "evaluation_result_id": result_id, "review_scope": "sampled", "blind_review": True,
        "evidence": {"original": "evidence"}, "reason": "original review", "final_decision": "fail",
        "reviewed_at": NOW,
    })
    return review_id, result_id


def test_correction_table_is_append_only_and_preserves_original_review(conn: sqlite3.Connection) -> None:
    review_id, result_id = _review_graph(conn)
    correction_id = insert_human_review_correction(conn, {
        "original_human_review_id": review_id,
        "evaluation_result_id": result_id,
        "review_mode": "corrective-re-review",
        "correction_reason": "procedure-invalid",
        "reviewer_evidence": {"raw_root": "object"},
        "reviewer_reason": "The stored response is an object.",
        "corrected_final_decision": "pass",
        "corrected_at": NOW,
    })

    assert correction_id > 0
    assert get_human_review_correction_for_review(conn, review_id)["corrected_final_decision"] == "pass"
    original = conn.execute(
        "SELECT evaluation_result_id, final_decision, reason FROM human_reviews WHERE id = ?",
        (review_id,),
    ).fetchone()
    assert tuple(original) == (result_id, "fail", "original review")
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        insert_human_review_correction(conn, {
            "original_human_review_id": review_id, "evaluation_result_id": result_id,
            "review_mode": "corrective-re-review", "correction_reason": "second",
            "reviewer_evidence": {}, "reviewer_reason": "second", "corrected_final_decision": "pass",
            "corrected_at": NOW,
        })
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE human_review_corrections SET reviewer_reason = 'changed' WHERE id = ?", (correction_id,))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM human_review_corrections WHERE id = ?", (correction_id,))


def test_correction_foreign_key_and_original_evaluation_pair_are_enforced(conn: sqlite3.Connection) -> None:
    review_id, result_id = _review_graph(conn)
    with pytest.raises(sqlite3.IntegrityError, match="evaluation_result_id"):
        insert_human_review_correction(conn, {
            "original_human_review_id": review_id, "evaluation_result_id": result_id + 1,
            "review_mode": "corrective-re-review", "correction_reason": "reason",
            "reviewer_evidence": {"evidence": True}, "reviewer_reason": "reason",
            "corrected_final_decision": "pass", "corrected_at": NOW,
        })


def test_correction_target_is_append_only_and_matches_original_review(conn: sqlite3.Connection) -> None:
    review_id, result_id = _review_graph(conn)
    target_id = insert_human_review_correction_target(conn, {
        "original_human_review_id": review_id,
        "evaluation_result_id": result_id,
        "authorization_reason": "procedure-invalid review",
        "authorized_at": NOW,
    })
    assert target_id > 0
    assert get_human_review_correction_target_for_review(conn, review_id)["evaluation_result_id"] == result_id
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        insert_human_review_correction_target(conn, {
            "original_human_review_id": review_id,
            "evaluation_result_id": result_id,
            "authorization_reason": "second authorization",
            "authorized_at": NOW,
        })
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(
            "UPDATE human_review_correction_targets SET authorization_reason = 'changed' WHERE id = ?",
            (target_id,),
        )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM human_review_correction_targets WHERE id = ?", (target_id,))

    with pytest.raises(sqlite3.IntegrityError, match="evaluation_result_id"):
        insert_human_review_correction_target(conn, {
            "original_human_review_id": review_id,
            "evaluation_result_id": result_id + 1,
            "authorization_reason": "mismatched authorization",
            "authorized_at": NOW,
        })
