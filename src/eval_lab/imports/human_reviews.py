from __future__ import annotations

from collections.abc import Mapping

from eval_lab.imports import ValidationResult, exact_keys, invalid, non_empty_string, valid


_HUMAN_REVIEW_KEYS = {
    "review_scope",
    "blind_review",
    "evidence",
    "reason",
    "final_decision",
    "reviewed_at",
}
_REVIEW_SCOPES = {"required", "sampled", "manual"}
_FINAL_DECISIONS = {"pass", "fail", "indeterminate"}


def parse_human_review_payload(payload: Mapping[str, object]) -> ValidationResult:
    """Validate a submitted Human Review without automatic-result metadata."""
    if not isinstance(payload, Mapping):
        return invalid(["human review payload must be an object"])

    errors = exact_keys(payload, _HUMAN_REVIEW_KEYS, "human review payload")
    if payload.get("review_scope") not in _REVIEW_SCOPES:
        errors.append("review_scope must be required, sampled, or manual")
    if not isinstance(payload.get("blind_review"), bool):
        errors.append("blind_review must be a boolean")
    evidence = payload.get("evidence")
    if not isinstance(evidence, (str, list, dict)):
        errors.append("evidence must be a JSON string, object, or array")
    errors.extend(non_empty_string(payload.get("reason"), "reason"))
    if payload.get("final_decision") not in _FINAL_DECISIONS:
        errors.append("final_decision must be pass, fail, or indeterminate")
    errors.extend(non_empty_string(payload.get("reviewed_at"), "reviewed_at"))
    return invalid(errors) if errors else valid(payload)
