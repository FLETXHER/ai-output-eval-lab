from __future__ import annotations

from eval_lab.domain.status import aggregate_calculated_status


def valid_grader(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "language_compliance": {
            "label": "pass",
            "reason": "Requested language is used.",
            "evidence": "All response text is Chinese.",
        },
        "required_facts": [
            {
                "fact_id": "F01",
                "label": "met",
                "output_evidence": "The date is stated.",
                "reason": "The output names the required date.",
            }
        ],
        "unsupported_claims": [],
        "readability": {
            "label": "pass",
            "reason": "The text is readable.",
            "evidence": "It has complete sentences.",
        },
        "primary_error_type": None,
        "secondary_error_types": [],
        "grader_reason": "All semantic checks pass.",
    }
    result.update(overrides)
    return result


def test_schema_failure_wins_over_indeterminate_grader() -> None:
    result = aggregate_calculated_status(
        [{"rule_key": "schema_pass", "status": "fail", "reason": "extra field"}],
        {"language_compliance": {"label": "indeterminate"}, "required_facts": []},
        ["F01"],
    )
    assert result["calculated_status"] == "fail"


def test_missing_grader_is_indeterminate_without_hard_failure() -> None:
    result = aggregate_calculated_status(
        [{"rule_key": "schema_pass", "status": "pass"}], None, ["F01"]
    )
    assert result["calculated_status"] == "indeterminate"


def test_semantic_failures_override_passing_deterministic_rules() -> None:
    grader = valid_grader(
        unsupported_claims=[
            {
                "claim": "Market leader",
                "output_evidence": "We are the market leader.",
                "supporting_fact_ids": [],
                "reason": "The source facts do not support this claim.",
            }
        ],
        primary_error_type="unsupported_claim",
    )

    result = aggregate_calculated_status(
        [{"rule_key": "schema_pass", "status": "pass"}], grader, ["F01"]
    )

    assert result["calculated_status"] == "fail"
    assert result["aggregation_rule_version"] == "1.0"
    assert result["blocking_reasons"] == ["unsupported claims detected"]


def test_language_indeterminate_keeps_result_indeterminate() -> None:
    grader = valid_grader(
        language_compliance={
            "label": "indeterminate",
            "reason": "Language cannot be reliably determined.",
            "evidence": "The response contains too little readable text.",
        },
        primary_error_type="ambiguous_evidence",
    )

    result = aggregate_calculated_status(
        [{"rule_key": "schema_pass", "status": "pass"}], grader, ["F01"]
    )

    assert result["calculated_status"] == "indeterminate"
    assert result["blocking_reasons"] == ["language compliance is indeterminate"]


def test_valid_language_failure_fails_calculated_status() -> None:
    result = aggregate_calculated_status(
        [{"rule_key": "schema_pass", "status": "pass"}],
        valid_grader(
            language_compliance={
                "label": "fail",
                "reason": "The output switches languages.",
                "evidence": "The summary contains English sentences.",
            },
            primary_error_type="language_noncompliance",
        ),
        ["F01"],
    )

    assert result["calculated_status"] == "fail"


def test_valid_missing_required_fact_fails_calculated_status() -> None:
    result = aggregate_calculated_status(
        [{"rule_key": "schema_pass", "status": "pass"}],
        valid_grader(
            required_facts=[
                {
                    "fact_id": "F01",
                    "label": "not_met",
                    "output_evidence": "Evidence was not found in the output.",
                    "reason": "The date is absent.",
                }
            ],
            primary_error_type="required_fact_missing",
        ),
        ["F01"],
    )

    assert result["calculated_status"] == "fail"


def test_valid_indeterminate_required_fact_keeps_status_indeterminate() -> None:
    result = aggregate_calculated_status(
        [{"rule_key": "schema_pass", "status": "pass"}],
        valid_grader(
            required_facts=[
                {
                    "fact_id": "F01",
                    "label": "indeterminate",
                    "output_evidence": "Evidence was not found in the output.",
                    "reason": "The output cannot be reliably read.",
                }
            ],
            primary_error_type="ambiguous_evidence",
        ),
        ["F01"],
    )

    assert result["calculated_status"] == "indeterminate"


def test_valid_diagnostics_do_not_affect_passing_status() -> None:
    result = aggregate_calculated_status(
        [{"rule_key": "schema_pass", "status": "pass"}],
        valid_grader(
            readability={
                "label": "fail",
                "reason": "Dense text.",
                "evidence": "The summary is one long paragraph.",
            },
            primary_error_type="readability_issue",
            secondary_error_types=[],
        ),
        ["F01"],
    )

    assert result["calculated_status"] == "pass"


def test_invalid_grader_payload_is_indeterminate_and_diagnostics_do_not_change_status() -> None:
    grader = valid_grader(
        required_facts=[],
        readability={
            "label": "fail",
            "reason": "Dense text.",
            "evidence": "Long paragraph.",
        },
        primary_error_type="readability_issue",
        secondary_error_types=[],
    )

    result = aggregate_calculated_status(
        [{"rule_key": "schema_pass", "status": "pass"}], grader, ["F01"]
    )

    assert result["calculated_status"] == "indeterminate"
    assert result["blocking_reasons"] == ["invalid grader payload"]


def test_all_hard_criteria_and_valid_semantics_pass() -> None:
    result = aggregate_calculated_status(
        [{"rule_key": "schema_pass", "status": "pass"}], valid_grader(), ["F01"], "2.0"
    )

    assert result == {
        "calculated_status": "pass",
        "aggregation_rule_version": "2.0",
        "blocking_reasons": [],
    }
