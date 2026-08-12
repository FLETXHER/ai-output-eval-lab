from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json


TASK_PACK_KEY: str = "grounded_structured_brief_generation"
CONTRACT_VERSION: str = "1.0"
TASK_PACK_CONTRACT: dict[str, object] = {
    "pack_key": TASK_PACK_KEY,
    "contract_version": CONTRACT_VERSION,
    "language": "zh-CN",
    "root_keys": ["title", "summary", "key_points"],
    "title_min_chars": 4,
    "title_max_chars": 20,
    "summary_min_chars": 60,
    "summary_max_chars": 120,
    "key_points_count": 3,
    "key_point_min_chars": 6,
    "key_point_max_chars": 40,
}


def canonical_json_hash(value: object) -> str:
    """Return the SHA-256 hash for canonical UTF-8 JSON."""
    canonical_json = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def validate_task_pack_contract(pack: Mapping[str, object]) -> list[str]:
    """Validate that metadata still represents the one approved Task Pack."""
    errors: list[str] = []
    for key, expected in TASK_PACK_CONTRACT.items():
        if pack.get(key) != expected:
            errors.append(f"{key} must be {expected!r}")

    extra_keys = set(pack) - set(TASK_PACK_CONTRACT)
    if extra_keys:
        errors.append("contract contains unsupported keys")
    return errors


def validate_case_record(case: Mapping[str, object]) -> list[str]:
    """Check deterministic case metadata without judging semantic feasibility."""
    errors: list[str] = []

    if not _non_empty_string(case.get("case_key")):
        errors.append("case_key must be a non-empty string")
    if not _positive_int(case.get("revision")):
        errors.append("revision must be a positive integer")

    split = case.get("split")
    if split not in {"dev", "holdout"}:
        errors.append("split must be 'dev' or 'holdout'")

    source_material = case.get("source_material")
    if not _non_empty_string(source_material):
        errors.append("source_material must be a non-empty string")
        source_text: str | None = None
    else:
        source_text = source_material

    fact_ids = _validate_source_facts(case.get("source_facts"), source_text, errors)
    _validate_required_fact_ids(case.get("required_fact_ids"), fact_ids, errors)
    _validate_forbidden_claims(case.get("explicit_forbidden_claims"), errors)

    feasibility_status = case.get("feasibility_qa_status")
    if feasibility_status not in {"pending", "pass", "fail"}:
        errors.append("feasibility_qa_status must be 'pending', 'pass', or 'fail'")

    return errors


def _validate_source_facts(
    source_facts: object, source_text: str | None, errors: list[str]
) -> set[str]:
    if not isinstance(source_facts, list):
        errors.append("source_facts must be a list")
        return set()

    fact_ids: list[str] = []
    for index, fact in enumerate(source_facts):
        if not isinstance(fact, Mapping):
            errors.append(f"source_facts[{index}] must be an object")
            continue

        fact_id = fact.get("fact_id")
        if not _non_empty_string(fact_id):
            errors.append(f"source_facts[{index}].fact_id must be a non-empty string")
        else:
            fact_ids.append(fact_id.strip())

        text = fact.get("text")
        if not _non_empty_string(text):
            errors.append(f"source_facts[{index}].text must be a non-empty string")
        elif source_text is not None and text.strip() not in source_text:
            errors.append(f"source_facts[{index}].text must appear in source_material")

    if len(fact_ids) != len(set(fact_ids)):
        errors.append("source_facts fact_id values must be unique")
    return set(fact_ids)


def _validate_required_fact_ids(
    required_fact_ids: object, source_fact_ids: set[str], errors: list[str]
) -> None:
    if not isinstance(required_fact_ids, list):
        errors.append("required_fact_ids must be a list")
        return

    normalized_ids: list[str] = []
    for index, fact_id in enumerate(required_fact_ids):
        if not _non_empty_string(fact_id):
            errors.append(f"required_fact_ids[{index}] must be a non-empty string")
        else:
            normalized_ids.append(fact_id.strip())

    if len(normalized_ids) != len(set(normalized_ids)):
        errors.append("required_fact_ids must not contain duplicates")
    if not set(normalized_ids).issubset(source_fact_ids):
        errors.append("required_fact_ids must be a subset of source_facts fact_id values")


def _validate_forbidden_claims(forbidden_claims: object, errors: list[str]) -> None:
    if not isinstance(forbidden_claims, list):
        errors.append("explicit_forbidden_claims must be a list")
        return
    if any(not _non_empty_string(claim) for claim in forbidden_claims):
        errors.append("explicit_forbidden_claims must contain non-empty strings")


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
