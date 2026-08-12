from __future__ import annotations

from collections.abc import Mapping, Sequence
import json


_ROOT_KEYS = ("title", "summary", "key_points")


def parse_raw_json_response(raw_response: str) -> tuple[object | None, str | None]:
    """Parse only the trimmed raw response, without any repair or extraction."""
    try:
        return json.loads(raw_response.strip()), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc.msg}"


def run_deterministic_rules(
    raw_response: str,
    contract: Mapping[str, object],
    forbidden_claims: Sequence[str],
) -> dict[str, object]:
    """Evaluate only strict JSON/schema/length/literal-claim rule checks."""
    parsed_value, parse_error = parse_raw_json_response(raw_response)
    rules: list[dict[str, object]] = []

    if parse_error is not None:
        rules.append(
            _rule(
                "json_parse_pass",
                "fail",
                None,
                "JSON object",
                parse_error,
            )
        )
        rules.extend(_not_applicable_field_rules(contract, forbidden_claims, "JSON parsing failed"))
        return {"parsed_value": None, "rule_results": rules}

    if not isinstance(parsed_value, Mapping):
        rules.append(
            _rule(
                "json_parse_pass",
                "fail",
                type(parsed_value).__name__,
                "JSON object",
                "trimmed raw response did not parse as a JSON object",
            )
        )
        rules.extend(
            _not_applicable_field_rules(contract, forbidden_claims, "JSON root is not an object")
        )
        return {"parsed_value": parsed_value, "rule_results": rules}

    rules.append(
        _rule(
            "json_parse_pass",
            "pass",
            "JSON object",
            "JSON object",
            "trimmed raw response parsed directly as a JSON object",
        )
    )
    rules.append(_schema_rule(parsed_value))
    rules.append(_text_length_rule("title", parsed_value.get("title"), contract))
    rules.append(_text_length_rule("summary", parsed_value.get("summary"), contract))
    rules.append(_key_points_count_rule(parsed_value.get("key_points"), contract))
    rules.append(_key_point_lengths_rule(parsed_value.get("key_points"), contract))
    rules.append(_forbidden_claims_rule(parsed_value, forbidden_claims))
    return {"parsed_value": parsed_value, "rule_results": rules}


def _schema_rule(value: Mapping[str, object]) -> dict[str, object]:
    errors: list[str] = []
    if set(value) != set(_ROOT_KEYS) or len(value) != len(_ROOT_KEYS):
        errors.append("root must have exactly title, summary, and key_points")
    if not _non_empty_string(value.get("title")):
        errors.append("title must be a non-empty trimmed string")
    if not _non_empty_string(value.get("summary")):
        errors.append("summary must be a non-empty trimmed string")

    key_points = value.get("key_points")
    if not isinstance(key_points, list):
        errors.append("key_points must be a list")
    else:
        if len(key_points) != 3:
            errors.append("key_points must contain exactly three items")
        if any(not _non_empty_string(item) for item in key_points):
            errors.append("key_points items must be non-empty trimmed strings")

    return _rule(
        "schema_pass",
        "pass" if not errors else "fail",
        sorted(value.keys()),
        list(_ROOT_KEYS),
        "schema is valid" if not errors else "; ".join(errors),
    )


def _text_length_rule(
    field: str, value: object, contract: Mapping[str, object]
) -> dict[str, object]:
    min_length = contract.get(f"{field}_min_chars")
    max_length = contract.get(f"{field}_max_chars")
    expected = {"min_chars": min_length, "max_chars": max_length}
    if not isinstance(value, str):
        return _rule(
            f"{field}_length",
            "not_applicable",
            None,
            expected,
            f"{field} is not a readable string",
        )

    actual = len(value.strip())
    if _within_range(actual, min_length, max_length):
        return _rule(
            f"{field}_length", "pass", actual, expected, f"{field} length is within range"
        )
    return _rule(
        f"{field}_length", "fail", actual, expected, f"{field} length is outside range"
    )


def _key_points_count_rule(
    key_points: object, contract: Mapping[str, object]
) -> dict[str, object]:
    expected = contract.get("key_points_count")
    if not isinstance(key_points, list):
        return _rule(
            "key_points_count",
            "not_applicable",
            None,
            expected,
            "key_points is not a readable list",
        )
    actual = len(key_points)
    return _rule(
        "key_points_count",
        "pass" if actual == expected else "fail",
        actual,
        expected,
        "key_points count is valid" if actual == expected else "key_points count is invalid",
    )


def _key_point_lengths_rule(
    key_points: object, contract: Mapping[str, object]
) -> dict[str, object]:
    min_length = contract.get("key_point_min_chars")
    max_length = contract.get("key_point_max_chars")
    expected = {"min_chars": min_length, "max_chars": max_length}
    if not isinstance(key_points, list):
        return _rule(
            "key_point_lengths",
            "not_applicable",
            None,
            expected,
            "key_points is not a readable list",
        )
    if any(not isinstance(item, str) for item in key_points):
        return _rule(
            "key_point_lengths",
            "fail",
            [len(item.strip()) if isinstance(item, str) else None for item in key_points],
            expected,
            "key_points contains a non-string item",
        )

    actual = [len(item.strip()) for item in key_points]
    status = "pass" if all(_within_range(length, min_length, max_length) for length in actual) else "fail"
    return _rule(
        "key_point_lengths",
        status,
        actual,
        expected,
        "key point lengths are within range" if status == "pass" else "a key point length is outside range",
    )


def _forbidden_claims_rule(
    value: Mapping[str, object], forbidden_claims: Sequence[str]
) -> dict[str, object]:
    readable_parts: list[str] = []
    for field in ("title", "summary"):
        field_value = value.get(field)
        if isinstance(field_value, str):
            readable_parts.append(field_value)

    key_points = value.get("key_points")
    if isinstance(key_points, list):
        readable_parts.extend(item for item in key_points if isinstance(item, str))

    expected = list(forbidden_claims)
    if not readable_parts:
        return _rule(
            "forbidden_claims",
            "not_applicable",
            None,
            expected,
            "no response text fields are reliably readable",
        )

    response_text = "\n".join(readable_parts)
    actual = [claim for claim in forbidden_claims if isinstance(claim, str) and claim in response_text]
    return _rule(
        "forbidden_claims",
        "fail" if actual else "pass",
        actual,
        expected,
        "literal forbidden claim found" if actual else "no literal forbidden claim found",
    )


def _not_applicable_field_rules(
    contract: Mapping[str, object], forbidden_claims: Sequence[str], reason: str
) -> list[dict[str, object]]:
    return [
        _rule("schema_pass", "not_applicable", None, list(_ROOT_KEYS), reason),
        _rule(
            "title_length",
            "not_applicable",
            None,
            {
                "min_chars": contract.get("title_min_chars"),
                "max_chars": contract.get("title_max_chars"),
            },
            reason,
        ),
        _rule(
            "summary_length",
            "not_applicable",
            None,
            {
                "min_chars": contract.get("summary_min_chars"),
                "max_chars": contract.get("summary_max_chars"),
            },
            reason,
        ),
        _rule(
            "key_points_count",
            "not_applicable",
            None,
            contract.get("key_points_count"),
            reason,
        ),
        _rule(
            "key_point_lengths",
            "not_applicable",
            None,
            {
                "min_chars": contract.get("key_point_min_chars"),
                "max_chars": contract.get("key_point_max_chars"),
            },
            reason,
        ),
        _rule("forbidden_claims", "not_applicable", None, list(forbidden_claims), reason),
    ]


def _within_range(value: int, minimum: object, maximum: object) -> bool:
    return (
        isinstance(minimum, int)
        and not isinstance(minimum, bool)
        and isinstance(maximum, int)
        and not isinstance(maximum, bool)
        and minimum <= value <= maximum
    )


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _rule(
    rule_key: str,
    status: str,
    actual: object,
    expected: object,
    reason: str,
) -> dict[str, object]:
    return {
        "rule_key": rule_key,
        "status": status,
        "actual": actual,
        "expected": expected,
        "reason": reason,
    }
