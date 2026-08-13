from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sqlite3

import pytest

from eval_lab.application.grading import build_blind_grader_packet_for_output, calculate_output_status, import_grader_result
from eval_lab.application.outputs import evaluate_output_rules, record_model_output
from eval_lab.application.prompts import create_prompt_version
from eval_lab.application.reviews import (
    WorkflowError,
    build_blind_human_review_packet_for_result,
    record_human_review,
    required_review_targets,
    select_predeclared_review_sample,
)
from eval_lab.application.runs import create_evaluation_run
from eval_lab.domain.task_pack import TASK_PACK_CONTRACT, canonical_json_hash
from eval_lab.repositories.sqlite import connect, initialize_database, insert_grader_condition, insert_task_pack, insert_test_case


NOW = "2026-08-13T00:00:00Z"


@pytest.fixture
def conn(temporary_db_path: Path, repo_root: Path):
    connection = connect(temporary_db_path)
    initialize_database(connection, repo_root / "db" / "schema.sql")
    yield connection
    connection.close()


def _condition(conn: sqlite3.Connection) -> int:
    text_hash = lambda value: hashlib.sha256(value.encode()).hexdigest()
    return insert_grader_condition(conn, {
        "grader_product": "FORBIDDEN_GRADER_PRODUCT", "grader_visible_model": "FORBIDDEN_GRADER_MODEL",
        "grader_prompt": "FORBIDDEN_GRADER_PROMPT", "grader_prompt_hash": text_hash("FORBIDDEN_GRADER_PROMPT"), "grader_prompt_version_label": "grader-v1",
        "rubric": "FORBIDDEN_GRADER_RUBRIC", "rubric_hash": text_hash("FORBIDDEN_GRADER_RUBRIC"), "rubric_version_label": "rubric-v1",
        "error_taxonomy": "FORBIDDEN_ERROR_TAXONOMY", "error_taxonomy_hash": text_hash("FORBIDDEN_ERROR_TAXONOMY"), "error_taxonomy_version_label": "taxonomy-v1",
        "owner_approved_at": None, "created_at": NOW,
    })


def _make_results(conn: sqlite3.Connection, repo_root: Path, *, total: int = 5) -> tuple[list[int], int]:
    pack = insert_task_pack(conn, {"pack_key": "review-pack", "contract_version": "1", "contract_hash": "h", "language": "zh-CN", "title_min_chars": 4, "title_max_chars": 20, "summary_min_chars": 60, "summary_max_chars": 120, "key_points_count": 3, "key_point_min_chars": 6, "key_point_max_chars": 40, "created_at": NOW, "updated_at": NOW})
    condition_id = _condition(conn)
    condition = dict(conn.execute("SELECT * FROM grader_conditions WHERE id = ?", (condition_id,)).fetchone())
    results: list[int] = []
    for index in range(total):
        label = "v1" if index % 2 == 0 else "v2"
        prompt_id = create_prompt_version(conn, f"prompt {index}", f"{label}-review-{index}", "baseline")
        case = {"task_pack_id": pack, "case_key": f"review-{index}", "revision": 1, "split": "dev", "source_material": f"Source {index} gives fact F01.", "source_facts": [{"fact_id": "F01", "text": f"Fact {index}"}], "required_fact_ids": ["F01"], "explicit_forbidden_claims": [], "task_notes": "FORBIDDEN_TASK_INSTRUCTIONS", "feasibility_qa_status": "pass", "content_hash": f"case-{index}", "created_at": NOW, "updated_at": NOW}
        case_id = insert_test_case(conn, case)
        metadata = {"case_set_hash": "FORBIDDEN_CASE_SET", "contract_hash": "h", "generator_product": "FORBIDDEN_GENERATOR_PRODUCT", "generator_visible_model": "FORBIDDEN_GENERATOR_MODEL", "environment_notes": "FORBIDDEN_ENV", "protocol_version": "FORBIDDEN_PROTOCOL", "created_at": NOW, "updated_at": NOW}
        run_id = create_evaluation_run(conn, prompt_id, "REVIEW-COMP-01", "dev", metadata)
        output_id = record_model_output(conn, run_id, case_id, "generation-1.0", "a" * 64, '{"title":"Test","summary":"A sufficiently long summary with enough ordinary content to pass the check.","key_points":["One valid point","Two valid point","Three valid point"]}', NOW)
        evaluate_output_rules(conn, output_id, TASK_PACK_CONTRACT, [])
        packet = build_blind_grader_packet_for_output(conn, output_id, condition_id)
        payload = json.loads((repo_root / "tests" / "fixtures" / "demo_grader_valid.json").read_text(encoding="utf-8"))
        if index == 0:
            payload["language_compliance"] = {"label": "indeterminate", "reason": "ambiguous", "evidence": "limited"}
            payload["required_facts"][0]["label"] = "indeterminate"
            payload["primary_error_type"] = "ambiguous_evidence"
        if index == 1:
            payload["unsupported_claims"] = [{"claim": "unsupported", "output_evidence": "unsupported", "supporting_fact_ids": [], "reason": "not in source"}]
            payload["primary_error_type"] = "unsupported_claim"
        grader_id = import_grader_result(conn, output_id, condition, payload)
        results.append(calculate_output_status(conn, output_id, grader_id, condition_id))
    return results, condition_id


def test_blind_review_packet_hides_automatic_and_experiment_metadata(conn, repo_root: Path) -> None:
    results, _ = _make_results(conn, repo_root)
    packet = build_blind_human_review_packet_for_result(conn, results[0])
    assert set(packet["payload"]) == {"candidate_id", "user_task_output_contract", "source_material", "task_instructions", "constraints", "raw_model_response", "human_review_rubric", "decision_options"}
    contract_text = packet["payload"]["user_task_output_contract"]
    assert isinstance(contract_text, str)
    for expected in ("title", "summary", "key_points", "4", "20", "60", "120", "6", "40", "简体中文"):
        assert expected in contract_text
    exposed = packet["text"] + json.dumps(packet["payload"], ensure_ascii=False)
    for forbidden in ("\"split\"", "FORBIDDEN_GENERATOR_PRODUCT", "FORBIDDEN_GRADER_PROMPT", "FORBIDDEN_CASE_SET"):
        assert forbidden not in exposed


def test_record_human_review_only_writes_final_decision_and_preserves_automatic_result(conn, repo_root: Path) -> None:
    results, _ = _make_results(conn, repo_root)
    before = conn.execute("SELECT calculated_status FROM evaluation_results WHERE id = ?", (results[0],)).fetchone()[0]
    review_id = record_human_review(conn, results[0], "required", True, {"manual": "evidence"}, "Independent review", "pass")
    assert review_id > 0
    assert conn.execute("SELECT calculated_status FROM evaluation_results WHERE id = ?", (results[0],)).fetchone()[0] == before
    assert conn.execute("SELECT final_decision FROM human_reviews WHERE id = ?", (review_id,)).fetchone()[0] == "pass"
    with pytest.raises(WorkflowError, match="already exists"):
        record_human_review(conn, results[0], "required", True, {}, "again", "pass")


def test_predeclared_sampling_is_stable_stratified_and_independent_of_grader_outcomes(conn, repo_root: Path) -> None:
    results, _ = _make_results(conn, repo_root, total=6)
    first = select_predeclared_review_sample(conn, "REVIEW-COMP-01", 0.20)
    assert first == select_predeclared_review_sample(conn, "REVIEW-COMP-01", 0.20)
    rows = conn.execute("SELECT er.id, mo.candidate_id, run.prompt_version_id, run.split FROM evaluation_results er JOIN model_outputs mo ON mo.id = er.model_output_id JOIN evaluation_runs run ON run.id = mo.evaluation_run_id WHERE run.comparison_group_id = ?", ("REVIEW-COMP-01",)).fetchall()
    expected: list[int] = []
    for prompt_id in {row[2] for row in rows}:
        stratum = [row for row in rows if row[2] == prompt_id]
        ranked = sorted(stratum, key=lambda row: hashlib.sha256(row[1].encode("utf-8")).hexdigest())
        expected.extend(row[0] for row in ranked[:math.ceil(0.20 * len(stratum))])
    assert first == sorted(expected)
    conn.execute("UPDATE grader_results SET unsupported_claims_json = '[{\"claim\":\"later\"}]'")
    assert select_predeclared_review_sample(conn, "REVIEW-COMP-01", 0.20) == first


def test_required_review_queue_unions_exceptions_with_sample_from_remaining(conn, repo_root: Path) -> None:
    results, _ = _make_results(conn, repo_root, total=5)
    targets = required_review_targets(conn, "REVIEW-COMP-01")
    assert results[0] in targets
    assert results[1] in targets
    assert len(targets) >= 3
    assert targets == sorted(set(targets))
