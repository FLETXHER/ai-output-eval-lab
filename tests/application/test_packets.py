from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from eval_lab.application.packets import (
    build_blind_grader_packet,
    build_blind_human_review_packet,
    build_generation_packet,
)
from eval_lab.domain.task_pack import TASK_PACK_CONTRACT, canonical_json_hash
from eval_lab.repositories.sqlite import connect, initialize_database


NOW = "2026-08-13T00:00:00Z"


@pytest.fixture
def conn(temporary_db_path: Path, repo_root: Path):
    connection = connect(temporary_db_path)
    initialize_database(connection, repo_root / "db" / "schema.sql")
    yield connection
    connection.close()


def _insert_context(conn: sqlite3.Connection) -> dict[str, int]:
    contract = TASK_PACK_CONTRACT
    task_pack_id = conn.execute(
        """
        INSERT INTO task_packs (
            pack_key, contract_version, contract_hash, language,
            title_min_chars, title_max_chars, summary_min_chars,
            summary_max_chars, key_points_count, key_point_min_chars,
            key_point_max_chars, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            contract["pack_key"],
            contract["contract_version"],
            canonical_json_hash(contract),
            contract["language"],
            contract["title_min_chars"],
            contract["title_max_chars"],
            contract["summary_min_chars"],
            contract["summary_max_chars"],
            contract["key_points_count"],
            contract["key_point_min_chars"],
            contract["key_point_max_chars"],
            NOW,
            NOW,
        ),
    ).lastrowid
    assert task_pack_id is not None

    source_facts = [
        {"fact_id": "F01", "text": "九月九日启动"},
        {"fact_id": "F02", "text": "在北京举行发布会"},
    ]
    forbidden_claims = ["全球首发"]
    case_id = conn.execute(
        """
        INSERT INTO test_cases (
            task_pack_id, case_key, revision, split, source_material,
            source_facts_json, required_fact_ids_json,
            explicit_forbidden_claims_json, task_notes,
            feasibility_qa_status, content_hash, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_pack_id,
            "case-001",
            7,
            "holdout",
            "星河计划将于九月九日启动，并在北京举行发布会。",
            json.dumps(source_facts, ensure_ascii=False),
            json.dumps(["F01"], ensure_ascii=False),
            json.dumps(forbidden_claims, ensure_ascii=False),
            "标题需突出启动日期。",
            "pass",
            "FORBIDDEN_CASE_HASH",
            NOW,
            NOW,
        ),
    ).lastrowid
    assert case_id is not None

    prompt_id = conn.execute(
        """
        INSERT INTO prompt_versions (
            version_label, prompt_text, change_reason, content_hash,
            status, owner_approved_at, frozen_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "v2-FORBIDDEN",
            "实际提示词：忠实依据材料并只输出 JSON。",
            "FORBIDDEN_DESIRED_IMPROVEMENT",
            "FORBIDDEN_PROMPT_HASH",
            "frozen",
            NOW,
            NOW,
            NOW,
            NOW,
        ),
    ).lastrowid
    assert prompt_id is not None

    run_id = conn.execute(
        """
        INSERT INTO evaluation_runs (
            comparison_group_id, prompt_version_id, split, case_set_hash,
            contract_hash, generator_product, generator_visible_model,
            environment_notes, protocol_version, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "FORBIDDEN_COMPARISON_GROUP",
            prompt_id,
            "holdout",
            "FORBIDDEN_CASE_SET_HASH",
            canonical_json_hash(contract),
            "FORBIDDEN_GENERATOR_PRODUCT",
            "FORBIDDEN_GENERATOR_MODEL",
            "FORBIDDEN_ENVIRONMENT_NOTES",
            "FORBIDDEN_PROTOCOL_VERSION",
            "open",
            NOW,
            NOW,
        ),
    ).lastrowid
    assert run_id is not None

    raw_response = '{"title":"九月九日启动","summary":"原样回答"}'
    model_output_id = conn.execute(
        """
        INSERT INTO model_outputs (
            evaluation_run_id, test_case_id, candidate_id,
            generation_packet_version, generation_packet_hash, raw_response,
            output_hash, generated_at, technical_retry_count,
            technical_retry_reasons_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            case_id,
            "candidate-c84f2a",
            "placeholder-generation-version",
            "placeholder-generation-hash",
            raw_response,
            "FORBIDDEN_OUTPUT_HASH",
            NOW,
            0,
            "[]",
            NOW,
            NOW,
        ),
    ).lastrowid
    assert model_output_id is not None

    grader_condition_id = conn.execute(
        """
        INSERT INTO grader_conditions (
            grader_product, grader_visible_model, grader_prompt,
            grader_prompt_hash, grader_prompt_version_label, rubric,
            rubric_hash, rubric_version_label, error_taxonomy,
            error_taxonomy_hash, error_taxonomy_version_label,
            owner_approved_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "FORBIDDEN_GRADER_PRODUCT",
            "FORBIDDEN_GRADER_MODEL",
            "逐项检查候选回答。",
            "FORBIDDEN_GRADER_PROMPT_HASH",
            "FORBIDDEN_GRADER_PROMPT_LABEL",
            "事实必须由来源材料支持。",
            "FORBIDDEN_RUBRIC_HASH",
            "FORBIDDEN_RUBRIC_LABEL",
            "missing_fact | unsupported_claim",
            "FORBIDDEN_TAXONOMY_HASH",
            "FORBIDDEN_TAXONOMY_LABEL",
            NOW,
            NOW,
        ),
    ).lastrowid
    assert grader_condition_id is not None

    grader_result_id = conn.execute(
        """
        INSERT INTO grader_results (
            model_output_id, grader_condition_id, blind_packet_version,
            blind_packet_hash, raw_payload_json, import_status,
            normalized_semantic_json, language_compliance, readability,
            primary_error_type, secondary_error_types_json,
            unsupported_claims_json, reason_json, evidence_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            model_output_id,
            grader_condition_id,
            "placeholder-blind-version",
            "placeholder-blind-hash",
            '{"FORBIDDEN_PRIOR_GRADER_RESULT":true}',
            "valid",
            '{"FORBIDDEN_NORMALIZED_RESULT":true}',
            "fail",
            "FORBIDDEN_READABILITY",
            "FORBIDDEN_PRIMARY_ERROR_TYPE",
            "[]",
            "[]",
            '{"FORBIDDEN_GRADER_REASON":true}',
            '{"FORBIDDEN_GRADER_EVIDENCE":true}',
            NOW,
        ),
    ).lastrowid
    assert grader_result_id is not None

    evaluation_result_id = conn.execute(
        """
        INSERT INTO evaluation_results (
            model_output_id, grader_result_id, grader_condition_id,
            aggregation_rule_version, calculated_status,
            blocking_reasons_json, calculated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            model_output_id,
            grader_result_id,
            grader_condition_id,
            "FORBIDDEN_AGGREGATION_VERSION",
            "fail",
            '["FORBIDDEN_BLOCKING_REASON"]',
            NOW,
        ),
    ).lastrowid
    assert evaluation_result_id is not None

    conn.execute(
        """
        INSERT INTO human_reviews (
            evaluation_result_id, review_scope, blind_review, evidence_json,
            reason, final_decision, reviewed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evaluation_result_id,
            "manual",
            1,
            '{"FORBIDDEN_PREVIOUS_HUMAN_EVIDENCE":true}',
            "FORBIDDEN_PREVIOUS_HUMAN_REASON",
            "fail",
            NOW,
        ),
    )
    return {
        "run_id": run_id,
        "case_id": case_id,
        "model_output_id": model_output_id,
        "grader_condition_id": grader_condition_id,
        "grader_result_id": grader_result_id,
        "evaluation_result_id": evaluation_result_id,
    }


def test_generation_builder_is_repeatable_and_persists_output_provenance(
    conn: sqlite3.Connection,
) -> None:
    ids = _insert_context(conn)

    first = build_generation_packet(conn, ids["run_id"], ids["case_id"])
    second = build_generation_packet(conn, ids["run_id"], ids["case_id"])

    assert first == second
    stored = conn.execute(
        """
        SELECT generation_packet_version, generation_packet_hash
        FROM model_outputs WHERE id = ?
        """,
        (ids["model_output_id"],),
    ).fetchone()
    assert tuple(stored) == (first["packet_version"], first["content_hash"])
    exposed = first["text"] + json.dumps(first["payload"], ensure_ascii=False)
    assert "实际提示词：忠实依据材料并只输出 JSON。" in exposed
    for forbidden in (
        "v2-FORBIDDEN",
        "FORBIDDEN_CASE_HASH",
        "FORBIDDEN_PROMPT_HASH",
        "FORBIDDEN_COMPARISON_GROUP",
        "FORBIDDEN_GENERATOR_PRODUCT",
        "FORBIDDEN_GENERATOR_MODEL",
        "FORBIDDEN_FACT",
    ):
        assert forbidden not in exposed


def test_blind_grader_builder_is_repeatable_and_persists_grader_provenance(
    conn: sqlite3.Connection,
) -> None:
    ids = _insert_context(conn)

    first = build_blind_grader_packet(
        conn, ids["model_output_id"], ids["grader_condition_id"]
    )
    second = build_blind_grader_packet(
        conn, ids["model_output_id"], ids["grader_condition_id"]
    )

    assert first == second
    stored = conn.execute(
        """
        SELECT blind_packet_version, blind_packet_hash
        FROM grader_results WHERE id = ?
        """,
        (ids["grader_result_id"],),
    ).fetchone()
    assert tuple(stored) == (first["packet_version"], first["content_hash"])
    assert first["payload"]["raw_model_response"] == (
        '{"title":"九月九日启动","summary":"原样回答"}'
    )
    exposed = first["text"] + json.dumps(first["payload"], ensure_ascii=False)
    for allowed in ("F01", "逐项检查候选回答。", "missing_fact | unsupported_claim"):
        assert allowed in exposed
    assert set(first["payload"]["constraints"]) == {
        "task_instructions",
        "explicit_forbidden_claims",
    }
    for forbidden in (
        "v2-FORBIDDEN",
        "holdout",
        "FORBIDDEN_GENERATOR_PRODUCT",
        "FORBIDDEN_GENERATOR_MODEL",
        "FORBIDDEN_PRIOR_GRADER_RESULT",
        "FORBIDDEN_PREVIOUS_HUMAN_REASON",
        "FORBIDDEN_BLOCKING_REASON",
    ):
        assert forbidden not in exposed


def test_blind_human_review_builder_exposes_no_automatic_or_experiment_metadata(
    conn: sqlite3.Connection,
) -> None:
    ids = _insert_context(conn)

    first = build_blind_human_review_packet(conn, ids["evaluation_result_id"])
    second = build_blind_human_review_packet(conn, ids["evaluation_result_id"])

    assert first == second
    assert first["payload"]["candidate_id"] == "candidate-c84f2a"
    assert first["payload"]["raw_model_response"] == (
        '{"title":"九月九日启动","summary":"原样回答"}'
    )
    assert first["payload"]["task_instructions"] == "标题需突出启动日期。"
    assert first["payload"]["decision_options"] == [
        "pass",
        "fail",
        "indeterminate",
    ]
    assert set(first["payload"]["constraints"]) == {"explicit_forbidden_claims"}
    exposed = first["text"] + json.dumps(first["payload"], ensure_ascii=False)
    for forbidden in (
        "v2-FORBIDDEN",
        "holdout",
        "FORBIDDEN_GENERATOR_PRODUCT",
        "FORBIDDEN_GENERATOR_MODEL",
        "FORBIDDEN_PRIOR_GRADER_RESULT",
        "FORBIDDEN_GRADER_REASON",
        "FORBIDDEN_GRADER_EVIDENCE",
        "FORBIDDEN_PRIMARY_ERROR_TYPE",
        "FORBIDDEN_PREVIOUS_HUMAN_REASON",
        "FORBIDDEN_PREVIOUS_HUMAN_EVIDENCE",
        "FORBIDDEN_BLOCKING_REASON",
        "FORBIDDEN_AGGREGATION_VERSION",
    ):
        assert forbidden not in exposed


@pytest.mark.parametrize(
    ("builder", "args"),
    [
        (build_generation_packet, (999, 999)),
        (build_blind_grader_packet, (999, 999)),
        (build_blind_human_review_packet, (999,)),
    ],
)
def test_packet_builders_reject_missing_database_context(
    conn: sqlite3.Connection, builder, args: tuple[int, ...]
) -> None:
    with pytest.raises(LookupError):
        builder(conn, *args)
