from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone

from eval_lab.repositories.sqlite import freeze_prompt_version as persist_frozen_prompt
from eval_lab.repositories.sqlite import insert_prompt_version


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
        "SELECT status FROM prompt_versions WHERE id = ?", (prompt_version_id,)
    ).fetchone()
    if row is None:
        raise WorkflowError(f"prompt version {prompt_version_id} was not found")
    if row["status"] != "draft":
        raise WorkflowError("only a draft prompt version can be frozen")
    persist_frozen_prompt(conn, prompt_version_id, frozen_at)


def _require_non_empty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"{name} must be a non-empty string")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
