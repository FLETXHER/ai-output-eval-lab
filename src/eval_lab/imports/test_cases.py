from __future__ import annotations

from collections.abc import Mapping

from eval_lab.domain.task_pack import validate_case_record, validate_task_pack_contract
from eval_lab.imports import ValidationResult, exact_keys, invalid, parse_json_text, valid


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
    return invalid(errors) if errors else valid(payload)
