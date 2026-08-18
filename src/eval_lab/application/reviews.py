from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import math
import sqlite3

from eval_lab.application.packets import (
    build_blind_human_review_packet,
    build_corrective_human_review_packet,
)
from eval_lab.application.prompts import WorkflowError
from eval_lab.domain.review_corrections import (
    CORRECTIVE_RE_REVIEW,
    effective_final_decision,
    validate_correction_payload,
)
from eval_lab.imports.human_reviews import parse_human_review_payload
from eval_lab.repositories.sqlite import (
    get_human_review_correction_for_review,
    insert_human_review,
    insert_human_review_correction,
)


def build_blind_human_review_packet_for_result(
    conn: sqlite3.Connection, evaluation_result_id: int
) -> dict[str, object]:
    """Build the independent pre-submission packet with no automatic evidence."""
    return build_blind_human_review_packet(conn, evaluation_result_id)


def build_corrective_human_review_packet_for_result(
    conn: sqlite3.Connection, evaluation_result_id: int
) -> dict[str, object]:
    """Build the separate corrective review packet with a literal raw-response block."""
    return build_corrective_human_review_packet(conn, evaluation_result_id)


def select_predeclared_review_sample(
    conn: sqlite3.Connection, comparison_group_id: str, fraction: float = 0.20
) -> list[int]:
    """Select a stable SHA-256 sample without reading any Grader outcomes."""
    _validate_sampling_inputs(comparison_group_id, fraction)
    return sorted(_sample_rows(_evaluation_rows(conn, comparison_group_id), fraction))


def required_review_targets(conn: sqlite3.Connection, comparison_group_id: str) -> list[int]:
    """Queue all automatic exceptions plus the predeclared sample of remaining rows."""
    return sorted(review_target_scopes(conn, comparison_group_id))


def review_target_scopes(
    conn: sqlite3.Connection, comparison_group_id: str, fraction: float = 0.20
) -> dict[int, str]:
    """Return each predeclared target and its immutable required/sampled scope."""
    _validate_sampling_inputs(comparison_group_id, fraction)
    rows = _evaluation_rows(conn, comparison_group_id, include_grader_outcomes=True)
    required = [row for row in rows if _requires_review(row)]
    required_ids = {int(row["evaluation_result_id"]) for row in required}
    sampled_remaining = _sample_rows(
        [row for row in rows if int(row["evaluation_result_id"]) not in required_ids], fraction
    )
    scopes = {evaluation_result_id: "required" for evaluation_result_id in required_ids}
    scopes.update({evaluation_result_id: "sampled" for evaluation_result_id in sampled_remaining})
    return scopes


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
    context = conn.execute(
        """
        SELECT run.comparison_group_id
        FROM evaluation_results AS er
        JOIN model_outputs AS mo ON mo.id = er.model_output_id
        JOIN evaluation_runs AS run ON run.id = mo.evaluation_run_id
        WHERE er.id = ?
        """,
        (evaluation_result_id,),
    ).fetchone()
    if context is None:
        raise WorkflowError(f"evaluation result {evaluation_result_id} was not found")
    target_scope = review_target_scopes(conn, str(context["comparison_group_id"])).get(
        evaluation_result_id
    )
    if target_scope is None:
        raise WorkflowError("evaluation result is not a predeclared review target")
    if review_scope != target_scope:
        raise WorkflowError(f"review_scope must be {target_scope} for this target")
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


def record_human_review_correction(
    conn: sqlite3.Connection,
    original_human_review_id: int,
    evaluation_result_id: int,
    correction_reason: str,
    reviewer_evidence: object,
    reviewer_reason: str,
    corrected_final_decision: str,
    *,
    corrected_at: str | None = None,
    review_mode: str = CORRECTIVE_RE_REVIEW,
) -> int:
    """Append one corrective re-review without changing the original review."""
    original = conn.execute(
        """
        SELECT id, evaluation_result_id
        FROM human_reviews
        WHERE id = ?
        """,
        (original_human_review_id,),
    ).fetchone()
    if original is None:
        raise WorkflowError(f"human review {original_human_review_id} was not found")
    if int(original["evaluation_result_id"]) != evaluation_result_id:
        raise WorkflowError(
            "correction evaluation_result_id must match the original human review"
        )
    if get_human_review_correction_for_review(conn, original_human_review_id) is not None:
        raise WorkflowError("human review already has a correction")
    try:
        validate_correction_payload(
            correction_reason=correction_reason,
            reviewer_evidence=reviewer_evidence,
            reviewer_reason=reviewer_reason,
            corrected_final_decision=corrected_final_decision,
            review_mode=review_mode,
        )
    except ValueError as exc:
        raise WorkflowError(str(exc)) from exc
    timestamp = _utc_now() if corrected_at is None else corrected_at
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise WorkflowError("corrected_at must be a non-empty string")
    try:
        return insert_human_review_correction(
            conn,
            {
                "original_human_review_id": original_human_review_id,
                "evaluation_result_id": evaluation_result_id,
                "review_mode": review_mode,
                "correction_reason": correction_reason,
                "reviewer_evidence": reviewer_evidence,
                "reviewer_reason": reviewer_reason,
                "corrected_final_decision": corrected_final_decision,
                "corrected_at": timestamp,
            },
        )
    except sqlite3.IntegrityError as exc:
        raise WorkflowError("human review correction could not be appended") from exc


def effective_human_review_decision(
    conn: sqlite3.Connection, evaluation_result_id: int
) -> str | None:
    """Read the effective human layer while retaining original/correction rows."""
    row = conn.execute(
        """
        SELECT hr.final_decision AS original_final_decision,
               hrc.corrected_final_decision
        FROM human_reviews AS hr
        LEFT JOIN human_review_corrections AS hrc
          ON hrc.original_human_review_id = hr.id
        WHERE hr.evaluation_result_id = ?
        """,
        (evaluation_result_id,),
    ).fetchone()
    if row is None:
        raise WorkflowError(f"human review for evaluation result {evaluation_result_id} was not found")
    return effective_final_decision(
        row["original_final_decision"], row["corrected_final_decision"]
    )


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
