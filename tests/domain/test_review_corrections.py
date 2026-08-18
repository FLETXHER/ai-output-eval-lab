from __future__ import annotations

import pytest

from eval_lab.domain.review_corrections import (
    CORRECTIVE_RE_REVIEW,
    effective_final_decision,
    validate_correction_payload,
)


def test_correction_payload_requires_a_valid_decision_and_nonempty_provenance() -> None:
    validate_correction_payload(
        correction_reason="renderer procedure was invalid",
        reviewer_evidence={"raw_root": "object"},
        reviewer_reason="The stored response parses as an object.",
        corrected_final_decision="pass",
        review_mode=CORRECTIVE_RE_REVIEW,
    )

    with pytest.raises(ValueError, match="corrected_final_decision"):
        validate_correction_payload(
            correction_reason="renderer procedure was invalid",
            reviewer_evidence={"raw_root": "object"},
            reviewer_reason="The stored response parses as an object.",
            corrected_final_decision="maybe",
            review_mode=CORRECTIVE_RE_REVIEW,
        )

    with pytest.raises(ValueError, match="correction_reason"):
        validate_correction_payload(
            correction_reason=" ",
            reviewer_evidence={"raw_root": "object"},
            reviewer_reason="The stored response parses as an object.",
            corrected_final_decision="pass",
            review_mode=CORRECTIVE_RE_REVIEW,
        )


def test_correction_payload_requires_json_evidence_and_reason() -> None:
    with pytest.raises(ValueError, match="reviewer_evidence"):
        validate_correction_payload(
            correction_reason="renderer procedure was invalid",
            reviewer_evidence=object(),
            reviewer_reason="The stored response parses as an object.",
            corrected_final_decision="pass",
            review_mode=CORRECTIVE_RE_REVIEW,
        )

    with pytest.raises(ValueError, match="reviewer_reason"):
        validate_correction_payload(
            correction_reason="renderer procedure was invalid",
            reviewer_evidence={"raw_root": "object"},
            reviewer_reason=" ",
            corrected_final_decision="pass",
            review_mode=CORRECTIVE_RE_REVIEW,
        )

    with pytest.raises(ValueError, match="reviewer_evidence"):
        validate_correction_payload(
            correction_reason="renderer procedure was invalid",
            reviewer_evidence={"evidence": " "},
            reviewer_reason="The stored response parses as an object.",
            corrected_final_decision="pass",
            review_mode=CORRECTIVE_RE_REVIEW,
        )


def test_effective_decision_prefers_a_correction_and_preserves_original_without_one() -> None:
    assert effective_final_decision("fail", "pass") == "pass"
    assert effective_final_decision("fail", None) == "fail"
    assert effective_final_decision(None, None) is None
