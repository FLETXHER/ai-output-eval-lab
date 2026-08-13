from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence

from eval_lab.application.prompts import WorkflowError
from eval_lab.domain.task_pack import TASK_PACK_CONTRACT, canonical_json_hash
from eval_lab.imports.test_cases import parse_test_case_payload, validate_experiment_assets
from eval_lab.repositories.sqlite import insert_grader_condition, transaction


def load_case(conn: sqlite3.Connection, case_id: int) -> dict[str, object]:
    """Load one Case and its fixed Task Pack contract in application-ready form."""
    row = conn.execute(
        """
        SELECT tc.*, tp.pack_key, tp.contract_version, tp.contract_hash,
               tp.language, tp.title_min_chars, tp.title_max_chars,
               tp.summary_min_chars, tp.summary_max_chars, tp.key_points_count,
               tp.key_point_min_chars, tp.key_point_max_chars
        FROM test_cases AS tc
        JOIN task_packs AS tp ON tp.id = tc.task_pack_id
        WHERE tc.id = ?
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        raise WorkflowError(f"test case {case_id} was not found")

    return {
        "id": row["id"],
        "case_key": row["case_key"],
        "revision": row["revision"],
        "split": row["split"],
        "source_material": row["source_material"],
        "source_facts": _load_json_list(row["source_facts_json"], "source_facts_json"),
        "required_fact_ids": _load_json_list(
            row["required_fact_ids_json"], "required_fact_ids_json"
        ),
        "explicit_forbidden_claims": _load_json_list(
            row["explicit_forbidden_claims_json"], "explicit_forbidden_claims_json"
        ),
        "task_notes": row["task_notes"],
        "feasibility_qa_status": row["feasibility_qa_status"],
        "content_hash": row["content_hash"],
        "task_pack_contract": {
            "pack_key": row["pack_key"],
            "contract_version": row["contract_version"],
            "contract_hash": row["contract_hash"],
            "language": row["language"],
            "title_min_chars": row["title_min_chars"],
            "title_max_chars": row["title_max_chars"],
            "summary_min_chars": row["summary_min_chars"],
            "summary_max_chars": row["summary_max_chars"],
            "key_points_count": row["key_points_count"],
            "key_point_min_chars": row["key_point_min_chars"],
            "key_point_max_chars": row["key_point_max_chars"],
            "root_keys": ["title", "summary", "key_points"],
        },
    }


def _load_json_list(raw_value: object, field_name: str) -> list[object]:
    if not isinstance(raw_value, str):
        raise WorkflowError(f"stored {field_name} must be JSON text")
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"stored {field_name} is not valid JSON") from exc
    if not isinstance(parsed, list):
        raise WorkflowError(f"stored {field_name} must be a JSON list")
    return parsed


def compute_case_set_hash(cases: Sequence[Mapping[str, object]]) -> str:
    """Hash a Case collection in stable Case-key/revision order."""
    normalized_cases: list[dict[str, object]] = []
    for case in cases:
        if isinstance(case, Mapping):
            normalized_cases.append(dict(case))
        else:
            normalized_cases.append({"invalid_case_value": repr(case)})
    ordered_cases = sorted(
        normalized_cases,
        key=lambda case: (
            str(case.get("case_key", "")),
            str(case.get("revision", "")),
            canonical_json_hash(case),
        ),
    )
    return canonical_json_hash(ordered_cases)


def qa_case_set(
    cases: Sequence[Mapping[str, object]], task_pack: Mapping[str, object]
) -> dict[str, object]:
    """Validate formal Case-set readiness without persistence or semantic solving."""
    errors: list[str] = []
    task_pack_contract = {
        key: value for key, value in task_pack.items() if key != "contract_hash"
    }
    expected_contract_hash = canonical_json_hash(TASK_PACK_CONTRACT)
    if task_pack_contract != TASK_PACK_CONTRACT:
        errors.append("task pack does not match the fixed contract")
    if task_pack.get("contract_hash") != expected_contract_hash:
        errors.append("task pack contract_hash does not match the fixed contract")

    seen_keys: set[tuple[str, object]] = set()
    dev_cases = 0
    holdout_cases = 0
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            errors.append(f"case[{index}] must be an object")
            continue

        parsed = parse_test_case_payload(case)
        errors.extend(f"case[{index}]: {error}" for error in parsed["errors"])

        case_key = case.get("case_key")
        revision = case.get("revision")
        if isinstance(case_key, str) and case_key.strip() and isinstance(revision, int):
            identity = (case_key.strip(), revision)
            if identity in seen_keys:
                errors.append(f"duplicate case_key/revision: {identity[0]} rev {identity[1]}")
            seen_keys.add(identity)

        split = case.get("split")
        if split == "dev":
            dev_cases += 1
        elif split == "holdout":
            holdout_cases += 1

        if case.get("feasibility_qa_status") != "pass":
            errors.append(f"case[{index}] feasibility_qa_status must be 'pass' for formal readiness")
        if case.get("contract_hash") != expected_contract_hash:
            errors.append(f"case[{index}] contract_hash does not match the task pack contract")
        if case.get("content_hash") != _case_content_hash(case):
            errors.append(f"case[{index}] content_hash does not match Case content")

    total_cases = len(cases)
    if total_cases != 24:
        errors.append(f"formal Case set must contain exactly 24 cases, found {total_cases}")
    if dev_cases != 18:
        errors.append(f"formal Case set must contain exactly 18 dev cases, found {dev_cases}")
    if holdout_cases != 6:
        errors.append(
            f"formal Case set must contain exactly 6 holdout cases, found {holdout_cases}"
        )

    return {
        "total_cases": total_cases,
        "dev_cases": dev_cases,
        "holdout_cases": holdout_cases,
        "errors": errors,
        "case_set_hash": compute_case_set_hash(cases),
        "formal_ready": not errors,
    }


def register_approved_experiment_assets(
    conn: sqlite3.Connection, payload: Mapping[str, object]
) -> dict[str, int]:
    """Persist the owner-approved v1 asset snapshots as formal provenance.

    A checked-in draft manifest is deliberately rejected. This operation is
    the only bridge from file-based assets into ``prompt_versions`` and
    ``grader_conditions``; it adds no new storage shape.
    """
    errors = validate_experiment_assets(payload)
    if errors:
        raise WorkflowError("experiment assets must be owner-approved: " + "; ".join(errors))
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise WorkflowError("experiment assets must include an assets list")
    by_type = {
        asset["asset_type"]: asset
        for asset in assets
        if isinstance(asset, Mapping) and isinstance(asset.get("asset_type"), str)
    }
    required_types = ("prompt_v1", "grader_prompt_v1", "rubric_v1", "error_taxonomy_v1")
    if any(asset_type not in by_type for asset_type in required_types):
        raise WorkflowError("experiment assets are missing required v1 snapshots")

    prompt_asset = by_type["prompt_v1"]
    grader_prompt = by_type["grader_prompt_v1"]
    rubric = by_type["rubric_v1"]
    taxonomy = by_type["error_taxonomy_v1"]
    approved_at = _approved_at(prompt_asset)
    try:
        grader_product = _required_text(payload, "grader_product")
        grader_visible_model = _required_text(payload, "grader_visible_model")
        prompt_text = _required_text(prompt_asset, "content")
        prompt_hash = _required_text(prompt_asset, "content_hash")
    except WorkflowError:
        raise

    # Imports are validated before the transaction so rejected drafts leave no
    # partial Prompt/Grader provenance rows.
    from eval_lab.application.prompts import (
        approve_prompt_version,
        create_prompt_version,
        freeze_prompt_version,
    )

    with transaction(conn):
        prompt_version_id = create_prompt_version(
            conn,
            prompt_text,
            "v1",
            "Owner-approved formal baseline experiment asset",
        )
        stored_hash = conn.execute(
            "SELECT content_hash FROM prompt_versions WHERE id = ?", (prompt_version_id,)
        ).fetchone()[0]
        if stored_hash != prompt_hash:
            raise WorkflowError("stored Prompt v1 hash does not match approved asset snapshot")
        approve_prompt_version(conn, prompt_version_id, approved_at)
        freeze_prompt_version(conn, prompt_version_id, approved_at)
        grader_condition_id = insert_grader_condition(
            conn,
            {
                "grader_product": grader_product,
                "grader_visible_model": grader_visible_model,
                "grader_prompt": _required_text(grader_prompt, "content"),
                "grader_prompt_hash": _required_text(grader_prompt, "content_hash"),
                "grader_prompt_version_label": "v1",
                "rubric": _required_text(rubric, "content"),
                "rubric_hash": _required_text(rubric, "content_hash"),
                "rubric_version_label": "v1",
                "error_taxonomy": _required_text(taxonomy, "content"),
                "error_taxonomy_hash": _required_text(taxonomy, "content_hash"),
                "error_taxonomy_version_label": "v1",
                "owner_approved_at": _approved_at(grader_prompt),
                "created_at": _approved_at(grader_prompt),
            },
        )
    return {
        "prompt_version_id": prompt_version_id,
        "grader_condition_id": grader_condition_id,
    }


def _case_content_hash(case: Mapping[str, object]) -> str:
    return canonical_json_hash({key: value for key, value in case.items() if key != "content_hash"})


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"experiment asset {key} must be a non-empty string")
    return value


def _approved_at(asset: Mapping[str, object]) -> str:
    value = asset.get("owner_approved_at")
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError("experiment asset must have owner_approved_at")
    return value
