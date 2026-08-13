from __future__ import annotations

import pytest

from eval_lab.domain.grader_contract import (
    normalize_grader_payload,
    validate_grader_payload,
)


def valid_payload() -> dict[str, object]:
    return {
        "language_compliance": {
            "label": "pass",
            "reason": "The response is in the requested language.",
            "evidence": "All visible response fields are Chinese.",
        },
        "required_facts": [
            {
                "fact_id": "F01",
                "label": "met",
                "output_evidence": "The launch date is September 9.",
                "reason": "The required date appears in the output.",
            },
            {
                "fact_id": "F02",
                "label": "met",
                "output_evidence": "The location is stated.",
                "reason": "The required location appears in the output.",
            },
        ],
        "unsupported_claims": [],
        "readability": {
            "label": "pass",
            "reason": "The response is easy to scan.",
            "evidence": "Short paragraphs and complete sentences.",
        },
        "primary_error_type": None,
        "secondary_error_types": [],
        "grader_reason": "The response follows the semantic checks.",
    }


def test_normalizes_a_valid_allowlisted_payload_into_a_new_mapping() -> None:
    payload = valid_payload()
    payload["grader_reason"] = "  The response follows the semantic checks.  "

    normalized = normalize_grader_payload(payload, ["F01", "F02"])

    assert normalized == valid_payload()
    assert normalized is not payload
    assert normalized["language_compliance"] is not payload["language_compliance"]


def test_rejects_missing_and_duplicate_required_fact_ids() -> None:
    missing = valid_payload()
    missing["required_facts"] = [missing["required_facts"][0]]
    duplicate = valid_payload()
    duplicate["required_facts"] = [
        duplicate["required_facts"][0],
        duplicate["required_facts"][0],
    ]

    assert any("exactly once" in error for error in validate_grader_payload(missing, ["F01", "F02"]))
    assert any("duplicates" in error for error in validate_grader_payload(duplicate, ["F01", "F02"]))


def test_rejects_invalid_labels_and_unsupported_fact_ids() -> None:
    payload = valid_payload()
    payload["language_compliance"]["label"] = "approved"  # type: ignore[index]
    payload["required_facts"][1]["fact_id"] = "F03"  # type: ignore[index]

    errors = validate_grader_payload(payload, ["F01", "F02"])

    assert any("language_compliance.label" in error for error in errors)
    assert any("unsupported fact_id" in error for error in errors)


def test_met_requires_evidence_but_not_met_and_indeterminate_may_be_empty() -> None:
    payload = valid_payload()
    payload["required_facts"][0]["output_evidence"] = " "  # type: ignore[index]
    payload["required_facts"][1] = {
        "fact_id": "F02",
        "label": "indeterminate",
        "output_evidence": " ",
        "reason": "Evidence is ambiguous.",
    }

    errors = validate_grader_payload(payload, ["F01", "F02"])

    assert any("required_facts[0].output_evidence" in error for error in errors)
    assert not any("required_facts[1].output_evidence" in error for error in errors)

    payload["required_facts"][1]["reason"] = " "  # type: ignore[index]
    assert any("required_facts[1].reason" in error for error in validate_grader_payload(payload, ["F01", "F02"]))


def test_rejects_malformed_unsupported_claims_and_blind_metadata() -> None:
    malformed = valid_payload()
    malformed["unsupported_claims"] = [
        {
            "claim": "Market leader",
            "output_evidence": "We are the market leader.",
            "supporting_fact_ids": "F01",
            "reason": "No support was supplied.",
        }
    ]
    blind_metadata = valid_payload()
    blind_metadata["prompt_version"] = "v2"

    assert any(
        "supporting_fact_ids" in error
        for error in validate_grader_payload(malformed, ["F01", "F02"])
    )
    assert any("unsupported keys" in error for error in validate_grader_payload(blind_metadata, ["F01", "F02"]))
    with pytest.raises(ValueError):
        normalize_grader_payload(blind_metadata, ["F01", "F02"])


def test_rejects_unsupported_claim_supporting_fact_ids() -> None:
    payload = valid_payload()
    payload["unsupported_claims"] = [
        {
            "claim": "Market leader",
            "output_evidence": "We are the market leader.",
            "supporting_fact_ids": ["UNKNOWN"],
            "reason": "The claim needs source support.",
        }
    ]

    errors = validate_grader_payload(payload, ["F01", "F02"])

    assert any("unsupported supporting_fact_id 'UNKNOWN'" in error for error in errors)


def test_unsupported_claims_may_reference_any_source_fact_not_only_required_facts() -> None:
    payload = valid_payload()
    payload["unsupported_claims"] = [
        {
            "claim": "The package includes a cable.",
            "output_evidence": "包装包含数据线。",
            "supporting_fact_ids": ["F03"],
            "reason": "F03 was checked but does not support the claim.",
        }
    ]
    payload["primary_error_type"] = "unsupported_claim"

    assert validate_grader_payload(payload, ["F01", "F02"], ["F01", "F02", "F03"]) == []
    unknown = payload.copy()
    unknown["unsupported_claims"] = [dict(payload["unsupported_claims"][0], supporting_fact_ids=["F99"])]  # type: ignore[index]
    assert any(
        "unsupported supporting_fact_id 'F99'" in error
        for error in validate_grader_payload(unknown, ["F01", "F02"], ["F01", "F02", "F03"])
    )


def test_readability_label_is_a_three_state_diagnostic() -> None:
    payload = valid_payload()
    payload["readability"]["label"] = "good"  # type: ignore[index]
    assert any("readability.label" in error for error in validate_grader_payload(payload, ["F01", "F02"]))


def test_taxonomy_uses_fixed_priority_and_all_remaining_diagnostics_as_secondary() -> None:
    payload = valid_payload()
    payload["required_facts"][0]["label"] = "not_met"  # type: ignore[index]
    payload["required_facts"][0]["output_evidence"] = ""  # type: ignore[index]
    payload["unsupported_claims"] = [
        {
            "claim": "Unsupported claim.",
            "output_evidence": "输出证据。",
            "supporting_fact_ids": [],
            "reason": "Source does not support it.",
        }
    ]
    payload["language_compliance"]["label"] = "fail"  # type: ignore[index]
    payload["readability"]["label"] = "fail"  # type: ignore[index]
    payload["primary_error_type"] = "unsupported_claim"
    payload["secondary_error_types"] = [
        "required_fact_missing",
        "language_noncompliance",
        "readability_issue",
    ]
    assert validate_grader_payload(payload, ["F01", "F02"]) == []

    payload["secondary_error_types"] = ["required_fact_missing"]
    assert any(
        "every other detected diagnostic" in error
        for error in validate_grader_payload(payload, ["F01", "F02"])
    )


def test_taxonomy_rejects_arbitrary_duplicate_or_primary_secondary_values() -> None:
    payload = valid_payload()
    payload["readability"]["label"] = "fail"  # type: ignore[index]
    payload["primary_error_type"] = "readability_issue"
    payload["secondary_error_types"] = ["readability_issue", "readability_issue"]
    errors = validate_grader_payload(payload, ["F01", "F02"])
    assert any("duplicates" in error for error in errors)
    assert any("must not contain primary_error_type" in error for error in errors)


def test_language_hard_criterion_requires_complete_evidence() -> None:
    payload = valid_payload()
    payload["language_compliance"] = {
        "label": "fail",
        "reason": "The output switches languages.",
        "evidence": "The summary contains English sentences.",
    }
    payload["primary_error_type"] = "language_noncompliance"

    assert validate_grader_payload(payload, ["F01", "F02"]) == []

    payload["language_compliance"]["evidence"] = " "  # type: ignore[index]
    assert any(
        "language_compliance.evidence" in error
        for error in validate_grader_payload(payload, ["F01", "F02"])
    )
