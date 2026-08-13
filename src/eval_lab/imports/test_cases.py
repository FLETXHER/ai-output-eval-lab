from __future__ import annotations

from collections.abc import Mapping
import hashlib
from pathlib import Path

from eval_lab.domain.task_pack import (
    TASK_PACK_CONTRACT,
    canonical_json_hash,
    validate_case_record,
    validate_task_pack_contract,
)
from eval_lab.imports import (
    ValidationResult,
    exact_keys,
    invalid,
    non_empty_string,
    parse_json_text,
    sha256_hash,
    valid,
)


_TASK_PACK_KEYS = {
    "pack_key",
    "contract_version",
    "language",
    "root_keys",
    "title_min_chars",
    "title_max_chars",
    "summary_min_chars",
    "summary_max_chars",
    "key_points_count",
    "key_point_min_chars",
    "key_point_max_chars",
}
_TEST_CASE_KEYS = {
    "case_key",
    "revision",
    "split",
    "source_material",
    "source_facts",
    "required_fact_ids",
    "explicit_forbidden_claims",
    "task_notes",
    "feasibility_qa_status",
    "content_hash",
    "contract_hash",
    "traceability_metadata",
}

_TRACEABILITY_KEYS = {"source_of_truth", "source_facts_traceable"}
_EXPERIMENT_ASSET_MANIFEST_KEYS = {
    "manifest_version",
    "grader_product",
    "grader_visible_model",
    "assets",
}
_EXPERIMENT_ASSET_KEYS = {
    "asset_type",
    "version_label",
    "content",
    "content_hash",
    "status",
    "owner_approved_at",
}
_REQUIRED_EXPERIMENT_ASSET_TYPES = {
    "prompt_v1",
    "grader_prompt_v1",
    "rubric_v1",
    "error_taxonomy_v1",
}


def parse_task_pack_payload(payload: Mapping[str, object]) -> ValidationResult:
    """Validate the one fixed task-pack contract at an import boundary."""
    if not isinstance(payload, Mapping):
        return invalid(["task pack payload must be an object"])
    errors = exact_keys(payload, _TASK_PACK_KEYS, "task pack payload")
    errors.extend(validate_task_pack_contract(payload))
    return invalid(errors) if errors else valid(payload)


def parse_test_case_payload(payload: Mapping[str, object]) -> ValidationResult:
    """Validate external Case annotations without evaluating model output."""
    if not isinstance(payload, Mapping):
        return invalid(["test case payload must be an object"])
    errors = exact_keys(payload, _TEST_CASE_KEYS, "test case payload")
    errors.extend(validate_case_record(payload))
    errors.extend(sha256_hash(payload.get("content_hash"), "content_hash"))
    errors.extend(sha256_hash(payload.get("contract_hash"), "contract_hash"))
    errors.extend(_validate_traceability_metadata(payload.get("traceability_metadata")))
    return invalid(errors) if errors else valid(payload)


def load_task_pack_seed(path: str | Path) -> ValidationResult:
    """Load the checked-in fixed contract and verify its declared hash."""
    parsed = _read_seed_json(path)
    if _is_parse_failure(parsed):
        return parsed
    if not isinstance(parsed, Mapping):
        return invalid(["task pack seed must be a JSON object"])

    expected_keys = set(TASK_PACK_CONTRACT) | {"contract_hash"}
    errors = exact_keys(parsed, expected_keys, "task pack seed")
    contract = {key: value for key, value in parsed.items() if key != "contract_hash"}
    errors.extend(validate_task_pack_contract(contract))
    errors.extend(sha256_hash(parsed.get("contract_hash"), "contract_hash"))
    if parsed.get("contract_hash") != canonical_json_hash(contract):
        errors.append("contract_hash does not match the fixed task pack contract")
    return invalid(errors) if errors else valid(parsed)


def load_test_case_seed(path: str | Path) -> ValidationResult:
    """Load a non-final or formal Case collection without touching SQLite."""
    parsed = _read_seed_json(path)
    if _is_parse_failure(parsed):
        return parsed
    if not isinstance(parsed, list):
        return invalid(["test case seed must be a JSON list"])

    errors: list[str] = []
    for index, candidate in enumerate(parsed):
        if not isinstance(candidate, Mapping):
            errors.append(f"test case seed[{index}] must be an object")
            continue
        result = parse_test_case_payload(candidate)
        errors.extend(f"test case seed[{index}]: {error}" for error in result["errors"])
        expected_hash = _case_content_hash(candidate)
        if candidate.get("content_hash") != expected_hash:
            errors.append(f"test case seed[{index}]: content_hash does not match Case content")
    return invalid(errors) if errors else valid(parsed)


def load_experiment_assets(path: str | Path) -> ValidationResult:
    """Load reproducible Experiment Asset snapshots without granting approval.

    The checked-in manifest is intentionally a draft. This loader validates
    file structure and hashes only; formal registration additionally requires
    :func:`validate_experiment_assets` to find owner approval for all assets.
    """
    parsed = _read_seed_json(path)
    if _is_parse_failure(parsed):
        return parsed
    if not isinstance(parsed, Mapping):
        return invalid(["experiment asset manifest must be a JSON object"])
    errors = _validate_experiment_asset_structure(parsed)
    return invalid(errors) if errors else valid(parsed)


def validate_experiment_assets(payload: Mapping[str, object]) -> list[str]:
    """Return formal-registration errors for the complete v1 asset set."""
    errors = _validate_experiment_asset_structure(payload)
    assets = payload.get("assets") if isinstance(payload, Mapping) else None
    if not isinstance(assets, list):
        return errors
    for asset in assets:
        if not isinstance(asset, Mapping):
            continue
        asset_type = asset.get("asset_type")
        if not isinstance(asset_type, str) or not asset_type:
            continue
        if asset.get("status") != "approved" or not isinstance(
            asset.get("owner_approved_at"), str
        ) or not str(asset["owner_approved_at"]).strip():
            errors.append(
                f"asset '{asset_type}' must be owner-approved before formal registration"
            )
    return errors


def _validate_traceability_metadata(value: object) -> list[str]:
    if not isinstance(value, Mapping):
        return ["traceability_metadata must be an object"]
    errors = exact_keys(value, _TRACEABILITY_KEYS, "traceability_metadata")
    if value.get("source_of_truth") != "source_material":
        errors.append("traceability_metadata.source_of_truth must be 'source_material'")
    if value.get("source_facts_traceable") is not True:
        errors.append("traceability_metadata.source_facts_traceable must be true")
    return errors


def _validate_experiment_asset_structure(payload: Mapping[str, object]) -> list[str]:
    errors = exact_keys(
        payload, _EXPERIMENT_ASSET_MANIFEST_KEYS, "experiment asset manifest"
    )
    if payload.get("manifest_version") != "1.0":
        errors.append("experiment asset manifest_version must be '1.0'")
    errors.extend(_required_non_empty_values(payload, ("grader_product", "grader_visible_model")))

    assets = payload.get("assets")
    if not isinstance(assets, list):
        return [*errors, "experiment asset manifest.assets must be a list"]

    seen_types: set[str] = set()
    for index, asset in enumerate(assets):
        label = f"experiment asset manifest.assets[{index}]"
        if not isinstance(asset, Mapping):
            errors.append(f"{label} must be an object")
            continue
        errors.extend(exact_keys(asset, _EXPERIMENT_ASSET_KEYS, label))
        errors.extend(non_empty_string(asset.get("asset_type"), f"{label}.asset_type"))
        errors.extend(non_empty_string(asset.get("version_label"), f"{label}.version_label"))
        errors.extend(non_empty_string(asset.get("content"), f"{label}.content"))
        errors.extend(sha256_hash(asset.get("content_hash"), f"{label}.content_hash"))
        asset_type = asset.get("asset_type")
        if isinstance(asset_type, str) and asset_type:
            if asset_type in seen_types:
                errors.append(f"duplicate experiment asset type: {asset_type}")
            seen_types.add(asset_type)
        if asset.get("version_label") != "v1":
            errors.append(f"{label}.version_label must use version_label 'v1'")
        content = asset.get("content")
        if isinstance(content, str) and asset.get("content_hash") != _content_hash(content):
            errors.append(f"{label}.content_hash does not match content")
        status = asset.get("status")
        if status not in {"draft", "approved"}:
            errors.append(f"{label}.status must be 'draft' or 'approved'")
        approved_at = asset.get("owner_approved_at")
        if status == "draft" and approved_at is not None:
            errors.append(f"{label}.owner_approved_at must be null while status is draft")
        if status == "approved" and (
            not isinstance(approved_at, str) or not approved_at.strip()
        ):
            errors.append(
                f"{label}.owner_approved_at must be a non-empty string when status is approved"
            )

    missing_types = _REQUIRED_EXPERIMENT_ASSET_TYPES - seen_types
    extra_types = seen_types - _REQUIRED_EXPERIMENT_ASSET_TYPES
    if missing_types:
        errors.append(
            "experiment asset manifest is missing required asset types: "
            + ", ".join(sorted(missing_types))
        )
    if extra_types:
        errors.append(
            "experiment asset manifest contains unsupported asset types: "
            + ", ".join(sorted(extra_types))
        )
    return errors


def _required_non_empty_values(
    payload: Mapping[str, object], keys: tuple[str, ...]
) -> list[str]:
    errors: list[str] = []
    for key in keys:
        errors.extend(non_empty_string(payload.get(key), key))
    return errors


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _case_content_hash(case: Mapping[str, object]) -> str:
    return canonical_json_hash({key: value for key, value in case.items() if key != "content_hash"})


def _read_seed_json(path: str | Path) -> object:
    try:
        raw_text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return invalid([f"could not read seed file: {exc}"])
    return parse_json_text(raw_text)


def _is_parse_failure(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("ok") is False
        and value.get("value") is None
        and isinstance(value.get("errors"), list)
        and "raw_text" in value
    )
