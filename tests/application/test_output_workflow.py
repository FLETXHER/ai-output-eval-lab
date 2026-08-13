from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from eval_lab.application.outputs import WorkflowError, evaluate_output_rules, record_model_output
from eval_lab.application.prompts import create_prompt_version
from eval_lab.application.runs import close_run, create_evaluation_run
from eval_lab.domain.task_pack import TASK_PACK_CONTRACT, canonical_json_hash
from eval_lab.repositories.sqlite import (
    connect,
    fetch_raw_response,
    fetch_retry_count,
    initialize_database,
    insert_task_pack,
    insert_test_case,
)


NOW = "2026-08-13T09:00:00Z"
METADATA = {
    "case_set_hash": "case-set-hash",
    "contract_hash": canonical_json_hash(TASK_PACK_CONTRACT),
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


@pytest.fixture
def run_and_case(conn: sqlite3.Connection, repo_root) -> tuple[int, int]:
    case = json.loads((repo_root / "tests" / "fixtures" / "demo_case.json").read_text(encoding="utf-8"))
    pack_id = insert_task_pack(conn, {
        "pack_key": TASK_PACK_CONTRACT["pack_key"], "contract_version": TASK_PACK_CONTRACT["contract_version"],
        "contract_hash": canonical_json_hash(TASK_PACK_CONTRACT), "language": TASK_PACK_CONTRACT["language"],
        "title_min_chars": 4, "title_max_chars": 20, "summary_min_chars": 60, "summary_max_chars": 120,
        "key_points_count": 3, "key_point_min_chars": 6, "key_point_max_chars": 40,
        "created_at": NOW, "updated_at": NOW,
    })
    case_id = insert_test_case(conn, {**case, "task_pack_id": pack_id, "content_hash": canonical_json_hash(case), "created_at": NOW, "updated_at": NOW})
    prompt_id = create_prompt_version(conn, "baseline", "v1", "baseline")
    return create_evaluation_run(conn, prompt_id, "DEV-COMP-01", "dev", METADATA), case_id


def test_first_actual_response_is_immutable_and_quality_failure_is_not_retryable(conn, run_and_case) -> None:
    run_id, case_id = run_and_case
    raw_response = " \nnot json\n"
    output_id = record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", raw_response, NOW)
    with pytest.raises(WorkflowError, match="first actual response"):
        record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", '{"title":"retry"}', NOW)
    assert fetch_raw_response(conn, output_id) == raw_response


def test_technical_retries_are_null_response_only_and_recorded(conn, run_and_case) -> None:
    run_id, case_id = run_and_case
    output_id = record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", None, None, "page load failure")
    assert record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", None, None, "network error") == output_id
    assert fetch_retry_count(conn, output_id) == 2
    assert record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", "first response", NOW) == output_id
    assert fetch_raw_response(conn, output_id) == "first response"
    with pytest.raises(WorkflowError, match="technical reason"):
        record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", None, None)
    with pytest.raises(WorkflowError, match="technical retry"):
        record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", "response", NOW, "network error")


def test_blank_actual_response_is_rejected_without_creating_quality_evidence(conn, run_and_case) -> None:
    run_id, case_id = run_and_case
    with pytest.raises(WorkflowError, match="raw_response must contain non-whitespace"):
        record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", " \n\t ", NOW)
    assert conn.execute("SELECT COUNT(*) FROM model_outputs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM rule_results").fetchone()[0] == 0

    output_id = record_model_output(
        conn, run_id, case_id, "packet-v1", "packet-hash", None, None, "network error"
    )
    before = tuple(
        conn.execute(
            "SELECT raw_response, technical_retry_count, technical_retry_reasons_json FROM model_outputs WHERE id = ?",
            (output_id,),
        ).fetchone()
    )
    with pytest.raises(WorkflowError, match="raw_response must contain non-whitespace"):
        record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", "\n  ", NOW)
    after = tuple(
        conn.execute(
            "SELECT raw_response, technical_retry_count, technical_retry_reasons_json FROM model_outputs WHERE id = ?",
            (output_id,),
        ).fetchone()
    )
    assert after == before
    assert conn.execute("SELECT COUNT(*) FROM rule_results").fetchone()[0] == 0


def test_packet_provenance_closed_run_and_rules_persistence(conn, run_and_case) -> None:
    run_id, case_id = run_and_case
    with pytest.raises(WorkflowError, match="generation_packet_version"):
        record_model_output(conn, run_id, case_id, "", "packet-hash", None, None, "network error")
    with pytest.raises(WorkflowError, match="generation_packet_hash"):
        record_model_output(conn, run_id, case_id, "packet-v1", "", None, None, "network error")

    raw = '{"title":"星河灯","summary":"星河随身灯重量为120克，包装内含USB-C充电线，适合日常随身使用。","key_points":["重量为120克，便于携带","包装内含USB-C充电线","适合日常随身携带"]}'
    output_id = record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", raw, NOW)
    persisted = evaluate_output_rules(conn, output_id, TASK_PACK_CONTRACT, ["防水"])
    assert {row["rule_key"] for row in persisted} == {"json_parse_pass", "schema_pass", "title_length", "summary_length", "key_points_count", "key_point_lengths", "forbidden_claims"}
    assert conn.execute("SELECT COUNT(*) FROM rule_results WHERE model_output_id = ?", (output_id,)).fetchone()[0] == len(persisted)

    close_run(conn, run_id)
    with pytest.raises(WorkflowError, match="closed"):
        record_model_output(conn, run_id, case_id + 1, "packet-v1", "packet-hash", "response", NOW)
    with pytest.raises(WorkflowError, match="closed"):
        evaluate_output_rules(conn, output_id, TASK_PACK_CONTRACT, ["防水"])
