from __future__ import annotations

import json
import sqlite3

from eval_lab.application.prompts import WorkflowError


def load_case(conn: sqlite3.Connection, case_id: int) -> dict[str, object]:
    """Load one Case and its fixed Task Pack contract in application-ready form."""
    row = conn.execute(
        """
        SELECT tc.*, tp.pack_key, tp.contract_version, tp.contract_hash,
               tp.language, tp.title_min_chars, tp.title_max_chars,
               tp.summary_min_chars, tp.summary_max_chars, tp.key_points_count,
               tp.key_point_min_chars, tp.key_point_max_chars
        FROM test_cases AS tc
        JOIN task_packs AS tp ON tp.id = tc.task_pack_id
        WHERE tc.id = ?
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        raise WorkflowError(f"test case {case_id} was not found")

    return {
        "id": row["id"],
        "case_key": row["case_key"],
        "revision": row["revision"],
        "split": row["split"],
        "source_material": row["source_material"],
        "source_facts": _load_json_list(row["source_facts_json"], "source_facts_json"),
        "required_fact_ids": _load_json_list(
            row["required_fact_ids_json"], "required_fact_ids_json"
        ),
        "explicit_forbidden_claims": _load_json_list(
            row["explicit_forbidden_claims_json"], "explicit_forbidden_claims_json"
        ),
        "task_notes": row["task_notes"],
        "feasibility_qa_status": row["feasibility_qa_status"],
        "content_hash": row["content_hash"],
        "task_pack_contract": {
            "pack_key": row["pack_key"],
            "contract_version": row["contract_version"],
            "contract_hash": row["contract_hash"],
            "language": row["language"],
            "title_min_chars": row["title_min_chars"],
            "title_max_chars": row["title_max_chars"],
            "summary_min_chars": row["summary_min_chars"],
            "summary_max_chars": row["summary_max_chars"],
            "key_points_count": row["key_points_count"],
            "key_point_min_chars": row["key_point_min_chars"],
            "key_point_max_chars": row["key_point_max_chars"],
            "root_keys": ["title", "summary", "key_points"],
        },
    }


def _load_json_list(raw_value: object, field_name: str) -> list[object]:
    if not isinstance(raw_value, str):
        raise WorkflowError(f"stored {field_name} must be JSON text")
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"stored {field_name} is not valid JSON") from exc
    if not isinstance(parsed, list):
        raise WorkflowError(f"stored {field_name} must be a JSON list")
    return parsed
