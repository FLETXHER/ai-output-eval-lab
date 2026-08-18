from __future__ import annotations

import hashlib
import json
import sqlite3

from streamlit.testing.v1 import AppTest

from eval_lab.application.grading import calculate_output_status, import_grader_result
from eval_lab.application.outputs import evaluate_output_rules, record_model_output
from eval_lab.application.packets import build_blind_grader_packet
from eval_lab.application.prompts import create_prompt_version
from eval_lab.application.reviews import authorize_human_review_correction_target
from eval_lab.application.runs import create_evaluation_run
from eval_lab.domain.task_pack import TASK_PACK_CONTRACT, canonical_json_hash
from eval_lab.repositories.sqlite import (
    connect,
    initialize_database,
    insert_grader_condition,
    insert_human_review,
    insert_task_pack,
    insert_test_case,
)


NOW = "2026-08-13T00:00:00Z"
RAW_INVALID_JSON = "  {not valid JSON}  "


def _page_test(page_module: str, db_path: str, repo_root: str) -> AppTest:
    source = f"""
import sqlite3
import sys
sys.path.insert(0, {repo_root!r})
from {page_module} import render
conn = sqlite3.connect({db_path!r})
conn.row_factory = sqlite3.Row
conn.execute('PRAGMA foreign_keys = ON')
render(conn)
"""
    return AppTest.from_string(source).run()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seed(db_path, repo_root, *, visible_model: str = "UI_GENERATOR_MODEL") -> dict[str, int]:
    conn = connect(db_path)
    initialize_database(conn, repo_root / "db" / "schema.sql")
    pack_id = insert_task_pack(
        conn,
        {
            "pack_key": TASK_PACK_CONTRACT["pack_key"],
            "contract_version": TASK_PACK_CONTRACT["contract_version"],
            "contract_hash": canonical_json_hash(TASK_PACK_CONTRACT),
            "language": TASK_PACK_CONTRACT["language"],
            "title_min_chars": 4,
            "title_max_chars": 20,
            "summary_min_chars": 60,
            "summary_max_chars": 120,
            "key_points_count": 3,
            "key_point_min_chars": 6,
            "key_point_max_chars": 40,
            "created_at": NOW,
            "updated_at": NOW,
        },
    )
    case_id = insert_test_case(
        conn,
        {
            "task_pack_id": pack_id,
            "case_key": "ui-case",
            "revision": 1,
            "split": "dev",
            "source_material": "UI_SOURCE_ONLY: device weighs 120 grams.",
            "source_facts": [{"fact_id": "F01", "text": "device weighs 120 grams"}],
            "required_fact_ids": ["F01"],
            "explicit_forbidden_claims": ["waterproof"],
            "task_notes": "UI_TASK_INSTRUCTIONS: include the 120 gram weight.",
            "feasibility_qa_status": "pass",
            "content_hash": "case-hash",
            "created_at": NOW,
            "updated_at": NOW,
        },
    )
    prompt_id = create_prompt_version(conn, "UI_PROMPT_TEXT: output JSON.", "v1", "demo")
    run_id = create_evaluation_run(
        conn,
        prompt_id,
        "UI-COMP-01",
        "dev",
        {
            "case_set_hash": "UI_CASE_SET_HASH",
            "contract_hash": canonical_json_hash(TASK_PACK_CONTRACT),
            "generator_product": "UI_GENERATOR_PRODUCT",
            "generator_visible_model": visible_model,
            "environment_notes": "UI_ENVIRONMENT",
            "protocol_version": "1.0",
            "created_at": NOW,
            "updated_at": NOW,
        },
    )
    condition_id = insert_grader_condition(
        conn,
        {
            "grader_product": "UI_GRADER_PRODUCT",
            "grader_visible_model": "UI_GRADER_MODEL",
            "grader_prompt": "UI_GRADER_PROMPT",
            "grader_prompt_hash": _hash("UI_GRADER_PROMPT"),
            "grader_prompt_version_label": "grader-v1",
            "rubric": "UI_GRADER_RUBRIC",
            "rubric_hash": _hash("UI_GRADER_RUBRIC"),
            "rubric_version_label": "rubric-v1",
            "error_taxonomy": "UI_ERROR_TAXONOMY",
            "error_taxonomy_hash": _hash("UI_ERROR_TAXONOMY"),
            "error_taxonomy_version_label": "taxonomy-v1",
            "owner_approved_at": None,
            "created_at": NOW,
        },
    )
    conn.close()
    return {"case_id": case_id, "run_id": run_id, "condition_id": condition_id}


def _add_grader_condition(conn: sqlite3.Connection, source_condition_id: int, product: str) -> int:
    source = conn.execute(
        "SELECT * FROM grader_conditions WHERE id = ?", (source_condition_id,)
    ).fetchone()
    assert source is not None
    keys = (
        "grader_product", "grader_visible_model", "grader_prompt", "grader_prompt_hash",
        "grader_prompt_version_label", "rubric", "rubric_hash", "rubric_version_label",
        "error_taxonomy", "error_taxonomy_hash", "error_taxonomy_version_label",
        "owner_approved_at", "created_at",
    )
    values = {key: source[key] for key in keys}
    values["grader_product"] = product
    values["grader_prompt"] = f"{product} PROMPT"
    values["grader_prompt_hash"] = _hash(values["grader_prompt"])
    return insert_grader_condition(conn, values)


def _add_second_output(conn: sqlite3.Connection, ids: dict[str, int], case_key: str) -> int:
    pack_id = conn.execute("SELECT task_pack_id FROM test_cases WHERE id = ?", (ids["case_id"],)).fetchone()[0]
    case_id = insert_test_case(
        conn,
        {
            "task_pack_id": pack_id,
            "case_key": case_key,
            "revision": 1,
            "split": "dev",
            "source_material": "SECOND_SOURCE_ONLY",
            "source_facts": [{"fact_id": "F01", "text": "second fact"}],
            "required_fact_ids": ["F01"],
            "explicit_forbidden_claims": [],
            "task_notes": "SECOND_TASK_INSTRUCTIONS",
            "feasibility_qa_status": "pass",
            "content_hash": f"{case_key}-hash",
            "created_at": NOW,
            "updated_at": NOW,
        },
    )
    return record_model_output(
        conn,
        ids["run_id"],
        case_id,
        "generation-1.0",
        "b" * 64,
        "second raw candidate",
        NOW,
    )


def _add_first_output(conn: sqlite3.Connection, ids: dict[str, int]) -> int:
    return record_model_output(
        conn,
        ids["run_id"],
        ids["case_id"],
        "generation-1.0",
        "a" * 64,
        "first raw candidate",
        NOW,
    )


def _add_review_group(conn: sqlite3.Connection, ids: dict[str, int], group_id: str) -> int:
    pack_id = conn.execute("SELECT task_pack_id FROM test_cases WHERE id = ?", (ids["case_id"],)).fetchone()[0]
    case_id = insert_test_case(
        conn,
        {
            "task_pack_id": pack_id,
            "case_key": f"{group_id}-case",
            "revision": 1,
            "split": "dev",
            "source_material": f"{group_id}-SOURCE",
            "source_facts": [{"fact_id": "F01", "text": "group fact"}],
            "required_fact_ids": ["F01"],
            "explicit_forbidden_claims": [],
            "task_notes": f"{group_id}-TASK",
            "feasibility_qa_status": "pass",
            "content_hash": f"{group_id}-CASE-HASH",
            "created_at": NOW,
            "updated_at": NOW,
        },
    )
    prompt_id = create_prompt_version(conn, f"{group_id}-PROMPT", f"{group_id}-v1", "test")
    run_id = create_evaluation_run(
        conn,
        prompt_id,
        group_id,
        "dev",
        {
            "case_set_hash": f"{group_id}-CASE-SET",
            "contract_hash": canonical_json_hash(TASK_PACK_CONTRACT),
            "generator_product": "UI_GENERATOR_PRODUCT",
            "generator_visible_model": "UI_GENERATOR_MODEL",
            "environment_notes": "UI_ENVIRONMENT",
            "protocol_version": "1.0",
            "created_at": NOW,
            "updated_at": NOW,
        },
    )
    output_id = record_model_output(
        conn, run_id, case_id, "generation-1.0", "c" * 64, "group raw candidate", NOW
    )
    conn.execute(
        """
        INSERT INTO evaluation_results (
            model_output_id, grader_result_id, grader_condition_id,
            aggregation_rule_version, calculated_status, blocking_reasons_json, calculated_at
            ) VALUES (?, NULL, ?, ?, ?, ?, ?)
        """,
        (output_id, ids["condition_id"], "aggregation-v1", "pass", "[]", NOW),
    )
    conn.commit()
    return output_id


def test_grader_condition_fresh_state_requires_explicit_selection(temporary_db_path, repo_root) -> None:
    ids = _seed(temporary_db_path, repo_root)
    conn = connect(temporary_db_path)
    _add_first_output(conn, ids)
    conn.close()
    page = _page_test("pages.evaluation", str(temporary_db_path), str(repo_root))
    assert not page.exception
    assert page.selectbox[1].value is None
    assert not page.code
    assert not page.button
    assert any("明确选择 Grader 条件" in item.value for item in page.info)


def test_grader_condition_unselected_cannot_submit_import(temporary_db_path, repo_root) -> None:
    ids = _seed(temporary_db_path, repo_root)
    conn = connect(temporary_db_path)
    _add_first_output(conn, ids)
    conn.close()
    page = _page_test("pages.evaluation", str(temporary_db_path), str(repo_root))
    assert page.selectbox[1].value is None
    conn = connect(temporary_db_path)
    assert conn.execute("SELECT COUNT(*) FROM grader_results").fetchone()[0] == 0
    conn.close()
    assert ids["run_id"] > 0


def test_grader_condition_explicit_second_selection_builds_second_condition_packet(
    temporary_db_path, repo_root
) -> None:
    ids = _seed(temporary_db_path, repo_root)
    conn = connect(temporary_db_path)
    _add_first_output(conn, ids)
    second_condition_id = _add_grader_condition(conn, ids["condition_id"], "SECOND_CONDITION")
    conn.close()
    page = _page_test("pages.evaluation", str(temporary_db_path), str(repo_root))
    page.selectbox[1].select(second_condition_id).run()
    assert not page.exception
    assert page.selectbox[1].value == second_condition_id
    assert "SECOND_CONDITION PROMPT" in page.code[0].value


def test_grader_condition_selection_survives_candidate_switch(
    temporary_db_path, repo_root
) -> None:
    ids = _seed(temporary_db_path, repo_root)
    conn = connect(temporary_db_path)
    _add_first_output(conn, ids)
    second_condition_id = _add_grader_condition(conn, ids["condition_id"], "SECOND_CONDITION")
    second_output_id = _add_second_output(conn, ids, "ui-case-2")
    conn.close()
    page = _page_test("pages.evaluation", str(temporary_db_path), str(repo_root))
    page.selectbox[1].select(second_condition_id).run()
    page.selectbox[0].select(second_output_id).run()
    assert not page.exception
    assert page.selectbox[1].value == second_condition_id
    assert "SECOND_CONDITION PROMPT" in page.code[0].value


def _store_indeterminate_result(db_path, repo_root, ids: dict[str, int]) -> int:
    conn = connect(db_path)
    output_id = record_model_output(
        conn,
        ids["run_id"],
        ids["case_id"],
        "generation-1.0",
        "a" * 64,
        '{"title":"设备简介","summary":"该设备重量为120克，来源材料仅提供这一项事实。这里使用额外的中性表述来满足固定长度要求，但不增加任何可以被判断真假的外部信息。请仅基于给定材料生成结构化短内容，并保持表达清晰、简洁且忠实于来源。","key_points":["设备重量为120克","仅依据给定来源材料","不补充额外事实信息"]}',
        NOW,
    )
    evaluate_output_rules(conn, output_id, TASK_PACK_CONTRACT, ["waterproof"])
    condition = dict(conn.execute("SELECT * FROM grader_conditions WHERE id = ?", (ids["condition_id"],)).fetchone())
    packet = build_blind_grader_packet(conn, output_id, ids["condition_id"])
    payload = json.loads((repo_root / "tests" / "fixtures" / "demo_grader_indeterminate.json").read_text(encoding="utf-8"))
    grader_id = import_grader_result(conn, output_id, condition, payload)
    result_id = calculate_output_status(conn, output_id, grader_id, ids["condition_id"])
    conn.close()
    return result_id


def test_model_output_page_preserves_invalid_response_runs_rules_and_separates_packet_provenance(
    temporary_db_path, repo_root
) -> None:
    ids = _seed(temporary_db_path, repo_root)
    page = _page_test("pages.model_outputs", str(temporary_db_path), str(repo_root))
    assert not page.exception
    assert page.title[0].value == "模型输出"
    assert page.subheader[0].value == "可直接复制的生成任务包"
    packet_text = page.code[0].value
    assert "UI_SOURCE_ONLY" in packet_text
    for forbidden in ("F01", "required_fact_ids", "v1", "UI_CASE_SET_HASH", "UI_GENERATOR_PRODUCT"):
        assert forbidden not in packet_text
    assert any("生成任务包版本" in item.value for item in page.caption)
    assert any("生成任务包哈希" in item.value for item in page.caption)

    page.text_area[0].set_value(RAW_INVALID_JSON)
    page.text_input[0].set_value(NOW)
    page.button[0].click().run()
    assert not page.exception
    conn = connect(temporary_db_path)
    output = conn.execute("SELECT * FROM model_outputs WHERE evaluation_run_id = ?", (ids["run_id"],)).fetchone()
    assert output["raw_response"] == RAW_INVALID_JSON
    assert output["generation_packet_version"] == "generation-1.0"
    assert output["generation_packet_hash"] == _hash(packet_text)
    assert conn.execute("SELECT status FROM rule_results WHERE model_output_id = ? AND rule_key = 'json_parse_pass'", (output["id"],)).fetchone()[0] == "fail"
    conn.close()
    rendered = "\n".join(item.value for item in page.markdown)
    assert "quality retry" not in rendered.lower()


def test_model_output_page_stores_technical_retry_separately(temporary_db_path, repo_root) -> None:
    ids = _seed(temporary_db_path, repo_root)
    page = _page_test("pages.model_outputs", str(temporary_db_path), str(repo_root))
    page.text_area[1].set_value("network error")
    page.button[1].click().run()
    assert not page.exception
    conn = connect(temporary_db_path)
    row = conn.execute("SELECT raw_response, technical_retry_count, technical_retry_reasons_json FROM model_outputs WHERE evaluation_run_id = ?", (ids["run_id"],)).fetchone()
    assert row["raw_response"] is None
    assert row["technical_retry_count"] == 1
    assert json.loads(row["technical_retry_reasons_json"]) == ["network error"]
    conn.close()


def test_model_output_page_records_visible_model_before_first_capture(temporary_db_path, repo_root) -> None:
    ids = _seed(temporary_db_path, repo_root, visible_model="not_visible")
    page = _page_test("pages.model_outputs", str(temporary_db_path), str(repo_root))

    page.text_input[0].set_value("GPT-5").run()
    page.button[0].click().run()

    assert not page.exception
    conn = connect(temporary_db_path)
    assert conn.execute(
        "SELECT generator_visible_model FROM evaluation_runs WHERE id = ?", (ids["run_id"],)
    ).fetchone()[0] == "GPT-5"
    assert conn.execute(
        "SELECT COUNT(*) FROM model_outputs WHERE evaluation_run_id = ?", (ids["run_id"],)
    ).fetchone()[0] == 0
    conn.close()


def test_evaluation_page_blind_grader_packet_hides_experiment_metadata(temporary_db_path, repo_root) -> None:
    ids = _seed(temporary_db_path, repo_root)
    conn = connect(temporary_db_path)
    output_id = record_model_output(conn, ids["run_id"], ids["case_id"], "generation-1.0", "a" * 64, "raw candidate", NOW)
    conn.close()
    page = _page_test("pages.evaluation", str(temporary_db_path), str(repo_root))
    assert not page.exception
    page.selectbox[1].select(ids["condition_id"]).run()
    assert not page.exception
    packet_text = page.code[0].value
    for forbidden in ("v1", "UI_CASE_SET_HASH", "UI_GENERATOR_PRODUCT", "UI_GENERATOR_MODEL", "calculated_status", "human_review", "previous"):
        assert forbidden not in packet_text
    assert "candidate-" in packet_text
    assert any("盲化 Grader 任务包哈希" in item.value for item in page.caption)
    assert "api" not in "\n".join(item.value for item in page.markdown).lower()
    assert output_id > 0


def test_evaluation_ui_passes_raw_grader_text_to_application_without_json_repair_or_write(
    temporary_db_path, repo_root
) -> None:
    ids = _seed(temporary_db_path, repo_root)
    conn = connect(temporary_db_path)
    record_model_output(conn, ids["run_id"], ids["case_id"], "generation-1.0", "a" * 64, "raw candidate", NOW)
    conn.close()
    page = _page_test("pages.evaluation", str(temporary_db_path), str(repo_root))
    page.selectbox[1].select(ids["condition_id"]).run()
    page.text_area[0].set_value("```json\n{}\n```")
    page.button[0].click().run()
    assert not page.exception
    assert page.error
    conn = connect(temporary_db_path)
    assert conn.execute("SELECT COUNT(*) FROM grader_results").fetchone()[0] == 0
    conn.close()


def test_evaluation_ui_imports_exact_seven_field_json_and_stores_packet_provenance(
    temporary_db_path, repo_root
) -> None:
    ids = _seed(temporary_db_path, repo_root)
    conn = connect(temporary_db_path)
    output_id = record_model_output(
        conn, ids["run_id"], ids["case_id"], "generation-1.0", "a" * 64, "raw candidate", NOW
    )
    packet = build_blind_grader_packet(conn, output_id, ids["condition_id"])
    conn.close()
    raw_text = (repo_root / "tests" / "fixtures" / "demo_grader_valid.json").read_text(encoding="utf-8")

    page = _page_test("pages.evaluation", str(temporary_db_path), str(repo_root))
    page.selectbox[1].select(ids["condition_id"]).run()
    page.text_area[0].set_value(raw_text)
    page.button[0].click().run()
    assert not page.exception
    assert page.success
    conn = connect(temporary_db_path)
    stored = conn.execute(
        "SELECT * FROM grader_results WHERE model_output_id = ?", (output_id,)
    ).fetchone()
    assert stored is not None
    assert set(json.loads(stored["raw_payload_json"])) == {
        "language_compliance",
        "required_facts",
        "unsupported_claims",
        "readability",
        "primary_error_type",
        "secondary_error_types",
        "grader_reason",
    }
    assert stored["blind_packet_version"] == packet["packet_version"]
    assert stored["blind_packet_hash"] == packet["content_hash"]
    conn.close()


def test_ui_pages_delegate_sql_reads_and_json_parsing_outside_page_modules(repo_root) -> None:
    for name in ("model_outputs.py", "evaluation.py", "analysis.py"):
        source = (repo_root / "pages" / name).read_text(encoding="utf-8")
        assert "conn.execute" not in source
    assert "json.loads" not in (repo_root / "pages" / "evaluation.py").read_text(encoding="utf-8")


def test_blind_human_review_hides_automatic_evidence_until_submission_then_shows_both_layers(
    temporary_db_path, repo_root
) -> None:
    ids = _seed(temporary_db_path, repo_root)
    result_id = _store_indeterminate_result(temporary_db_path, repo_root, ids)
    page = _page_test("pages.evaluation", str(temporary_db_path), str(repo_root))
    page.radio[0].set_value("盲化人工复核").run()
    assert not page.exception
    pre_submit = page.code[0].value
    for expected in ("candidate-", "UI_SOURCE_ONLY", "UI_TASK_INSTRUCTIONS", "Human Review Rubric", "Decision Options"):
        assert expected in pre_submit
    for forbidden in ("UI_GRADER_PROMPT", "UI_GRADER_RUBRIC", "calculated_status", "primary_error_type", "v1", "UI_GENERATOR_PRODUCT", "UI-COMP-01"):
        assert forbidden not in pre_submit
    page.selectbox[1].set_value("pass")
    page.text_area[0].set_value("independent evidence")
    page.text_area[1].set_value("independent reason")
    page.button[0].click().run()
    assert not page.exception
    rendered = "\n".join(item.value for item in [*page.markdown, *page.caption])
    assert "calculated_status（自动计算）：indeterminate" in rendered
    assert "final_decision（人工最终裁决）：pass" in rendered
    conn = connect(temporary_db_path)
    assert conn.execute("SELECT calculated_status FROM evaluation_results WHERE id = ?", (result_id,)).fetchone()[0] == "indeterminate"
    review = conn.execute("SELECT review_scope, final_decision FROM human_reviews WHERE evaluation_result_id = ?", (result_id,)).fetchone()
    assert review["review_scope"] == "required"
    assert review["final_decision"] == "pass"
    conn.close()


def test_corrective_human_review_path_displays_literal_raw_response_without_auto_outcomes(
    temporary_db_path, repo_root
) -> None:
    ids = _seed(temporary_db_path, repo_root)
    result_id = _store_indeterminate_result(temporary_db_path, repo_root, ids)
    conn = connect(temporary_db_path)
    conn.execute(
        "UPDATE model_outputs SET raw_response = raw_response || char(10) WHERE id = (SELECT model_output_id FROM evaluation_results WHERE id = ?)",
        (result_id,),
    )
    conn.commit()
    review_id = insert_human_review(
        conn,
        {
            "evaluation_result_id": result_id,
            "review_scope": "required",
            "blind_review": True,
            "evidence": {"original": "display was misleading"},
            "reason": "original procedure-invalid review",
            "final_decision": "fail",
            "reviewed_at": NOW,
        },
    )
    authorize_human_review_correction_target(
        conn, review_id, result_id, "procedure-invalid review", authorized_at=NOW
    )
    conn.close()

    page = _page_test("pages.evaluation", str(temporary_db_path), str(repo_root))
    page.radio[0].set_value("纠正性人工复核（corrective-re-review）").run()
    assert not page.exception
    packet_text = page.code[0].value
    assert "## 原始模型回答（逐字文本）\n{" in packet_text
    assert '\"{\\\"title\\\"' not in packet_text
    for forbidden in ("calculated_status", "grader_result", "UI-COMP-01"):
        assert forbidden not in packet_text


def test_blind_human_review_batch_selector_does_not_expose_comparison_group_ids(
    temporary_db_path, repo_root
) -> None:
    ids = _seed(temporary_db_path, repo_root)
    conn = connect(temporary_db_path)
    first_output_id = _add_first_output(conn, ids)
    conn.execute(
        """
        INSERT INTO evaluation_results (
            model_output_id, grader_result_id, grader_condition_id,
            aggregation_rule_version, calculated_status, blocking_reasons_json, calculated_at
        ) VALUES (?, NULL, ?, ?, ?, ?, ?)
        """,
        (first_output_id, ids["condition_id"], "aggregation-v1", "pass", "[]", NOW),
    )
    conn.commit()
    _add_review_group(conn, ids, "SECOND-REVIEW-GROUP")
    conn.close()

    page = _page_test("pages.evaluation", str(temporary_db_path), str(repo_root))
    page.radio[0].set_value("盲化人工复核").run()

    assert not page.exception
    batch_options = [str(option) for option in page.selectbox[0].options]
    assert batch_options == ["评测批次 1", "评测批次 2"]
    assert "UI-COMP-01" not in batch_options
    assert "SECOND-REVIEW-GROUP" not in batch_options


def test_analysis_page_separates_status_layers_and_read_only(temporary_db_path, repo_root) -> None:
    ids = _seed(temporary_db_path, repo_root)
    _store_indeterminate_result(temporary_db_path, repo_root, ids)
    conn = connect(temporary_db_path)
    before = "\n".join(conn.iterdump())
    conn.close()
    page = _page_test("pages.analysis", str(temporary_db_path), str(repo_root))
    assert not page.exception
    rendered = "\n".join(item.value for item in [*page.markdown, *page.caption])
    for label in ("calculated_status", "final_decision", "人工复核覆盖率", "determinate", "indeterminate 比例"):
        assert label in rendered
    conn = connect(temporary_db_path)
    assert "\n".join(conn.iterdump()) == before
    conn.close()
