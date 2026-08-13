from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import sqlite3

from eval_lab.application.cases import load_case
from eval_lab.application.packets import build_blind_grader_packet
from eval_lab.application.prompts import WorkflowError
from eval_lab.domain.grader_contract import normalize_grader_payload
from eval_lab.domain.status import aggregate_calculated_status
from eval_lab.imports.grader_results import parse_grader_payload
from eval_lab.repositories.sqlite import (
    insert_evaluation_result,
    insert_grader_fact_results,
    insert_grader_result,
)


def build_blind_grader_packet_for_output(
    conn: sqlite3.Connection, model_output_id: int, grader_condition_id: int
) -> dict[str, object]:
    """Build exactly one pointwise, version-blind Grader packet."""
    return build_blind_grader_packet(conn, model_output_id, grader_condition_id)


def import_grader_result(
    conn: sqlite3.Connection,
    model_output_id: int,
    grader_condition: Mapping[str, object],
    raw_payload: Mapping[str, object],
) -> int:
    """Validate and persist a returned Grader JSON result without repair."""
    condition_id = _grader_condition_id(grader_condition)
    _stored_condition(conn, condition_id, grader_condition)
    case_id = _case_id_for_output(conn, model_output_id)
    case = load_case(conn, case_id)
    required_fact_ids = _required_fact_ids(case)
    packet = build_blind_grader_packet_for_output(conn, model_output_id, condition_id)

    validation = parse_grader_payload(raw_payload, required_fact_ids)
    if not validation["ok"] or validation["value"] is None:
        raise WorkflowError("invalid grader payload: " + "; ".join(validation["errors"]))
    value = validation["value"]
    if (
        value["blind_packet_version"] != packet["packet_version"]
        or value["blind_packet_hash"] != packet["content_hash"]
    ):
        raise WorkflowError("grader packet provenance does not match the rendered packet")
    if conn.execute(
        "SELECT 1 FROM grader_results WHERE model_output_id = ? AND grader_condition_id = ?",
        (model_output_id, condition_id),
    ).fetchone() is not None:
        raise WorkflowError("a grader result already exists for this output and condition")

    semantic = normalize_grader_payload(
        {key: item for key, item in value.items() if not key.startswith("blind_packet_")},
        required_fact_ids,
    )
    now = _utc_now()
    result_id = insert_grader_result(
        conn,
        {
            "model_output_id": model_output_id,
            "grader_condition_id": condition_id,
            "blind_packet_version": value["blind_packet_version"],
            "blind_packet_hash": value["blind_packet_hash"],
            "raw_payload": dict(raw_payload),
            "import_status": "valid",
            "normalized_semantic": semantic,
            "language_compliance": _label(semantic["language_compliance"]),
            "readability": _label(semantic["readability"]),
            "primary_error_type": semantic["primary_error_type"],
            "secondary_error_types": semantic["secondary_error_types"],
            "unsupported_claims": semantic["unsupported_claims"],
            "reason": _reason_snapshot(semantic),
            "evidence": _evidence_snapshot(semantic),
            "created_at": now,
        },
    )
    facts = semantic["required_facts"]
    if not isinstance(facts, list):
        raise WorkflowError("normalized grader facts must be a list")
    insert_grader_fact_results(
        conn,
        result_id,
        [
            {
                "fact_id": fact["fact_id"],
                "status": fact["label"],
                "output_evidence": fact["output_evidence"],
                "reason": fact["reason"],
            }
            for fact in facts
            if isinstance(fact, Mapping)
        ],
    )
    return result_id


def calculate_output_status(
    conn: sqlite3.Connection,
    model_output_id: int,
    grader_result_id: int | None,
    grader_condition_id: int,
    aggregation_rule_version: str = "1.0",
) -> int:
    """Persist the Domain-calculated automatic status; never use Human Review."""
    _require_non_empty(aggregation_rule_version, "aggregation_rule_version")
    case_id = _case_id_for_output(conn, model_output_id)
    case = load_case(conn, case_id)
    required_fact_ids = _required_fact_ids(case)
    _stored_condition(conn, grader_condition_id)
    if conn.execute(
        "SELECT 1 FROM evaluation_results WHERE model_output_id = ? AND grader_condition_id = ?",
        (model_output_id, grader_condition_id),
    ).fetchone() is not None:
        raise WorkflowError("an evaluation result already exists for this output and condition")

    rule_rows = conn.execute(
        "SELECT rule_key, status, reason FROM rule_results WHERE model_output_id = ? ORDER BY id",
        (model_output_id,),
    ).fetchall()
    rules = [dict(row) for row in rule_rows]
    grader = _load_grader_semantic(
        conn, model_output_id, grader_result_id, grader_condition_id
    )
    aggregated = aggregate_calculated_status(
        rules, grader, required_fact_ids, aggregation_rule_version
    )
    return insert_evaluation_result(
        conn,
        {
            "model_output_id": model_output_id,
            "grader_result_id": grader_result_id,
            "grader_condition_id": grader_condition_id,
            "aggregation_rule_version": aggregation_rule_version,
            "calculated_status": aggregated["calculated_status"],
            "blocking_reasons": aggregated["blocking_reasons"],
            "calculated_at": _utc_now(),
        },
    )


def _grader_condition_id(grader_condition: Mapping[str, object]) -> int:
    value = grader_condition.get("id")
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise WorkflowError("grader_condition must include a positive integer id")
    return value


def _stored_condition(
    conn: sqlite3.Connection,
    condition_id: int,
    supplied: Mapping[str, object] | None = None,
) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM grader_conditions WHERE id = ?", (condition_id,)).fetchone()
    if row is None:
        raise WorkflowError(f"grader condition {condition_id} was not found")
    if supplied is not None:
        for key in (
            "grader_prompt", "grader_prompt_hash", "rubric", "rubric_hash",
            "error_taxonomy", "error_taxonomy_hash",
        ):
            if key in supplied and supplied[key] != row[key]:
                raise WorkflowError("grader condition snapshots must match stored provenance")
    return row


def _case_id_for_output(conn: sqlite3.Connection, model_output_id: int) -> int:
    row = conn.execute(
        "SELECT test_case_id FROM model_outputs WHERE id = ?", (model_output_id,)
    ).fetchone()
    if row is None:
        raise WorkflowError(f"model output {model_output_id} was not found")
    return int(row["test_case_id"])


def _required_fact_ids(case: Mapping[str, object]) -> list[str]:
    values = case["required_fact_ids"]
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise WorkflowError("stored required_fact_ids must be a list of strings")
    return values


def _load_grader_semantic(
    conn: sqlite3.Connection,
    model_output_id: int,
    grader_result_id: int | None,
    grader_condition_id: int,
) -> dict[str, object] | None:
    if grader_result_id is None:
        return None
    row = conn.execute(
        """
        SELECT normalized_semantic_json, import_status
        FROM grader_results
        WHERE id = ? AND model_output_id = ? AND grader_condition_id = ?
        """,
        (grader_result_id, model_output_id, grader_condition_id),
    ).fetchone()
    if row is None:
        raise WorkflowError("grader result does not belong to this output and condition")
    if row["import_status"] != "valid" or row["normalized_semantic_json"] is None:
        return None
    try:
        semantic = json.loads(row["normalized_semantic_json"])
    except json.JSONDecodeError as exc:
        raise WorkflowError("stored normalized grader result is not valid JSON") from exc
    if not isinstance(semantic, dict):
        raise WorkflowError("stored normalized grader result must be an object")
    return semantic


def _label(value: object) -> str:
    if not isinstance(value, Mapping) or not isinstance(value.get("label"), str):
        raise WorkflowError("normalized diagnostic is invalid")
    return value["label"]


def _reason_snapshot(semantic: Mapping[str, object]) -> dict[str, object]:
    return {
        "grader_reason": semantic["grader_reason"],
        "language_compliance": semantic["language_compliance"]["reason"],  # type: ignore[index]
        "readability": semantic["readability"]["reason"],  # type: ignore[index]
    }


def _evidence_snapshot(semantic: Mapping[str, object]) -> dict[str, object]:
    return {
        "language_compliance": semantic["language_compliance"]["evidence"],  # type: ignore[index]
        "readability": semantic["readability"]["evidence"],  # type: ignore[index]
    }


def _require_non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"{field_name} must be a non-empty string")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
