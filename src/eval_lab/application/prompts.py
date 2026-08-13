from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone

from eval_lab.repositories.sqlite import freeze_prompt_version as persist_frozen_prompt
from eval_lab.repositories.sqlite import (
    get_evaluation_run,
    insert_prompt_version,
    transaction,
)


class WorkflowError(ValueError):
    """Raised when an evaluation workflow operation violates its lifecycle."""


def create_prompt_version(
    conn: sqlite3.Connection,
    prompt_text: str,
    version_label: str,
    change_reason: str,
) -> int:
    """Create an immutable draft prompt version with exact-text provenance."""
    _require_non_empty(prompt_text, "prompt_text")
    _require_non_empty(version_label, "version_label")
    _require_non_empty(change_reason, "change_reason")
    now = _utc_now()
    return insert_prompt_version(
        conn,
        {
            "version_label": version_label,
            "prompt_text": prompt_text,
            "change_reason": change_reason,
            "content_hash": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            "status": "draft",
            "owner_approved_at": None,
            "frozen_at": None,
            "created_at": now,
            "updated_at": now,
        },
    )


def freeze_prompt_version(
    conn: sqlite3.Connection, prompt_version_id: int, frozen_at: str
) -> None:
    """Freeze an existing draft prompt without changing its recorded text/hash."""
    _require_non_empty(frozen_at, "frozen_at")
    row = conn.execute(
        "SELECT status, owner_approved_at FROM prompt_versions WHERE id = ?", (prompt_version_id,)
    ).fetchone()
    if row is None:
        raise WorkflowError(f"prompt version {prompt_version_id} was not found")
    if row["status"] != "draft":
        raise WorkflowError("only a draft prompt version can be frozen")
    if not isinstance(row["owner_approved_at"], str) or not row["owner_approved_at"].strip():
        raise WorkflowError("only an owner-approved prompt version can be frozen")
    persist_frozen_prompt(conn, prompt_version_id, frozen_at)


def approve_prompt_version(
    conn: sqlite3.Connection, prompt_version_id: int, approved_at: str
) -> None:
    """Record owner approval for a draft prompt without freezing it."""
    _require_non_empty(approved_at, "approved_at")
    row = conn.execute(
        "SELECT status, owner_approved_at FROM prompt_versions WHERE id = ?", (prompt_version_id,)
    ).fetchone()
    if row is None:
        raise WorkflowError(f"prompt version {prompt_version_id} was not found")
    if row["status"] != "draft":
        raise WorkflowError("only a draft prompt version can be owner-approved")
    if row["owner_approved_at"] is not None:
        raise WorkflowError("prompt version is already owner-approved")
    with transaction(conn):
        conn.execute(
            "UPDATE prompt_versions SET owner_approved_at = ?, updated_at = ? WHERE id = ?",
            (approved_at, _utc_now(), prompt_version_id),
        )


def create_prompt_v2_after_dev(
    conn: sqlite3.Connection,
    dev_run_id: int,
    prompt_text: str,
    change_reason: str,
) -> int:
    """Create a v2 draft only after a closed Dev v1 run has stored results."""
    _require_non_empty(prompt_text, "prompt_text")
    _require_non_empty(change_reason, "change_reason")
    try:
        run = get_evaluation_run(conn, dev_run_id)
    except LookupError as exc:
        raise WorkflowError(f"evaluation run {dev_run_id} was not found") from exc
    if run["split"] != "dev":
        raise WorkflowError("Prompt v2 can only be created after a Dev run")
    if run["status"] != "closed":
        raise WorkflowError("Dev run must be closed before creating Prompt v2")
    prompt = conn.execute(
        "SELECT version_label FROM prompt_versions WHERE id = ?", (run["prompt_version_id"],)
    ).fetchone()
    if prompt is None or prompt["version_label"] != "v1":
        raise WorkflowError("Prompt v2 requires a completed Dev Prompt v1 run")
    result_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM evaluation_results AS er
        JOIN model_outputs AS mo ON mo.id = er.model_output_id
        WHERE mo.evaluation_run_id = ?
        """,
        (dev_run_id,),
    ).fetchone()[0]
    if int(result_count) == 0:
        raise WorkflowError("Dev run must have evaluation_results before creating Prompt v2")
    _require_complete_dev_case_coverage(conn, dev_run_id)
    return create_prompt_version(conn, prompt_text, "v2", change_reason)


def _require_complete_dev_case_coverage(
    conn: sqlite3.Connection, dev_run_id: int
) -> None:
    """Require output and evaluation coverage for every Dev Case in the run's Task Pack."""
    task_pack_rows = conn.execute(
        """
        SELECT DISTINCT tc.task_pack_id
        FROM model_outputs AS mo
        JOIN test_cases AS tc ON tc.id = mo.test_case_id
        WHERE mo.evaluation_run_id = ?
        """,
        (dev_run_id,),
    ).fetchall()
    if len(task_pack_rows) != 1:
        raise WorkflowError(
            "Dev run must have complete Dev case coverage for exactly one Task Pack"
        )
    task_pack_id = task_pack_rows[0]["task_pack_id"]
    expected_cases = conn.execute(
        """
        SELECT id, case_key
        FROM test_cases
        WHERE task_pack_id = ? AND split = 'dev'
        ORDER BY case_key, revision, id
        """,
        (task_pack_id,),
    ).fetchall()
    if not expected_cases:
        raise WorkflowError("Dev run must have complete Dev case coverage; no Dev Cases found")

    missing_outputs: list[str] = []
    missing_results: list[str] = []
    for case in expected_cases:
        output = conn.execute(
            """
            SELECT mo.id
            FROM model_outputs AS mo
            WHERE mo.evaluation_run_id = ? AND mo.test_case_id = ?
            """,
            (dev_run_id, case["id"]),
        ).fetchone()
        case_key = str(case["case_key"])
        if output is None:
            missing_outputs.append(case_key)
            continue
        result_count = conn.execute(
            "SELECT COUNT(*) FROM evaluation_results WHERE model_output_id = ?",
            (output["id"],),
        ).fetchone()[0]
        if int(result_count) == 0:
            missing_results.append(case_key)

    if missing_outputs or missing_results:
        details: list[str] = []
        if missing_outputs:
            details.append("missing model outputs: " + ", ".join(missing_outputs))
        if missing_results:
            details.append("missing evaluation_results: " + ", ".join(missing_results))
        raise WorkflowError("Dev run must have complete Dev case coverage (" + "; ".join(details) + ")")


def _require_non_empty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"{name} must be a non-empty string")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
