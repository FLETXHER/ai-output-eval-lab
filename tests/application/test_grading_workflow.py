from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from eval_lab.application.grading import (
    WorkflowError,
    approve_grader_condition,
    build_blind_grader_packet_for_output,
    calculate_output_status,
    import_grader_result,
    import_grader_result_text,
)
from eval_lab.application.cases import load_case
from eval_lab.application.outputs import evaluate_output_rules, record_model_output
from eval_lab.application.prompts import (
    approve_prompt_version,
    create_prompt_version,
    freeze_prompt_version,
)
from eval_lab.application.runs import create_evaluation_run
from eval_lab.domain.task_pack import TASK_PACK_CONTRACT, canonical_json_hash
from eval_lab.repositories.sqlite import (
    connect,
    initialize_database,
    insert_grader_condition,
    insert_task_pack,
    insert_test_case,
)


NOW = "2026-08-13T00:00:00Z"


@pytest.fixture
def conn(temporary_db_path: Path, repo_root: Path):
    connection = connect(temporary_db_path)
    initialize_database(connection, repo_root / "db" / "schema.sql")
    yield connection
    connection.close()


def _case_data(case_key: str, split: str = "dev") -> dict[str, object]:
    return {
        "case_key": case_key,
        "revision": 1,
        "split": split,
        "source_material": "Source says the device weighs 120 grams.",
        "source_facts": [{"fact_id": "F01", "text": "The device weighs 120 grams."}],
        "required_fact_ids": ["F01"],
        "explicit_forbidden_claims": ["waterproof"],
        "task_notes": "Include the device weight and return strict JSON.",
        "feasibility_qa_status": "pass",
    }


def _metadata() -> dict[str, str]:
    return {
        "case_set_hash": "case-set-hash",
        "contract_hash": canonical_json_hash(TASK_PACK_CONTRACT),
        "generator_product": "FORBIDDEN_GENERATOR_PRODUCT",
        "generator_visible_model": "FORBIDDEN_GENERATOR_MODEL",
        "environment_notes": "FORBIDDEN_ENVIRONMENT_NOTES",
        "protocol_version": "1.0",
        "created_at": NOW,
        "updated_at": NOW,
    }


def _condition_data(suffix: str = "one") -> dict[str, object]:
    prompt = f"Actual grader prompt snapshot {suffix}."
    rubric = f"Actual rubric snapshot {suffix}."
    taxonomy = f"Actual taxonomy snapshot {suffix}."
    digest = lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
    return {
        "grader_product": "FORBIDDEN_GRADER_PRODUCT",
        "grader_visible_model": "FORBIDDEN_GRADER_MODEL",
        "grader_prompt": prompt,
        "grader_prompt_hash": digest(prompt),
        "grader_prompt_version_label": f"grader-{suffix}",
        "rubric": rubric,
        "rubric_hash": digest(rubric),
        "rubric_version_label": f"rubric-{suffix}",
        "error_taxonomy": taxonomy,
        "error_taxonomy_hash": digest(taxonomy),
        "error_taxonomy_version_label": f"taxonomy-{suffix}",
        "owner_approved_at": None,
        "created_at": NOW,
    }


def _setup_output(conn: sqlite3.Connection, *, label: str = "v1", group: str = "DEV-COMP-01") -> tuple[int, int]:
    existing_pack = conn.execute(
        "SELECT id FROM task_packs WHERE pack_key = ?", (TASK_PACK_CONTRACT["pack_key"],)
    ).fetchone()
    pack_id = int(existing_pack["id"]) if existing_pack is not None else insert_task_pack(conn, {
        "pack_key": TASK_PACK_CONTRACT["pack_key"], "contract_version": TASK_PACK_CONTRACT["contract_version"],
        "contract_hash": canonical_json_hash(TASK_PACK_CONTRACT), "language": TASK_PACK_CONTRACT["language"],
        "title_min_chars": 4, "title_max_chars": 20, "summary_min_chars": 60, "summary_max_chars": 120,
        "key_points_count": 3, "key_point_min_chars": 6, "key_point_max_chars": 40,
        "created_at": NOW, "updated_at": NOW,
    })
    case = _case_data(f"case-{label}")
    case_id = insert_test_case(conn, {**case, "task_pack_id": pack_id, "content_hash": canonical_json_hash(case), "created_at": NOW, "updated_at": NOW})
    prompt_id = create_prompt_version(conn, f"Prompt text {label}", label, "baseline")
    run_id = create_evaluation_run(conn, prompt_id, group, "dev", _metadata())
    output_id = record_model_output(
        conn, run_id, case_id, "generation-1.0", "a" * 64,
        '{"title":"Test","summary":"A sufficiently long summary with a stated 120 gram weight for the device.","key_points":["120 gram weight","Source only fact","No unsupported claim"]}', NOW,
    )
    evaluate_output_rules(conn, output_id, TASK_PACK_CONTRACT, ["waterproof"])
    return output_id, run_id


def _payload(repo_root: Path, name: str, packet: dict[str, object]) -> dict[str, object]:
    payload = json.loads((repo_root / "tests" / "fixtures" / name).read_text(encoding="utf-8"))
    payload["blind_packet_version"] = packet["packet_version"]
    payload["blind_packet_hash"] = packet["content_hash"]
    return payload


def test_imports_valid_grader_result_with_snapshots_fact_rows_and_packet_provenance(conn, repo_root: Path) -> None:
    output_id, _ = _setup_output(conn)
    condition_id = insert_grader_condition(conn, _condition_data())
    condition = dict(conn.execute("SELECT * FROM grader_conditions WHERE id = ?", (condition_id,)).fetchone())
    assert condition["grader_prompt_hash"] == hashlib.sha256(condition["grader_prompt"].encode("utf-8")).hexdigest()
    assert condition["rubric_hash"] == hashlib.sha256(condition["rubric"].encode("utf-8")).hexdigest()
    assert condition["error_taxonomy_hash"] == hashlib.sha256(condition["error_taxonomy"].encode("utf-8")).hexdigest()

    packet = build_blind_grader_packet_for_output(conn, output_id, condition_id)
    payload = _payload(repo_root, "demo_grader_valid.json", packet)
    result_id = import_grader_result(conn, output_id, condition, payload)

    stored = conn.execute("SELECT * FROM grader_results WHERE id = ?", (result_id,)).fetchone()
    assert stored["blind_packet_version"] == packet["packet_version"]
    assert stored["blind_packet_hash"] == packet["content_hash"]
    assert json.loads(stored["raw_payload_json"]) == payload
    assert json.loads(stored["normalized_semantic_json"])["grader_reason"] == payload["grader_reason"]
    assert stored["language_compliance"] == "pass"
    assert [tuple(row) for row in conn.execute("SELECT fact_id, status FROM grader_fact_results WHERE grader_result_id = ?", (result_id,))] == [("F01", "met")]
    exposed = packet["text"] + json.dumps(packet["payload"], ensure_ascii=False)
    for expected in (condition["grader_prompt"], condition["rubric"], condition["error_taxonomy"]):
        assert expected in exposed
    for forbidden in ("\"split\"", "FORBIDDEN_GENERATOR_PRODUCT", "FORBIDDEN_GENERATOR_MODEL", "calculated_status"):
        assert forbidden not in exposed


def test_grader_import_rejects_invalid_or_mismatched_payload_and_duplicate_output_condition(conn, repo_root: Path) -> None:
    output_id, _ = _setup_output(conn)
    condition_id = insert_grader_condition(conn, _condition_data())
    condition = dict(conn.execute("SELECT * FROM grader_conditions WHERE id = ?", (condition_id,)).fetchone())
    packet = build_blind_grader_packet_for_output(conn, output_id, condition_id)
    payload = _payload(repo_root, "demo_grader_valid.json", packet)
    payload["required_facts"] = []
    with pytest.raises(WorkflowError, match="invalid grader payload"):
        import_grader_result(conn, output_id, condition, payload)
    assert conn.execute("SELECT COUNT(*) FROM grader_results").fetchone()[0] == 0

    valid = _payload(repo_root, "demo_grader_valid.json", packet)
    valid["blind_packet_hash"] = "f" * 64
    with pytest.raises(WorkflowError, match="packet provenance"):
        import_grader_result(conn, output_id, condition, valid)
    valid["blind_packet_hash"] = packet["content_hash"]
    import_grader_result(conn, output_id, condition, valid)
    with pytest.raises(WorkflowError, match="already exists"):
        import_grader_result(conn, output_id, condition, valid)


@pytest.mark.parametrize("raw_text", ["{not JSON}", "```json\n{}\n```", "[]"])
def test_grader_text_import_rejects_malformed_fenced_or_non_object_without_writes(
    conn, repo_root: Path, raw_text: str
) -> None:
    output_id, _ = _setup_output(conn)
    condition_id = insert_grader_condition(conn, _condition_data())
    condition = dict(conn.execute("SELECT * FROM grader_conditions WHERE id = ?", (condition_id,)).fetchone())
    with pytest.raises(WorkflowError, match="invalid grader JSON"):
        import_grader_result_text(conn, output_id, condition, raw_text)
    assert conn.execute("SELECT COUNT(*) FROM grader_results").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM grader_fact_results").fetchone()[0] == 0


def test_calculated_status_uses_only_rules_and_grader_not_human_review(conn, repo_root: Path) -> None:
    output_id, _ = _setup_output(conn)
    condition_id = insert_grader_condition(conn, _condition_data())
    condition = dict(conn.execute("SELECT * FROM grader_conditions WHERE id = ?", (condition_id,)).fetchone())
    packet = build_blind_grader_packet_for_output(conn, output_id, condition_id)
    grader_result_id = import_grader_result(conn, output_id, condition, _payload(repo_root, "demo_grader_valid.json", packet))

    evaluation_id = calculate_output_status(conn, output_id, grader_result_id, condition_id)
    before = conn.execute("SELECT calculated_status FROM evaluation_results WHERE id = ?", (evaluation_id,)).fetchone()[0]
    assert before == "pass"
    conn.execute("INSERT INTO human_reviews (evaluation_result_id, review_scope, blind_review, evidence_json, reason, final_decision, reviewed_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (evaluation_id, "manual", 1, "{}", "A human disagrees.", "fail", NOW))
    assert conn.execute("SELECT calculated_status FROM evaluation_results WHERE id = ?", (evaluation_id,)).fetchone()[0] == "pass"


def test_calculated_status_persists_indeterminate_and_grader_conditions_stay_separate(conn, repo_root: Path) -> None:
    output_v1, _ = _setup_output(conn, label="v1")
    output_v2, _ = _setup_output(conn, label="v2")
    output_v3, _ = _setup_output(conn, label="v3")
    condition_one = insert_grader_condition(conn, _condition_data("one"))
    condition_two = insert_grader_condition(conn, _condition_data("two"))
    stored_one = dict(conn.execute("SELECT * FROM grader_conditions WHERE id = ?", (condition_one,)).fetchone())
    packet_one = build_blind_grader_packet_for_output(conn, output_v1, condition_one)
    result_one = import_grader_result(conn, output_v1, stored_one, _payload(repo_root, "demo_grader_indeterminate.json", packet_one))
    evaluation_one = calculate_output_status(conn, output_v1, result_one, condition_one)
    assert conn.execute("SELECT calculated_status FROM evaluation_results WHERE id = ?", (evaluation_one,)).fetchone()[0] == "indeterminate"

    packet_two = build_blind_grader_packet_for_output(conn, output_v2, condition_one)
    result_two = import_grader_result(conn, output_v2, stored_one, _payload(repo_root, "demo_grader_valid.json", packet_two))
    evaluation_two = calculate_output_status(conn, output_v2, result_two, condition_one)
    assert conn.execute("SELECT grader_condition_id FROM evaluation_results WHERE id = ?", (evaluation_two,)).fetchone()[0] == condition_one
    stored_two = dict(conn.execute("SELECT * FROM grader_conditions WHERE id = ?", (condition_two,)).fetchone())
    packet_three = build_blind_grader_packet_for_output(conn, output_v3, condition_two)
    result_three = import_grader_result(conn, output_v3, stored_two, _payload(repo_root, "demo_grader_valid.json", packet_three))
    evaluation_three = calculate_output_status(conn, output_v3, result_three, condition_two)
    assert conn.execute("SELECT grader_condition_id FROM evaluation_results WHERE id = ?", (evaluation_three,)).fetchone()[0] == condition_two
    assert condition_one != condition_two


def test_pointwise_packet_reads_only_requested_candidate(conn) -> None:
    output_one, _ = _setup_output(conn, label="v1")
    output_two, _ = _setup_output(conn, label="v2")
    condition_id = insert_grader_condition(conn, _condition_data())
    packet = build_blind_grader_packet_for_output(conn, output_one, condition_id)
    other_candidate = conn.execute("SELECT candidate_id FROM model_outputs WHERE id = ?", (output_two,)).fetchone()[0]
    assert packet["payload"]["candidate_id"] != other_candidate
    assert other_candidate not in packet["text"]


def test_load_case_returns_annotations_and_fixed_contract(conn) -> None:
    output_id, _ = _setup_output(conn)
    case_id = conn.execute("SELECT test_case_id FROM model_outputs WHERE id = ?", (output_id,)).fetchone()[0]
    case = load_case(conn, case_id)
    assert case["required_fact_ids"] == ["F01"]
    assert case["task_pack_contract"]["root_keys"] == ["title", "summary", "key_points"]


def test_formal_grader_use_requires_owner_approved_condition(conn) -> None:
    output_id, run_id = _setup_output(conn)
    prompt_id = conn.execute(
        "SELECT prompt_version_id FROM evaluation_runs WHERE id = ?", (run_id,)
    ).fetchone()[0]
    approve_prompt_version(conn, prompt_id, NOW)
    freeze_prompt_version(conn, prompt_id, NOW)
    condition_id = insert_grader_condition(conn, _condition_data())

    with pytest.raises(WorkflowError, match="owner-approved grader condition"):
        build_blind_grader_packet_for_output(conn, output_id, condition_id)

    approve_grader_condition(conn, condition_id, NOW)
    assert (
        build_blind_grader_packet_for_output(conn, output_id, condition_id)["packet_version"]
        == "blind-grader-1.0"
    )
