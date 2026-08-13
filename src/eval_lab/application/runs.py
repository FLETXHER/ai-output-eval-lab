from __future__ import annotations

from collections.abc import Mapping
import sqlite3

from eval_lab.application.prompts import WorkflowError
from eval_lab.repositories.sqlite import (
    get_evaluation_run,
    insert_evaluation_run,
    update_run_status,
)


_METADATA_KEYS = (
    "case_set_hash",
    "contract_hash",
    "generator_product",
    "generator_visible_model",
    "environment_notes",
    "protocol_version",
)
_COMPARABLE_KEYS = (
    "comparison_group_id",
    "split",
    "case_set_hash",
    "contract_hash",
    "generator_product",
    "generator_visible_model",
    "environment_notes",
    "protocol_version",
)


def create_evaluation_run(
    conn: sqlite3.Connection,
    prompt_version_id: int,
    comparison_group_id: str,
    split: str,
    metadata: Mapping[str, object],
) -> int:
    """Open one run once its required provenance and Holdout gate are satisfied."""
    _require_non_empty(comparison_group_id, "comparison_group_id")
    if split not in {"dev", "holdout"}:
        raise WorkflowError("split must be 'dev' or 'holdout'")
    _validate_metadata(metadata)

    prompt = conn.execute(
        "SELECT id FROM prompt_versions WHERE id = ?", (prompt_version_id,)
    ).fetchone()
    if prompt is None:
        raise WorkflowError(f"prompt version {prompt_version_id} was not found")

    if split == "holdout":
        frozen_v2 = conn.execute(
            "SELECT 1 FROM prompt_versions WHERE version_label = 'v2' AND status = 'frozen'"
        ).fetchone()
        if frozen_v2 is None:
            raise WorkflowError("Holdout runs require frozen Prompt v2")

    created_at = _metadata_timestamp(metadata, "created_at")
    updated_at = _metadata_timestamp(metadata, "updated_at", fallback=created_at)
    return insert_evaluation_run(
        conn,
        {
            "comparison_group_id": comparison_group_id,
            "prompt_version_id": prompt_version_id,
            "split": split,
            **{key: metadata[key] for key in _METADATA_KEYS},
            "status": "open",
            "created_at": created_at,
            "updated_at": updated_at,
        },
    )


def assert_runs_comparable(
    run_a: Mapping[str, object], run_b: Mapping[str, object]
) -> None:
    """Reject paired analysis when any approved comparison condition differs."""
    for key in _COMPARABLE_KEYS:
        if _mapping_value(run_a, key) != _mapping_value(run_b, key):
            raise WorkflowError(f"runs are not comparable: {key} differs")


def close_run(conn: sqlite3.Connection, run_id: int) -> None:
    """Close an open run so it can no longer receive output or rule writes."""
    run = get_evaluation_run(conn, run_id)
    if run["status"] != "open":
        raise WorkflowError("only an open evaluation run can be closed")
    update_run_status(conn, run_id, "closed")


def _validate_metadata(metadata: Mapping[str, object]) -> None:
    for key in _METADATA_KEYS:
        _require_non_empty(metadata.get(key), key)


def _metadata_timestamp(
    metadata: Mapping[str, object], key: str, *, fallback: str | None = None
) -> str:
    value = metadata.get(key, fallback)
    return _require_non_empty(value, key)


def _require_non_empty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"{name} must be a non-empty string")
    return value


def _mapping_value(mapping: Mapping[str, object], key: str) -> object:
    if key not in mapping.keys():
        raise WorkflowError(f"run metadata is missing {key}")
    return mapping[key]
