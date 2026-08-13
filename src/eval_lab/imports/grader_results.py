from __future__ import annotations

from collections.abc import Mapping, Sequence

from eval_lab.domain.grader_contract import validate_grader_payload
from eval_lab.imports import (
    ValidationResult,
    exact_keys,
    invalid,
    parse_json_text,
    valid,
)


_GRADER_FIELDS = {
    "language_compliance",
    "required_facts",
    "unsupported_claims",
    "readability",
    "primary_error_type",
    "secondary_error_types",
    "grader_reason",
}
_FORBIDDEN_BLIND_METADATA = {
    "prompt_version",
    "prompt_version_id",
    "split",
    "generator_product",
    "generator_model",
    "generator_visible_model",
    "evaluation_run",
    "evaluation_run_id",
    "comparison_group_id",
    "calculated_status",
    "human_review",
    "previous_grader_result",
    "analysis_conclusion",
}


def parse_grader_payload(
    payload: Mapping[str, object],
    required_fact_ids: Sequence[str],
    source_fact_ids: Sequence[str] | None = None,
) -> ValidationResult:
    """Validate a blind Grader submission without importing experiment identity."""
    if not isinstance(payload, Mapping):
        return invalid(["grader payload must be an object"])

    errors = exact_keys(payload, _GRADER_FIELDS, "grader payload")
    if _FORBIDDEN_BLIND_METADATA & set(payload):
        errors.append("grader payload contains forbidden blind metadata")
    errors.extend(validate_grader_payload(payload, required_fact_ids, source_fact_ids))
    return invalid(errors) if errors else valid(payload)


def parse_grader_payload_text(
    raw_text: str,
    required_fact_ids: Sequence[str],
    source_fact_ids: Sequence[str] | None = None,
) -> ValidationResult:
    """Strictly parse external Grader text before validating its required schema."""
    parsed = parse_json_text(raw_text)
    if isinstance(parsed, Mapping) and parsed.get("ok") is False and "errors" in parsed:
        errors = parsed.get("errors")
        return invalid(list(errors) if isinstance(errors, list) else ["invalid JSON"])
    if not isinstance(parsed, Mapping):
        return invalid(["grader payload must be an object"])
    return parse_grader_payload(parsed, required_fact_ids, source_fact_ids)
