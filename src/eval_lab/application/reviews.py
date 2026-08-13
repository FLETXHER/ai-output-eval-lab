from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import math
import sqlite3

from eval_lab.application.packets import build_blind_human_review_packet
from eval_lab.application.prompts import WorkflowError
from eval_lab.imports.human_reviews import parse_human_review_payload
from eval_lab.repositories.sqlite import insert_human_review


def build_blind_human_review_packet_for_result(
    conn: sqlite3.Connection, evaluation_result_id: int
) -> dict[str, object]:
    """Build the independent pre-submission packet with no automatic evidence."""
    return build_blind_human_review_packet(conn, evaluation_result_id)


def select_predeclared_review_sample(
    conn: sqlite3.Connection, comparison_group_id: str, fraction: float = 0.20
) -> list[int]:
    """Select a stable SHA-256 sample without reading any Grader outcomes."""
    _validate_sampling_inputs(comparison_group_id, fraction)
    return sorted(_sample_rows(_evaluation_rows(conn, comparison_group_id), fraction))


def required_review_targets(conn: sqlite3.Connection, comparison_group_id: str) -> list[int]:
    """Queue all automatic exceptions plus the predeclared sample of remaining rows."""
    _validate_sampling_inputs(comparison_group_id, 0.20)
    rows = _evaluation_rows(conn, comparison_group_id, include_grader_outcomes=True)
    required = [row for row in rows if _requires_review(row)]
    required_ids = {int(row["evaluation_result_id"]) for row in required}
    sampled_remaining = _sample_rows(
        [row for row in rows if int(row["evaluation_result_id"]) not in required_ids], 0.20
    )
    return sorted(required_ids | set(sampled_remaining))


def record_human_review(
    conn: sqlite3.Connection,
    evaluation_result_id: int,
    review_scope: str,
    blind_review: bool,
    evidence: Mapping[str, object],
    reason: str,
    final_decision: str,
) -> int:
    """Persist one independent final decision without touching automatic evidence."""
    if conn.execute(
        "SELECT 1 FROM evaluation_results WHERE id = ?", (evaluation_result_id,)
    ).fetchone() is None:
        raise WorkflowError(f"evaluation result {evaluation_result_id} was not found")
    if conn.execute(
        "SELECT 1 FROM human_reviews WHERE evaluation_result_id = ?", (evaluation_result_id,)
    ).fetchone() is not None:
        raise WorkflowError("a human review already exists for this evaluation result")
    payload: dict[str, object] = {
        "review_scope": review_scope,
        "blind_review": blind_review,
        "evidence": dict(evidence),
        "reason": reason,
        "final_decision": final_decision,
        "reviewed_at": _utc_now(),
    }
    validation = parse_human_review_payload(payload)
    if not validation["ok"] or validation["value"] is None:
        raise WorkflowError("invalid human review payload: " + "; ".join(validation["errors"]))
    return insert_human_review(conn, {"evaluation_result_id": evaluation_result_id, **validation["value"]})


def _evaluation_rows(
    conn: sqlite3.Connection,
    comparison_group_id: str,
    *,
    include_grader_outcomes: bool = False,
) -> list[sqlite3.Row]:
    columns = "er.id AS evaluation_result_id, mo.candidate_id, run.prompt_version_id, run.split"
    if include_grader_outcomes:
        columns += ", er.calculated_status, gr.unsupported_claims_json"
    return list(
        conn.execute(
            f"""
            SELECT {columns}
            FROM evaluation_results AS er
            JOIN model_outputs AS mo ON mo.id = er.model_output_id
            JOIN evaluation_runs AS run ON run.id = mo.evaluation_run_id
            LEFT JOIN grader_results AS gr ON gr.id = er.grader_result_id
            WHERE run.comparison_group_id = ?
            """,
            (comparison_group_id,),
        )
    )


def _sample_rows(rows: Sequence[sqlite3.Row], fraction: float) -> list[int]:
    by_stratum: dict[tuple[int, str], list[sqlite3.Row]] = {}
    for row in rows:
        key = (int(row["prompt_version_id"]), str(row["split"]))
        by_stratum.setdefault(key, []).append(row)
    selected: list[int] = []
    for stratum_rows in by_stratum.values():
        ranked = sorted(
            stratum_rows,
            key=lambda row: hashlib.sha256(str(row["candidate_id"]).encode("utf-8")).hexdigest(),
        )
        selected.extend(
            int(row["evaluation_result_id"])
            for row in ranked[: math.ceil(fraction * len(ranked))]
        )
    return selected


def _requires_review(row: sqlite3.Row) -> bool:
    if row["calculated_status"] == "indeterminate":
        return True
    raw_claims = row["unsupported_claims_json"]
    if raw_claims is None:
        return False
    try:
        claims = json.loads(raw_claims)
    except json.JSONDecodeError:
        return True
    return not isinstance(claims, list) or bool(claims)


def _validate_sampling_inputs(comparison_group_id: str, fraction: float) -> None:
    if not isinstance(comparison_group_id, str) or not comparison_group_id.strip():
        raise WorkflowError("comparison_group_id must be a non-empty string")
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not 0 <= fraction <= 1:
        raise WorkflowError("fraction must be between 0 and 1")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
