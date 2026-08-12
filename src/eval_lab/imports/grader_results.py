from __future__ import annotations

from collections.abc import Mapping, Sequence

from eval_lab.domain.grader_contract import validate_grader_payload
from eval_lab.imports import ValidationResult, exact_keys, invalid, non_empty_string, sha256_hash, valid


_GRADER_FIELDS = {
    "blind_packet_version",
    "blind_packet_hash",
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
    payload: Mapping[str, object], required_fact_ids: Sequence[str]
) -> ValidationResult:
    """Validate a blind Grader submission without importing experiment identity."""
    if not isinstance(payload, Mapping):
        return invalid(["grader payload must be an object"])

    errors = exact_keys(payload, _GRADER_FIELDS, "grader payload")
    if _FORBIDDEN_BLIND_METADATA & set(payload):
        errors.append("grader payload contains forbidden blind metadata")
    errors.extend(non_empty_string(payload.get("blind_packet_version"), "blind_packet_version"))
    errors.extend(sha256_hash(payload.get("blind_packet_hash"), "blind_packet_hash"))

    semantic_payload = {
        key: value for key, value in payload.items() if key not in {"blind_packet_version", "blind_packet_hash"}
    }
    errors.extend(validate_grader_payload(semantic_payload, required_fact_ids))
    return invalid(errors) if errors else valid(payload)
