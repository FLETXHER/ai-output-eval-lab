"""Input import helpers for AI Output Eval Lab."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
from typing import TypedDict


class ValidationResult(TypedDict):
    ok: bool
    value: object | None
    errors: list[str]
    raw_text: str | None


def parse_json_text(raw_text: str) -> object:
    """Parse ordinary JSON without fences, repair, or substring extraction.

    A malformed input returns a validation result so callers can show the exact
    external text alongside a clear import error.
    """
    if not isinstance(raw_text, str):
        return _invalid(["raw JSON text must be a string"], raw_text=None)
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return _invalid(["invalid JSON"], raw_text=raw_text)


def valid(value: object) -> ValidationResult:
    return {"ok": True, "value": deepcopy(value), "errors": [], "raw_text": None}


def invalid(errors: list[str]) -> ValidationResult:
    return _invalid(errors, raw_text=None)


def exact_keys(
    payload: Mapping[str, object], allowed_keys: set[str], label: str
) -> list[str]:
    keys = set(payload)
    errors: list[str] = []
    missing = allowed_keys - keys
    extra = keys - allowed_keys
    if missing:
        errors.append(f"{label} is missing required keys: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"{label} contains unsupported keys: {', '.join(sorted(extra))}")
    return errors


def non_empty_string(value: object, field_name: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{field_name} must be a non-empty string"]
    return []


def sha256_hash(value: object, field_name: str) -> list[str]:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        return [f"{field_name} must be a lowercase SHA-256 hex string"]
    return []


def _invalid(errors: list[str], raw_text: str | None) -> ValidationResult:
    return {"ok": False, "value": None, "errors": errors, "raw_text": raw_text}
