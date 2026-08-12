from __future__ import annotations

from collections.abc import Mapping, Sequence

from eval_lab.domain.grader_contract import validate_grader_payload


def aggregate_calculated_status(
    rule_results: Sequence[Mapping[str, object]],
    grader_result: Mapping[str, object] | None,
    required_fact_ids: Sequence[str],
    aggregation_rule_version: str = "1.0",
) -> dict[str, object]:
    """Combine automatic evidence only; Human Review never participates."""
    hard_failures = _hard_failure_reasons(rule_results)
    if hard_failures:
        return _result("fail", aggregation_rule_version, hard_failures)

    if grader_result is None:
        return _result("indeterminate", aggregation_rule_version, ["grader result is missing"])

    if validate_grader_payload(grader_result, required_fact_ids):
        return _result("indeterminate", aggregation_rule_version, ["invalid grader payload"])

    semantic_failures = _semantic_failure_reasons(grader_result)
    if semantic_failures:
        return _result("fail", aggregation_rule_version, semantic_failures)

    semantic_indeterminates = _semantic_indeterminate_reasons(grader_result)
    if semantic_indeterminates:
        return _result("indeterminate", aggregation_rule_version, semantic_indeterminates)

    if not _all_rules_pass(rule_results):
        return _result(
            "indeterminate", aggregation_rule_version, ["deterministic rule evidence is incomplete"]
        )
    return _result("pass", aggregation_rule_version, [])


def _hard_failure_reasons(rule_results: Sequence[Mapping[str, object]]) -> list[str]:
    reasons: list[str] = []
    for rule in rule_results:
        if rule.get("status") == "fail":
            rule_key = rule.get("rule_key")
            reason = rule.get("reason")
            if isinstance(rule_key, str) and rule_key.strip():
                reasons.append(f"deterministic rule failed: {rule_key.strip()}")
            elif isinstance(reason, str) and reason.strip():
                reasons.append(f"deterministic rule failed: {reason.strip()}")
            else:
                reasons.append("deterministic rule failed")
    return reasons


def _semantic_failure_reasons(grader_result: Mapping[str, object]) -> list[str]:
    reasons: list[str] = []
    language = grader_result["language_compliance"]
    facts = grader_result["required_facts"]
    claims = grader_result["unsupported_claims"]
    if isinstance(language, Mapping) and language.get("label") == "fail":
        reasons.append("language compliance failed")
    if isinstance(facts, list) and any(
        isinstance(fact, Mapping) and fact.get("label") == "not_met" for fact in facts
    ):
        reasons.append("required fact is not met")
    if isinstance(claims, list) and claims:
        reasons.append("unsupported claims detected")
    return reasons


def _semantic_indeterminate_reasons(grader_result: Mapping[str, object]) -> list[str]:
    reasons: list[str] = []
    language = grader_result["language_compliance"]
    facts = grader_result["required_facts"]
    if isinstance(language, Mapping) and language.get("label") == "indeterminate":
        reasons.append("language compliance is indeterminate")
    if isinstance(facts, list) and any(
        isinstance(fact, Mapping) and fact.get("label") == "indeterminate" for fact in facts
    ):
        reasons.append("required fact is indeterminate")
    return reasons


def _all_rules_pass(rule_results: Sequence[Mapping[str, object]]) -> bool:
    return bool(rule_results) and all(rule.get("status") == "pass" for rule in rule_results)


def _result(status: str, version: str, reasons: list[str]) -> dict[str, object]:
    return {
        "calculated_status": status,
        "aggregation_rule_version": version,
        "blocking_reasons": reasons,
    }
