from __future__ import annotations

from collections.abc import Mapping, Sequence


_ROOT_KEYS = {
    "language_compliance",
    "required_facts",
    "unsupported_claims",
    "readability",
    "primary_error_type",
    "secondary_error_types",
    "grader_reason",
}
_LANGUAGE_LABELS = {"pass", "fail", "indeterminate"}
_FACT_LABELS = {"met", "not_met", "indeterminate"}
_READABILITY_LABELS = {"pass", "fail", "indeterminate"}
_ERROR_TYPES = {
    "unsupported_claim",
    "required_fact_missing",
    "language_noncompliance",
    "ambiguous_evidence",
    "readability_issue",
    "other",
}
_ERROR_PRIORITY = (
    "unsupported_claim",
    "required_fact_missing",
    "language_noncompliance",
    "ambiguous_evidence",
    "readability_issue",
    "other",
)


def normalize_grader_payload(
    payload: Mapping[str, object],
    required_fact_ids: Sequence[str],
    source_fact_ids: Sequence[str] | None = None,
) -> dict[str, object]:
    """Validate and copy a Grader result into the allowlisted Domain contract."""
    errors = validate_grader_payload(payload, required_fact_ids, source_fact_ids)
    if errors:
        raise ValueError("invalid grader payload: " + "; ".join(errors))

    language = payload["language_compliance"]
    readability = payload["readability"]
    required_facts = payload["required_facts"]
    unsupported_claims = payload["unsupported_claims"]
    secondary_error_types = payload["secondary_error_types"]

    return {
        "language_compliance": _normalize_diagnostic(language),
        "required_facts": [
            {
                "fact_id": fact["fact_id"].strip(),
                "label": fact["label"],
                "output_evidence": fact["output_evidence"].strip(),
                "reason": fact["reason"].strip(),
            }
            for fact in required_facts
        ],
        "unsupported_claims": [
            {
                "claim": claim["claim"].strip(),
                "output_evidence": claim["output_evidence"].strip(),
                "supporting_fact_ids": [fact_id.strip() for fact_id in claim["supporting_fact_ids"]],
                "reason": claim["reason"].strip(),
            }
            for claim in unsupported_claims
        ],
        "readability": _normalize_diagnostic(readability),
        "primary_error_type": (
            payload["primary_error_type"].strip()
            if isinstance(payload["primary_error_type"], str)
            else None
        ),
        "secondary_error_types": [error_type.strip() for error_type in secondary_error_types],
        "grader_reason": payload["grader_reason"].strip(),
    }


def validate_grader_payload(
    payload: Mapping[str, object],
    required_fact_ids: Sequence[str],
    source_fact_ids: Sequence[str] | None = None,
) -> list[str]:
    """Return contract errors without retaining any grading or experiment metadata."""
    errors: list[str] = []
    required_ids = _validate_required_ids(required_fact_ids, errors)
    source_ids = _validate_source_ids(
        required_fact_ids if source_fact_ids is None else source_fact_ids,
        required_ids,
        errors,
    )

    if not isinstance(payload, Mapping):
        return [*errors, "grader payload must be an object"]

    extra_keys = set(payload) - _ROOT_KEYS
    missing_keys = _ROOT_KEYS - set(payload)
    if extra_keys:
        errors.append("grader payload contains unsupported keys")
    if missing_keys:
        errors.append("grader payload is missing required keys")

    _validate_language(payload.get("language_compliance"), errors)
    _validate_facts(payload.get("required_facts"), required_ids, errors)
    _validate_claims(payload.get("unsupported_claims"), source_ids, errors)
    _validate_readability(payload.get("readability"), errors)

    primary_error_type = payload.get("primary_error_type")
    if primary_error_type is not None and not _non_empty_string(primary_error_type):
        errors.append("primary_error_type must be a diagnostic string or null")

    secondary_error_types = payload.get("secondary_error_types")
    if not isinstance(secondary_error_types, list) or any(
        not _non_empty_string(error_type) for error_type in secondary_error_types
    ):
        errors.append("secondary_error_types must be a list of diagnostic strings")

    _validate_error_taxonomy(payload, errors)

    if not _non_empty_string(payload.get("grader_reason")):
        errors.append("grader_reason must be a non-empty string")
    return errors


def _validate_required_ids(required_fact_ids: Sequence[str], errors: list[str]) -> set[str]:
    fact_ids = list(required_fact_ids)
    if any(not _non_empty_string(fact_id) for fact_id in fact_ids):
        errors.append("required_fact_ids must contain non-empty strings")
    normalized_ids = [fact_id.strip() for fact_id in fact_ids if _non_empty_string(fact_id)]
    if len(normalized_ids) != len(set(normalized_ids)):
        errors.append("required_fact_ids must not contain duplicates")
    return set(normalized_ids)


def _validate_source_ids(
    source_fact_ids: Sequence[str], required_ids: set[str], errors: list[str]
) -> set[str]:
    fact_ids = list(source_fact_ids)
    if any(not _non_empty_string(fact_id) for fact_id in fact_ids):
        errors.append("source_fact_ids must contain non-empty strings")
    normalized_ids = [fact_id.strip() for fact_id in fact_ids if _non_empty_string(fact_id)]
    if len(normalized_ids) != len(set(normalized_ids)):
        errors.append("source_fact_ids must not contain duplicates")
    source_ids = set(normalized_ids)
    if not required_ids.issubset(source_ids):
        errors.append("required_fact_ids must be a subset of source_fact_ids")
    return source_ids


def _validate_language(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append("language_compliance must be an object")
        return
    _validate_exact_keys(value, {"label", "reason", "evidence"}, "language_compliance", errors)
    if value.get("label") not in _LANGUAGE_LABELS:
        errors.append("language_compliance.label must be pass, fail, or indeterminate")
    _require_non_empty(value.get("reason"), "language_compliance.reason", errors)
    _require_non_empty(value.get("evidence"), "language_compliance.evidence", errors)


def _validate_facts(value: object, required_ids: set[str], errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("required_facts must be a list")
        return

    found_ids: list[str] = []
    for index, fact in enumerate(value):
        prefix = f"required_facts[{index}]"
        if not isinstance(fact, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        _validate_exact_keys(
            fact, {"fact_id", "label", "output_evidence", "reason"}, prefix, errors
        )
        fact_id = fact.get("fact_id")
        if not _non_empty_string(fact_id):
            errors.append(f"{prefix}.fact_id must be a non-empty string")
        else:
            normalized_id = fact_id.strip()
            found_ids.append(normalized_id)
            if normalized_id not in required_ids:
                errors.append(f"{prefix} has unsupported fact_id {normalized_id!r}")
        if fact.get("label") not in _FACT_LABELS:
            errors.append(f"{prefix}.label must be met, not_met, or indeterminate")
        _require_non_empty(fact.get("reason"), f"{prefix}.reason", errors)
        output_evidence = fact.get("output_evidence")
        if not isinstance(output_evidence, str):
            errors.append(f"{prefix}.output_evidence must be a string")
        elif fact.get("label") == "met" and not output_evidence.strip():
            errors.append(f"{prefix}.output_evidence must be a non-empty string")

    if len(found_ids) != len(set(found_ids)):
        errors.append("required_facts fact_id values must not contain duplicates")
    if set(found_ids) != required_ids or len(found_ids) != len(required_ids):
        errors.append("required_facts must cover each required_fact_id exactly once")


def _validate_claims(value: object, known_fact_ids: set[str], errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("unsupported_claims must be a list")
        return
    for index, claim in enumerate(value):
        prefix = f"unsupported_claims[{index}]"
        if not isinstance(claim, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        _validate_exact_keys(
            claim,
            {"claim", "output_evidence", "supporting_fact_ids", "reason"},
            prefix,
            errors,
        )
        _require_non_empty(claim.get("claim"), f"{prefix}.claim", errors)
        _require_non_empty(claim.get("output_evidence"), f"{prefix}.output_evidence", errors)
        _require_non_empty(claim.get("reason"), f"{prefix}.reason", errors)
        supporting_fact_ids = claim.get("supporting_fact_ids")
        if not isinstance(supporting_fact_ids, list) or any(
            not _non_empty_string(fact_id) for fact_id in supporting_fact_ids
        ):
            errors.append(f"{prefix}.supporting_fact_ids must be a list of fact IDs")
            continue
        for fact_id in supporting_fact_ids:
            normalized_id = fact_id.strip()
            if normalized_id not in known_fact_ids:
                errors.append(
                    f"{prefix} has unsupported supporting_fact_id {normalized_id!r}"
                )


def _validate_readability(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append("readability must be an object")
        return
    _validate_exact_keys(value, {"label", "reason", "evidence"}, "readability", errors)
    if value.get("label") not in _READABILITY_LABELS:
        errors.append("readability.label must be pass, fail, or indeterminate")
    _require_non_empty(value.get("reason"), "readability.reason", errors)
    _require_non_empty(value.get("evidence"), "readability.evidence", errors)


def _validate_error_taxonomy(payload: Mapping[str, object], errors: list[str]) -> None:
    """Ensure diagnostics are represented by the fixed, evidence-derived taxonomy."""
    detected = _detected_error_types(payload)
    primary = payload.get("primary_error_type")
    secondary = payload.get("secondary_error_types")

    if not detected:
        if primary is not None:
            errors.append("primary_error_type must be null when no diagnostic error is detected")
        if secondary != []:
            errors.append("secondary_error_types must be [] when no diagnostic error is detected")
        return

    expected_primary = next(
        error_type for error_type in _ERROR_PRIORITY if error_type in detected
    )
    if primary != expected_primary:
        errors.append(
            f"primary_error_type must be {expected_primary!r} for the detected diagnostics"
        )

    if not isinstance(secondary, list):
        return
    normalized_secondary = [
        item.strip() for item in secondary if isinstance(item, str)
    ]
    if len(normalized_secondary) != len(set(normalized_secondary)):
        errors.append("secondary_error_types must not contain duplicates")
    if primary is not None and primary in normalized_secondary:
        errors.append("secondary_error_types must not contain primary_error_type")
    for error_type in normalized_secondary:
        if error_type not in _ERROR_TYPES:
            errors.append(f"secondary_error_types contains unsupported error type {error_type!r}")
        elif error_type not in detected:
            errors.append(
                f"secondary_error_types contains undetected error type {error_type!r}"
            )
    if isinstance(primary, str) and primary in detected:
        expected_secondary = detected - {primary}
        if set(normalized_secondary) != expected_secondary:
            errors.append(
                "secondary_error_types must contain every other detected diagnostic exactly once"
            )


def _detected_error_types(payload: Mapping[str, object]) -> set[str]:
    detected: set[str] = set()
    # ``other`` has no separate structured field. Its declaration in either
    # taxonomy field is the deterministic evidence that this diagnostic exists;
    # the required non-empty grader_reason carries its explanation.
    if payload.get("primary_error_type") == "other":
        detected.add("other")
    declared_secondary = payload.get("secondary_error_types")
    if isinstance(declared_secondary, list) and "other" in declared_secondary:
        detected.add("other")

    unsupported_claims = payload.get("unsupported_claims")
    if isinstance(unsupported_claims, list) and unsupported_claims:
        detected.add("unsupported_claim")

    required_facts = payload.get("required_facts")
    if isinstance(required_facts, list):
        labels = {
            fact.get("label")
            for fact in required_facts
            if isinstance(fact, Mapping)
        }
        if "not_met" in labels:
            detected.add("required_fact_missing")
        if "indeterminate" in labels:
            detected.add("ambiguous_evidence")

    language = payload.get("language_compliance")
    if isinstance(language, Mapping):
        if language.get("label") == "fail":
            detected.add("language_noncompliance")
        elif language.get("label") == "indeterminate":
            detected.add("ambiguous_evidence")

    readability = payload.get("readability")
    if isinstance(readability, Mapping) and readability.get("label") == "fail":
        detected.add("readability_issue")
    return detected


def _validate_exact_keys(
    value: Mapping[str, object], allowed_keys: set[str], name: str, errors: list[str]
) -> None:
    if set(value) != allowed_keys:
        errors.append(f"{name} must contain exactly its allowlisted keys")


def _require_non_empty(value: object, name: str, errors: list[str]) -> None:
    if not _non_empty_string(value):
        errors.append(f"{name} must be a non-empty string")


def _normalize_diagnostic(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("validated diagnostics must be mappings")
    return {key: value[key].strip() for key in ("label", "reason", "evidence")}


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
