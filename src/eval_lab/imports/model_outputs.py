from __future__ import annotations

from collections.abc import Mapping

from eval_lab.imports import ValidationResult, exact_keys, invalid, non_empty_string, sha256_hash, valid


_MODEL_OUTPUT_KEYS = {
    "generation_packet_version",
    "generation_packet_hash",
    "raw_response",
    "generated_at",
}


def parse_model_output_payload(payload: Mapping[str, object]) -> ValidationResult:
    """Validate manual model-output evidence while preserving raw response bytes."""
    if not isinstance(payload, Mapping):
        return invalid(["model output payload must be an object"])

    errors = exact_keys(payload, _MODEL_OUTPUT_KEYS, "model output payload")
    errors.extend(non_empty_string(payload.get("generation_packet_version"), "generation_packet_version"))
    errors.extend(sha256_hash(payload.get("generation_packet_hash"), "generation_packet_hash"))
    if not isinstance(payload.get("raw_response"), str):
        errors.append("raw_response must be a string")
    errors.extend(non_empty_string(payload.get("generated_at"), "generated_at"))
    return invalid(errors) if errors else valid(payload)
