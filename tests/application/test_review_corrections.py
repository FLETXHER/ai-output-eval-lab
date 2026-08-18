from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from eval_lab.application.reviews import (
    authorize_human_review_correction_target,
    WorkflowError,
    build_corrective_human_review_packet_for_result,
    effective_human_review_decision,
    record_human_review_correction,
)
from eval_lab.application.ui_queries import list_uncorrected_human_review_targets
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
)


NOW = "2026-08-18T00:00:00Z"
CORRECTION_REASON = (
    "Original blind Human Review was procedure-invalid because JSON-string encoding used by the "
    "review packet renderer for a raw response with a trailing newline was misinterpreted as "
    "evidence that the stored raw response itself had a JSON string root. Read-only audit "
    "confirmed the stored raw response parses as a JSON object and deterministic JSON/schema "
    "checks pass."
)


@pytest.fixture
def conn(temporary_db_path: Path, repo_root: Path):
    connection = connect(temporary_db_path)
    initialize_database(connection, repo_root / "db" / "schema.sql")
    yield connection
    connection.close()


def _review_graph(conn: sqlite3.Connection, suffix: str = "") -> tuple[int, int]:
    pack_id = insert_task_pack(conn, {
        "pack_key": f"correction-app-pack{suffix}", "contract_version": "v1", "contract_hash": "contract",
        "language": "zh-CN", "title_min_chars": 4, "title_max_chars": 20,
        "summary_min_chars": 60, "summary_max_chars": 120, "key_points_count": 3,
        "key_point_min_chars": 6, "key_point_max_chars": 40, "created_at": NOW, "updated_at": NOW,
    })
    case_id = insert_test_case(conn, {
        "task_pack_id": pack_id, "case_key": f"correction-app-case{suffix}", "revision": 1, "split": "holdout",
        "source_material": "来源材料", "source_facts": [{"fact_id": "F01", "text": "事实"}],
        "required_fact_ids": ["F01"], "explicit_forbidden_claims": [], "task_notes": "任务说明",
        "feasibility_qa_status": "pass", "content_hash": "case", "created_at": NOW, "updated_at": NOW,
    })
    prompt_id = insert_prompt_version(conn, {
        "version_label": f"v1{suffix}", "prompt_text": "prompt", "change_reason": "baseline",
        "content_hash": "prompt", "status": "frozen", "owner_approved_at": NOW,
        "frozen_at": NOW, "created_at": NOW, "updated_at": NOW,
    })
    run_id = insert_evaluation_run(conn, {
        "comparison_group_id": f"CORRECTION-APP-COMP{suffix}", "prompt_version_id": prompt_id, "split": "holdout",
        "case_set_hash": "cases", "contract_hash": "contract", "generator_product": "manual",
        "generator_visible_model": "not_visible", "environment_notes": "same", "protocol_version": "v1",
        "status": "open", "created_at": NOW, "updated_at": NOW,
    })
    output_id = insert_model_output_slot(conn, {
        "evaluation_run_id": run_id, "test_case_id": case_id, "candidate_id": f"candidate-a1b2c3{suffix}",
        "generation_packet_version": "generation-1.0", "generation_packet_hash": "a" * 64,
        "raw_response": '{"title":"回答","summary":"原始回答文本。","key_points":["第一条","第二条","第三条"]}\n',
        "output_hash": "b" * 64, "generated_at": NOW, "technical_retry_count": 0,
        "technical_retry_reasons": [], "created_at": NOW, "updated_at": NOW,
    })
    condition_id = insert_grader_condition(conn, {
        "grader_product": "grader", "grader_visible_model": "not_visible", "grader_prompt": "prompt",
        "grader_prompt_hash": f"grader-prompt{suffix}", "grader_prompt_version_label": "v1", "rubric": "rubric",
        "rubric_hash": f"rubric{suffix}", "rubric_version_label": "v1", "error_taxonomy": "taxonomy",
        "error_taxonomy_hash": f"taxonomy{suffix}", "error_taxonomy_version_label": "v1",
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


def test_correction_workflow_is_append_only_and_effective_layer_is_separate(conn: sqlite3.Connection) -> None:
    review_id, result_id = _review_graph(conn)
    authorize_human_review_correction_target(
        conn, review_id, result_id, "procedure-invalid review", authorized_at=NOW
    )
    automatic_before = conn.execute(
        "SELECT calculated_status FROM evaluation_results WHERE id = ?", (result_id,)
    ).fetchone()[0]
    original_before = tuple(conn.execute(
        "SELECT evaluation_result_id, final_decision, reason, evidence_json FROM human_reviews WHERE id = ?",
        (review_id,),
    ).fetchone())

    correction_id = record_human_review_correction(
        conn, review_id, result_id, CORRECTION_REASON,
        {"raw_root": "object", "json_parse_pass": "pass", "schema_pass": "pass"},
        "The literal raw response parses as a JSON object; the prior display was encoded.",
        "pass",
        corrected_at=NOW,
    )

    assert correction_id > 0
    assert effective_human_review_decision(conn, result_id) == "pass"
    assert tuple(conn.execute(
        "SELECT evaluation_result_id, final_decision, reason, evidence_json FROM human_reviews WHERE id = ?",
        (review_id,),
    ).fetchone()) == original_before
    assert conn.execute("SELECT calculated_status FROM evaluation_results WHERE id = ?", (result_id,)).fetchone()[0] == automatic_before
    correction = conn.execute("SELECT review_mode, correction_reason, reviewer_reason, corrected_final_decision FROM human_review_corrections WHERE id = ?", (correction_id,)).fetchone()
    assert tuple(correction) == (
        "corrective-re-review", CORRECTION_REASON,
        "The literal raw response parses as a JSON object; the prior display was encoded.", "pass",
    )

    with pytest.raises(WorkflowError, match="already has a correction"):
        record_human_review_correction(
            conn, review_id, result_id, CORRECTION_REASON, {"evidence": "again"}, "again", "pass", corrected_at=NOW
        )


def test_effective_decision_without_correction_is_original_decision(conn: sqlite3.Connection) -> None:
    _, result_id = _review_graph(conn)
    assert effective_human_review_decision(conn, result_id) == "fail"


def test_correction_ui_target_query_is_candidate_only_and_removes_corrected_target(
    conn: sqlite3.Connection,
) -> None:
    review_id, result_id = _review_graph(conn)
    assert list_uncorrected_human_review_targets(conn) == []
    authorize_human_review_correction_target(
        conn, review_id, result_id, "procedure-invalid review", authorized_at=NOW
    )
    rows = list_uncorrected_human_review_targets(conn)
    assert rows == [{
        "human_review_id": review_id,
        "evaluation_result_id": result_id,
        "candidate_id": "candidate-a1b2c3",
    }]
    assert "calculated_status" not in rows[0]
    record_human_review_correction(
        conn, review_id, result_id, CORRECTION_REASON, {"raw_root": "object"}, "corrected", "pass", corrected_at=NOW
    )
    assert list_uncorrected_human_review_targets(conn) == []


def test_correction_workflow_rejects_invalid_decision(conn: sqlite3.Connection) -> None:
    review_id, result_id = _review_graph(conn)
    authorize_human_review_correction_target(
        conn, review_id, result_id, "procedure-invalid review", authorized_at=NOW
    )
    with pytest.raises(WorkflowError, match="corrected_final_decision"):
        record_human_review_correction(
            conn, review_id, result_id, CORRECTION_REASON,
            {"evidence": "valid"}, "reason", "maybe", corrected_at=NOW,
        )


def test_correction_workflow_rejects_empty_reason(conn: sqlite3.Connection) -> None:
    review_id, result_id = _review_graph(conn)
    authorize_human_review_correction_target(
        conn, review_id, result_id, "procedure-invalid review", authorized_at=NOW
    )
    with pytest.raises(WorkflowError, match="correction_reason"):
        record_human_review_correction(
            conn, review_id, result_id, " ", {"evidence": "valid"}, "reason", "pass", corrected_at=NOW
        )


def test_correction_workflow_rejects_missing_original_review(conn: sqlite3.Connection) -> None:
    _, result_id = _review_graph(conn)
    with pytest.raises(WorkflowError, match="human review"):
        record_human_review_correction(
            conn, 999, result_id, CORRECTION_REASON, {"evidence": "valid"}, "reason", "pass", corrected_at=NOW
        )


def test_correction_workflow_rejects_mismatched_evaluation_result(conn: sqlite3.Connection) -> None:
    review_id, result_id = _review_graph(conn)
    with pytest.raises(WorkflowError, match="evaluation_result_id"):
        record_human_review_correction(
            conn, review_id, result_id + 1, CORRECTION_REASON,
            {"evidence": "valid"}, "reason", "pass", corrected_at=NOW
        )


def test_correction_packet_has_literal_raw_response_and_blind_allowlist(conn: sqlite3.Connection) -> None:
    review_id, result_id = _review_graph(conn)
    authorize_human_review_correction_target(
        conn, review_id, result_id, "procedure-invalid review", authorized_at=NOW
    )
    packet = build_corrective_human_review_packet_for_result(conn, result_id)
    raw_response = packet["payload"]["raw_model_response"]
    assert packet["packet_version"] == "blind-human-review-1.1"
    assert f"## 原始模型回答（逐字文本）\n{raw_response}" in packet["text"]
    assert '"{\\"title\\"' not in packet["text"]
    assert set(packet["payload"]) == {
        "candidate_id", "user_task_output_contract", "source_material", "task_instructions",
        "constraints", "raw_model_response", "human_review_rubric", "decision_options", "review_mode",
    }
    exposed = packet["text"] + json.dumps(packet["payload"], ensure_ascii=False)
    for forbidden in ("calculated_status", "grader_result", "prompt_version", "HOLDOUT-COMP"):
        assert forbidden not in exposed


def test_unapproved_human_review_cannot_be_corrected(conn: sqlite3.Connection) -> None:
    review_id, result_id = _review_graph(conn)
    with pytest.raises(WorkflowError, match="not authorized"):
        record_human_review_correction(
            conn, review_id, result_id, CORRECTION_REASON,
            {"raw_root": "object"}, "corrective reason", "pass", corrected_at=NOW,
        )


def test_only_authorized_targets_are_listed_and_four_targets_are_exactly_selectable(
    conn: sqlite3.Connection,
) -> None:
    reviews = [_review_graph(conn, suffix=f"-{index}") for index in range(5)]
    for review_id, result_id in reviews[:4]:
        authorize_human_review_correction_target(
            conn, review_id, result_id, "procedure-invalid review", authorized_at=NOW
        )

    rows = list_uncorrected_human_review_targets(conn)
    assert [row["human_review_id"] for row in rows] == [review_id for review_id, _ in reviews[:4]]
    assert reviews[4][0] not in [row["human_review_id"] for row in rows]


def test_correction_authorization_requires_matching_evaluation_result(conn: sqlite3.Connection) -> None:
    review_id, result_id = _review_graph(conn)
    with pytest.raises(WorkflowError, match="evaluation_result_id"):
        authorize_human_review_correction_target(
            conn, review_id, result_id + 1, "procedure-invalid review", authorized_at=NOW
        )
