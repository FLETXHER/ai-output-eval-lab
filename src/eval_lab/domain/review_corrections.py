from __future__ import annotations

from collections.abc import Mapping, Sequence
import json


CORRECTIVE_RE_REVIEW = "corrective-re-review"
CORRECTED_FINAL_DECISIONS = frozenset({"pass", "fail", "indeterminate"})


def validate_correction_payload(
    *,
    correction_reason: object,
    reviewer_evidence: object,
    reviewer_reason: object,
    corrected_final_decision: object,
    review_mode: object,
) -> None:
    """Validate the immutable, append-only correction payload."""
    if not isinstance(correction_reason, str) or not correction_reason.strip():
        raise ValueError("correction_reason must be a non-empty string")
    if not isinstance(reviewer_reason, str) or not reviewer_reason.strip():
        raise ValueError("reviewer_reason must be a non-empty string")
    if review_mode != CORRECTIVE_RE_REVIEW:
        raise ValueError("review_mode must be corrective-re-review")
    if (
        not isinstance(corrected_final_decision, str)
        or corrected_final_decision not in CORRECTED_FINAL_DECISIONS
    ):
        raise ValueError(
            "corrected_final_decision must be pass, fail, or indeterminate"
        )
    if reviewer_evidence is None:
        raise ValueError("reviewer_evidence must be JSON-serializable evidence")
    try:
        json.dumps(reviewer_evidence, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("reviewer_evidence must be JSON-serializable evidence") from exc
    if _is_empty_evidence(reviewer_evidence):
        raise ValueError("reviewer_evidence must be JSON-serializable evidence")


def _is_empty_evidence(value: object) -> bool:
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, Mapping):
        return not value or all(_is_empty_evidence(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return not value or all(_is_empty_evidence(item) for item in value)
    return False


def effective_final_decision(
    original_final_decision: str | None,
    corrected_final_decision: str | None,
) -> str | None:
    """Return the effective human decision without changing the original layer."""
    if corrected_final_decision is not None:
        if (
            not isinstance(corrected_final_decision, str)
            or corrected_final_decision not in CORRECTED_FINAL_DECISIONS
        ):
            raise ValueError("corrected_final_decision must be pass, fail, or indeterminate")
        return corrected_final_decision
    return original_final_decision
