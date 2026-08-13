from __future__ import annotations

from hashlib import sha256
import sqlite3

import pytest

from eval_lab.analysis.reports import (
    failure_breakdown,
    load_query,
    paired_comparison,
    review_coverage,
    run_query,
    run_summary,
    status_distribution,
)
from eval_lab.repositories.sqlite import (
    connect,
    initialize_database,
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
)


NOW = "2026-08-13T00:00:00Z"


@pytest.fixture
def initialized_connection(temporary_db_path, repo_root):
    conn = connect(temporary_db_path)
    initialize_database(conn, repo_root / "db" / "schema.sql")
    yield conn
    conn.close()


def _database_state(conn: sqlite3.Connection) -> tuple[tuple[tuple[str, int], ...], str]:
    table_names = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    row_counts = tuple(
        (table_name, conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
        for table_name in table_names
    )
    content_hash = sha256("\n".join(conn.iterdump()).encode("utf-8")).hexdigest()
    return row_counts, content_hash


def _task_pack(conn: sqlite3.Connection) -> int:
    return insert_task_pack(conn, {
        "pack_key": "grounded-brief", "contract_version": "v1", "contract_hash": "contract-hash",
        "language": "zh-CN", "title_min_chars": 4, "title_max_chars": 20,
        "summary_min_chars": 60, "summary_max_chars": 120, "key_points_count": 3,
        "key_point_min_chars": 6, "key_point_max_chars": 40, "created_at": NOW, "updated_at": NOW,
    })


def _case(conn: sqlite3.Connection, pack_id: int, key: str) -> int:
    return insert_test_case(conn, {
        "task_pack_id": pack_id, "case_key": key, "revision": 1, "split": "dev",
        "source_material": f"{key} source", "source_facts": [{"fact_id": "F01", "text": "fact"}],
        "required_fact_ids": ["F01"], "explicit_forbidden_claims": [], "task_notes": "include fact",
        "feasibility_qa_status": "pass", "content_hash": f"{key}-hash", "created_at": NOW, "updated_at": NOW,
    })


def _prompt(conn: sqlite3.Connection, label: str) -> int:
    return insert_prompt_version(conn, {
        "version_label": label, "prompt_text": f"prompt {label}", "change_reason": "test",
        "content_hash": f"{label}-hash", "status": "frozen", "owner_approved_at": NOW,
        "frozen_at": NOW, "created_at": NOW, "updated_at": NOW,
    })


def _run(conn: sqlite3.Connection, prompt_id: int) -> int:
    return insert_evaluation_run(conn, {
        "comparison_group_id": "DEV-COMP-01", "prompt_version_id": prompt_id, "split": "dev",
        "case_set_hash": "cases-hash", "contract_hash": "contract-hash", "generator_product": "ChatGPT",
        "generator_visible_model": "not_visible", "environment_notes": "same session window",
        "protocol_version": "v1", "status": "closed", "created_at": NOW, "updated_at": NOW,
    })


def _condition(conn: sqlite3.Connection, *, suffix: str = "one") -> int:
    return insert_grader_condition(conn, {
        "grader_product": "Gemini", "grader_visible_model": "not_visible", "grader_prompt": f"grade-{suffix}",
        "grader_prompt_hash": f"grader-{suffix}-hash", "grader_prompt_version_label": "v1", "rubric": "rubric",
        "rubric_hash": "rubric-hash", "rubric_version_label": "v1", "error_taxonomy": "taxonomy",
        "error_taxonomy_hash": "taxonomy-hash", "error_taxonomy_version_label": "v1",
        "owner_approved_at": NOW, "created_at": NOW,
    })


def _output(conn: sqlite3.Connection, run_id: int, case_id: int, candidate_id: str, raw_response: str | None) -> int:
    return insert_model_output_slot(conn, {
        "evaluation_run_id": run_id, "test_case_id": case_id, "candidate_id": candidate_id,
        "generation_packet_version": "v1", "generation_packet_hash": f"{candidate_id}-packet",
        "raw_response": raw_response, "output_hash": f"{candidate_id}-output" if raw_response else None,
        "generated_at": NOW if raw_response else None, "technical_retry_count": 1 if raw_response is None else 0,
        "technical_retry_reasons": ["network error"] if raw_response is None else [],
        "created_at": NOW, "updated_at": NOW,
    })


def _evaluation(
    conn: sqlite3.Connection, output_id: int, condition_id: int, status: str, *, error: str | None = None,
    unsupported: list[object] | None = None, fact_status: str = "met", review: str | None = None,
) -> None:
    grader_id = insert_grader_result(conn, {
        "model_output_id": output_id, "grader_condition_id": condition_id, "blind_packet_version": "v1",
        "blind_packet_hash": f"grader-{output_id}", "raw_payload": {"ok": True}, "import_status": "valid",
        "normalized_semantic": {}, "language_compliance": "pass", "readability": "good",
        "primary_error_type": error, "secondary_error_types": [], "unsupported_claims": unsupported or [],
        "reason": {}, "evidence": {}, "created_at": NOW,
    })
    insert_grader_fact_results(conn, grader_id, [{
        "fact_id": "F01", "status": fact_status, "output_evidence": "evidence", "reason": "reason",
    }])
    result_id = insert_evaluation_result(conn, {
        "model_output_id": output_id, "grader_result_id": grader_id, "grader_condition_id": condition_id,
        "aggregation_rule_version": "v1", "calculated_status": status, "blocking_reasons": [], "calculated_at": NOW,
    })
    if review is not None:
        insert_human_review(conn, {
            "evaluation_result_id": result_id, "review_scope": "required", "blind_review": True,
            "evidence": {}, "reason": "review", "final_decision": review, "reviewed_at": NOW,
        })


@pytest.fixture
def analysis_data(initialized_connection: sqlite3.Connection) -> dict[str, int]:
    conn = initialized_connection
    pack_id = _task_pack(conn)
    case_one, case_two, case_three = (_case(conn, pack_id, key) for key in ("case-1", "case-2", "case-3"))
    v1, v2 = _prompt(conn, "v1"), _prompt(conn, "v2")
    run_v1, run_v2 = _run(conn, v1), _run(conn, v2)
    condition_id = _condition(conn)

    one_v1 = _output(conn, run_v1, case_one, "candidate-a1b2c3", "response one")
    two_v1 = _output(conn, run_v1, case_two, "candidate-a1b2c4", "response two")
    three_v1 = _output(conn, run_v1, case_three, "candidate-a1b2c5", None)
    one_v2 = _output(conn, run_v2, case_one, "candidate-b1b2c3", "response one improved")
    two_v2 = _output(conn, run_v2, case_two, "candidate-b1b2c4", "response two failed")
    three_v2 = _output(conn, run_v2, case_three, "candidate-b1b2c5", "response three")

    _evaluation(conn, one_v1, condition_id, "pass", review="pass")
    _evaluation(conn, two_v1, condition_id, "indeterminate", error="ambiguous_source", review="indeterminate")
    _evaluation(conn, one_v2, condition_id, "pass")
    _evaluation(conn, two_v2, condition_id, "fail", error="unsupported_claim", unsupported=[{"claim": "unsupported"}], fact_status="not_met", review="fail")
    _evaluation(conn, three_v2, condition_id, "pass")
    insert_rule_results(conn, two_v2, [{
        "rule_key": "summary_length", "rule_version": "v1", "status": "fail", "actual": 130,
        "expected": {"max": 120}, "reason": "too long", "calculated_at": NOW,
    }])
    return {"run_v1": run_v1, "run_v2": run_v2}


def test_named_queries_are_loadable_and_parameterized(analysis_data) -> None:
    for name in (
        "run_summary", "status_distribution", "paired_comparison", "rule_failures",
        "required_fact_failures", "unsupported_claims", "error_types", "bad_cases", "review_coverage",
    ):
        assert "?" in load_query(name)
    with pytest.raises(KeyError):
        load_query("unknown")


def test_run_summary_status_distribution_and_failure_breakdown_are_descriptive_and_read_only(
    initialized_connection: sqlite3.Connection, analysis_data: dict[str, int]
) -> None:
    before = _database_state(initialized_connection)
    summary = run_summary(initialized_connection, analysis_data["run_v1"])
    distribution = status_distribution(initialized_connection, analysis_data["run_v1"])
    breakdown = failure_breakdown(initialized_connection, analysis_data["run_v2"])
    assert summary.iloc[0].to_dict() == {
        "total_assigned": 3, "responses_received": 2, "technical_failure_count": 1,
        "not_evaluated_count": 1, "determinate_count": 1, "calculated_pass_count": 1,
        "pass_rate_among_determinate": 1.0, "indeterminate_count": 1, "indeterminate_rate": 0.5,
    }
    assert distribution.to_dict("records") == [
        {"decision_layer": "calculated_status", "status": "indeterminate", "count": 1},
        {"decision_layer": "calculated_status", "status": "pass", "count": 1},
        {"decision_layer": "final_decision", "status": "indeterminate", "count": 1},
        {"decision_layer": "final_decision", "status": "pass", "count": 1},
    ]
    assert breakdown["rule_failures"].to_dict("records") == [{"rule_key": "summary_length", "count": 1}]
    assert breakdown["required_fact_failures"].to_dict("records") == [{"fact_id": "F01", "status": "not_met", "count": 1}]
    assert breakdown["unsupported_claims"].to_dict("records") == [{"model_output_id": 5, "unsupported_claim_count": 1}]
    assert breakdown["error_types"].to_dict("records") == [{"primary_error_type": "unsupported_claim", "count": 1}]
    assert "bad_cases" in breakdown
    assert _database_state(initialized_connection) == before


def test_paired_comparison_and_review_coverage_keep_status_layers_separate_and_read_only(
    initialized_connection: sqlite3.Connection, analysis_data: dict[str, int]
) -> None:
    before = _database_state(initialized_connection)
    paired = paired_comparison(initialized_connection, "DEV-COMP-01")
    coverage = review_coverage(initialized_connection, "DEV-COMP-01")
    assert paired.columns.tolist() == [
        "test_case_id", "left_prompt_version", "right_prompt_version", "left_calculated_status",
        "right_calculated_status", "left_final_decision", "right_final_decision", "comparison",
    ]
    assert paired["test_case_id"].tolist() == [1, 2, 3]
    assert paired["left_calculated_status"].iloc[:2].tolist() == ["pass", "indeterminate"]
    assert paired["right_calculated_status"].tolist() == ["pass", "fail", "pass"]
    assert paired["comparison"].tolist() == ["unchanged", "indeterminate", "indeterminate"]
    assert paired.loc[2, "left_calculated_status"] != paired.loc[2, "left_calculated_status"]
    assert paired.loc[0, "left_final_decision"] == "pass"
    assert paired.loc[1, "left_final_decision"] == "indeterminate"
    assert paired.loc[1, "right_final_decision"] == "fail"
    assert paired.loc[2, "right_final_decision"] != paired.loc[2, "right_final_decision"]
    assert coverage.to_dict("records") == [
        {"total_evaluation_results": 5, "human_reviewed_count": 3, "human_review_coverage_rate": 0.6}
    ]
    assert _database_state(initialized_connection) == before


def test_paired_comparison_rejects_mismatched_conditions_and_run_query_is_read_only(
    initialized_connection: sqlite3.Connection, analysis_data: dict[str, int]
) -> None:
    initialized_connection.execute("UPDATE evaluation_runs SET protocol_version = 'v2' WHERE id = ?", (analysis_data["run_v2"],))
    before = _database_state(initialized_connection)
    with pytest.raises(ValueError, match="comparable"):
        paired_comparison(initialized_connection, "DEV-COMP-01")
    table = run_query(initialized_connection, "bad_cases", (analysis_data["run_v1"],))
    assert table.to_dict("records") == [{"model_output_id": 2, "candidate_id": "candidate-a1b2c4", "calculated_status": "indeterminate", "final_decision": "indeterminate", "primary_error_type": "ambiguous_source"}]
    assert _database_state(initialized_connection) == before


def test_analysis_rejects_mixed_grader_conditions_instead_of_merging_rows(
    initialized_connection: sqlite3.Connection, analysis_data: dict[str, int]
) -> None:
    conn = initialized_connection
    second_condition = _condition(conn, suffix="two")
    first_output_id = conn.execute(
        "SELECT id FROM model_outputs WHERE evaluation_run_id = ? ORDER BY id LIMIT 1",
        (analysis_data["run_v1"],),
    ).fetchone()[0]
    _evaluation(conn, first_output_id, second_condition, "pass")
    before = _database_state(conn)

    for report in (
        lambda: run_summary(conn, analysis_data["run_v1"]),
        lambda: status_distribution(conn, analysis_data["run_v1"]),
        lambda: failure_breakdown(conn, analysis_data["run_v1"]),
        lambda: run_query(conn, "bad_cases", (analysis_data["run_v1"],)),
        lambda: review_coverage(conn, "DEV-COMP-01"),
        lambda: paired_comparison(conn, "DEV-COMP-01"),
    ):
        with pytest.raises(ValueError, match="grader condition"):
            report()

    assert _database_state(conn) == before


def test_direct_paired_query_requires_one_shared_condition_per_run(
    initialized_connection: sqlite3.Connection, analysis_data: dict[str, int]
) -> None:
    conn = initialized_connection
    v1_prompt_id = conn.execute(
        "SELECT prompt_version_id FROM evaluation_runs WHERE id = ?",
        (analysis_data["run_v1"],),
    ).fetchone()[0]
    run_without_grading = _run(conn, v1_prompt_id)
    before = _database_state(conn)

    with pytest.raises(ValueError, match="shared grader condition"):
        run_query(
            conn,
            "paired_comparison",
            (analysis_data["run_v1"], run_without_grading, analysis_data["run_v1"], run_without_grading),
        )

    assert _database_state(conn) == before
