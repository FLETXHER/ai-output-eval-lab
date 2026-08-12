import json
import sqlite3
from pathlib import Path

import pytest

from eval_lab.repositories.sqlite import (
    connect,
    freeze_prompt_version,
    get_evaluation_run,
    insert_evaluation_result,
    insert_evaluation_run,
    insert_grader_condition,
    insert_grader_fact_results,
    insert_grader_result,
    insert_human_review,
    insert_model_output_slot,
    insert_prompt_version,
    insert_rule_results,
    insert_task_pack,
    insert_test_case,
    fetch_output_context,
    fetch_raw_response,
    fetch_retry_count,
    initialize_database,
    list_test_cases,
    update_run_status,
    update_technical_retry,
)


NOW = "2026-08-13T00:00:00Z"


@pytest.fixture
def initialized_connection(temporary_db_path: Path, repo_root: Path):
    conn = connect(temporary_db_path)
    initialize_database(conn, repo_root / "db" / "schema.sql")
    yield conn
    conn.close()


def task_pack_data() -> dict[str, object]:
    return {
        "pack_key": "grounded-structured-brief",
        "contract_version": "v1",
        "contract_hash": "contract-hash",
        "language": "zh-CN",
        "title_min_chars": 4,
        "title_max_chars": 20,
        "summary_min_chars": 60,
        "summary_max_chars": 120,
        "key_points_count": 3,
        "key_point_min_chars": 6,
        "key_point_max_chars": 40,
        "created_at": NOW,
        "updated_at": NOW,
    }


def case_data(task_pack_id: int, *, case_key: str = "case-001", split: str = "dev") -> dict[str, object]:
    return {
        "task_pack_id": task_pack_id,
        "case_key": case_key,
        "revision": 1,
        "split": split,
        "source_material": "星河牌随身灯重量为120克，包装含USB-C充电线。",
        "source_facts": [{"fact_id": "F01", "text": "重量为120克。"}, {"fact_id": "F02", "text": "包装含USB-C充电线。"}],
        "required_fact_ids": ["F01"],
        "explicit_forbidden_claims": ["防水"],
        "task_notes": "请用简体中文生成结构化短内容，必须说明重量。",
        "feasibility_qa_status": "pass",
        "content_hash": "case-hash",
        "created_at": NOW,
        "updated_at": NOW,
    }


def prompt_data(*, label: str = "v1") -> dict[str, object]:
    return {
        "version_label": label,
        "prompt_text": "根据材料生成JSON。",
        "change_reason": "baseline",
        "content_hash": f"prompt-{label}-hash",
        "status": "draft",
        "owner_approved_at": None,
        "frozen_at": None,
        "created_at": NOW,
        "updated_at": NOW,
    }


def run_data(prompt_version_id: int, *, split: str = "dev") -> dict[str, object]:
    return {
        "comparison_group_id": "DEV-COMP-01",
        "prompt_version_id": prompt_version_id,
        "split": split,
        "case_set_hash": "case-set-hash",
        "contract_hash": "contract-hash",
        "generator_product": "ChatGPT",
        "generator_visible_model": "not_visible",
        "environment_notes": "new chat for every candidate",
        "protocol_version": "v1",
        "status": "draft",
        "created_at": NOW,
        "updated_at": NOW,
    }


def output_data(run_id: int, test_case_id: int) -> dict[str, object]:
    return {
        "evaluation_run_id": run_id,
        "test_case_id": test_case_id,
        "candidate_id": "candidate-a1b2c3",
        "generation_packet_version": "generation-packet-v1",
        "generation_packet_hash": "generation-packet-hash",
        "raw_response": '{"title":"随身灯","summary":"星河牌随身灯重量为120克，包装含USB-C充电线。","key_points":["重量为120克","包装含USB-C充电线","适合随身携带"]}',
        "output_hash": "output-hash",
        "generated_at": NOW,
        "technical_retry_count": 0,
        "technical_retry_reasons": [],
        "created_at": NOW,
        "updated_at": NOW,
    }


def grader_condition_data() -> dict[str, object]:
    return {
        "grader_product": "Gemini",
        "grader_visible_model": "not_visible",
        "grader_prompt": "评估候选答案。",
        "grader_prompt_hash": "grader-prompt-hash",
        "grader_prompt_version_label": "v1",
        "rubric": "必须覆盖required facts。",
        "rubric_hash": "rubric-hash",
        "rubric_version_label": "v1",
        "error_taxonomy": "unsupported_claim",
        "error_taxonomy_hash": "taxonomy-hash",
        "error_taxonomy_version_label": "v1",
        "owner_approved_at": NOW,
        "created_at": NOW,
    }


def grader_result_data(model_output_id: int, grader_condition_id: int) -> dict[str, object]:
    return {
        "model_output_id": model_output_id,
        "grader_condition_id": grader_condition_id,
        "blind_packet_version": "blind-grader-packet-v1",
        "blind_packet_hash": "blind-grader-packet-hash",
        "raw_payload": {"result": "pass"},
        "import_status": "valid",
        "normalized_semantic": {"required_facts": []},
        "language_compliance": "pass",
        "readability": "good",
        "primary_error_type": None,
        "secondary_error_types": [],
        "unsupported_claims": [],
        "reason": {"language_compliance": "主体为简体中文"},
        "evidence": {"language_compliance": "title"},
        "created_at": NOW,
    }


def evaluation_result_data(model_output_id: int, grader_result_id: int, grader_condition_id: int) -> dict[str, object]:
    return {
        "model_output_id": model_output_id,
        "grader_result_id": grader_result_id,
        "grader_condition_id": grader_condition_id,
        "aggregation_rule_version": "v1",
        "calculated_status": "pass",
        "blocking_reasons": [],
        "calculated_at": NOW,
    }


def make_output_graph(conn: sqlite3.Connection, *, split: str = "dev") -> tuple[int, int, int, int, int, int]:
    task_pack_id = insert_task_pack(conn, task_pack_data())
    test_case_id = insert_test_case(conn, case_data(task_pack_id, split=split))
    prompt_version_id = insert_prompt_version(conn, prompt_data())
    run_id = insert_evaluation_run(conn, run_data(prompt_version_id, split=split))
    model_output_id = insert_model_output_slot(conn, output_data(run_id, test_case_id))
    grader_condition_id = insert_grader_condition(conn, grader_condition_data())
    return task_pack_id, test_case_id, run_id, model_output_id, grader_condition_id, prompt_version_id


def test_parent_child_inserts_json_round_trips_and_freeze_lifecycle(initialized_connection: sqlite3.Connection) -> None:
    task_pack_id, test_case_id, run_id, model_output_id, grader_condition_id, prompt_version_id = make_output_graph(initialized_connection)
    raw_case = initialized_connection.execute("SELECT source_facts_json FROM test_cases WHERE id = ?", (test_case_id,)).fetchone()[0]
    assert raw_case == '[{"fact_id": "F01", "text": "重量为120克。"}, {"fact_id": "F02", "text": "包装含USB-C充电线。"}]'
    context = fetch_output_context(initialized_connection, model_output_id)
    assert context["test_case"]["source_facts"] == [{"fact_id": "F01", "text": "重量为120克。"}, {"fact_id": "F02", "text": "包装含USB-C充电线。"}]
    assert context["evaluation_run"]["id"] == run_id
    assert context["task_pack"]["id"] == task_pack_id
    assert context["prompt_version"]["id"] == prompt_version_id
    assert context["model_output"]["generation_packet_hash"] == "generation-packet-hash"
    freeze_prompt_version(initialized_connection, prompt_version_id, NOW)
    frozen = initialized_connection.execute("SELECT status, frozen_at FROM prompt_versions WHERE id = ?", (prompt_version_id,)).fetchone()
    assert tuple(frozen) == ("frozen", NOW)
    update_run_status(initialized_connection, run_id, "open")
    assert get_evaluation_run(initialized_connection, run_id)["status"] == "open"
    assert grader_condition_id > 0


def test_output_provenance_retries_and_raw_response_round_trip(initialized_connection: sqlite3.Connection) -> None:
    _, _, _, model_output_id, _, _ = make_output_graph(initialized_connection)
    response = fetch_raw_response(initialized_connection, model_output_id)
    assert response is not None and response.startswith('{"title"')
    update_technical_retry(initialized_connection, model_output_id, "network error")
    update_technical_retry(initialized_connection, model_output_id, "page failed to load")
    row = initialized_connection.execute("SELECT technical_retry_reasons_json FROM model_outputs WHERE id = ?", (model_output_id,)).fetchone()
    assert fetch_retry_count(initialized_connection, model_output_id) == 2
    assert json.loads(row[0]) == ["network error", "page failed to load"]


def test_rule_grader_and_evaluation_children_round_trip(initialized_connection: sqlite3.Connection) -> None:
    _, _, _, model_output_id, grader_condition_id, _ = make_output_graph(initialized_connection)
    insert_rule_results(initialized_connection, model_output_id, [{"rule_key": "schema", "rule_version": "v1", "status": "pass", "actual": {"fields": ["title"]}, "expected": {"fields": ["title"]}, "reason": "valid", "calculated_at": NOW}])
    grader_result_id = insert_grader_result(initialized_connection, grader_result_data(model_output_id, grader_condition_id))
    insert_grader_fact_results(initialized_connection, grader_result_id, [{"fact_id": "F01", "status": "met", "output_evidence": "重量为120克", "reason": "matched"}])
    evaluation_result_id = insert_evaluation_result(initialized_connection, evaluation_result_data(model_output_id, grader_result_id, grader_condition_id))
    review_id = insert_human_review(initialized_connection, {"evaluation_result_id": evaluation_result_id, "review_scope": "required", "blind_review": True, "evidence": {"output": "重量为120克"}, "reason": "reviewed", "final_decision": "pass", "reviewed_at": NOW})
    assert review_id > 0
    assert initialized_connection.execute("SELECT actual_json FROM rule_results").fetchone()[0] == '{"fields": ["title"]}'
    assert initialized_connection.execute("SELECT blind_packet_version FROM grader_results WHERE id = ?", (grader_result_id,)).fetchone()[0] == "blind-grader-packet-v1"


@pytest.mark.parametrize("split, expected_count", [(None, 2), ("dev", 1), ("holdout", 1)])
def test_list_test_cases_filters_by_split(initialized_connection: sqlite3.Connection, split: str | None, expected_count: int) -> None:
    task_pack_id = insert_task_pack(initialized_connection, task_pack_data())
    insert_test_case(initialized_connection, case_data(task_pack_id, case_key="case-dev", split="dev"))
    insert_test_case(initialized_connection, case_data(task_pack_id, case_key="case-holdout", split="holdout"))
    assert len(list_test_cases(initialized_connection, task_pack_id, split)) == expected_count


def test_unique_constraints_surface_for_duplicate_entities(initialized_connection: sqlite3.Connection) -> None:
    _, test_case_id, run_id, model_output_id, grader_condition_id, _ = make_output_graph(initialized_connection)
    with pytest.raises(sqlite3.IntegrityError):
        insert_model_output_slot(initialized_connection, output_data(run_id, test_case_id))
    with pytest.raises(sqlite3.IntegrityError):
        insert_grader_condition(initialized_connection, grader_condition_data())
    grader_result_id = insert_grader_result(initialized_connection, grader_result_data(model_output_id, grader_condition_id))
    evaluation_data = evaluation_result_data(model_output_id, grader_result_id, grader_condition_id)
    evaluation_result_id = insert_evaluation_result(initialized_connection, evaluation_data)
    with pytest.raises(sqlite3.IntegrityError):
        insert_evaluation_result(initialized_connection, evaluation_data)
    review_data = {"evaluation_result_id": evaluation_result_id, "review_scope": "manual", "blind_review": False, "evidence": {}, "reason": "reviewed", "final_decision": None, "reviewed_at": NOW}
    insert_human_review(initialized_connection, review_data)
    with pytest.raises(sqlite3.IntegrityError):
        insert_human_review(initialized_connection, review_data)


def test_multi_row_rule_insert_rolls_back_every_row_on_failure(initialized_connection: sqlite3.Connection) -> None:
    _, _, _, model_output_id, _, _ = make_output_graph(initialized_connection)
    rows = [
        {"rule_key": "schema", "rule_version": "v1", "status": "pass", "actual": {}, "expected": {}, "reason": "first", "calculated_at": NOW},
        {"rule_key": "schema", "rule_version": "v1", "status": "fail", "actual": {}, "expected": {}, "reason": "duplicate", "calculated_at": NOW},
    ]
    with pytest.raises(sqlite3.IntegrityError):
        insert_rule_results(initialized_connection, model_output_id, rows)
    assert initialized_connection.execute("SELECT COUNT(*) FROM rule_results WHERE model_output_id = ?", (model_output_id,)).fetchone()[0] == 0
