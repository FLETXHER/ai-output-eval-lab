from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import sqlite3

from eval_lab.application.prompts import WorkflowError
from eval_lab.domain.rules import run_deterministic_rules
from eval_lab.repositories.sqlite import (
    fetch_output_context,
    insert_model_output_slot,
    insert_rule_results,
    transaction,
    update_technical_retry,
)


RULE_VERSION = "1.0"


def record_model_output(
    conn: sqlite3.Connection,
    run_id: int,
    test_case_id: int,
    generation_packet_version: str,
    generation_packet_hash: str,
    raw_response: str | None,
    generated_at: str | None,
    technical_retry_reason: str | None = None,
) -> int:
    """Persist the first actual response, or a technical retry before one exists."""
    _require_non_empty(generation_packet_version, "generation_packet_version")
    _require_non_empty(generation_packet_hash, "generation_packet_hash")
    _assert_open_run_and_matching_case(conn, run_id, test_case_id)
    _validate_capture_arguments(raw_response, generated_at, technical_retry_reason)

    existing = conn.execute(
        """SELECT id, raw_response, generation_packet_version, generation_packet_hash
        FROM model_outputs WHERE evaluation_run_id = ? AND test_case_id = ?""",
        (run_id, test_case_id),
    ).fetchone()
    if existing is None:
        return _create_output_slot(
            conn,
            run_id,
            test_case_id,
            generation_packet_version,
            generation_packet_hash,
            raw_response,
            generated_at,
            technical_retry_reason,
        )

    if existing["raw_response"] is not None:
        raise WorkflowError("the first actual response is immutable evidence")
    if (
        existing["generation_packet_version"] != generation_packet_version
        or existing["generation_packet_hash"] != generation_packet_hash
    ):
        raise WorkflowError("technical retries must use the original generation packet")

    output_id = int(existing["id"])
    if raw_response is None:
        update_technical_retry(conn, output_id, technical_retry_reason or "")
        return output_id

    with transaction(conn):
        conn.execute(
            """UPDATE model_outputs
            SET raw_response = ?, output_hash = ?, generated_at = ?, updated_at = ?
            WHERE id = ? AND raw_response IS NULL""",
            (raw_response, _response_hash(raw_response), generated_at, _utc_now(), output_id),
        )
    return output_id


def evaluate_output_rules(
    conn: sqlite3.Connection,
    model_output_id: int,
    contract: Mapping[str, object],
    forbidden_claims: Sequence[str],
) -> list[dict[str, object]]:
    """Delegate deterministic Rules to Domain and persist their complete result set."""
    context = fetch_output_context(conn, model_output_id)
    if context["evaluation_run"]["status"] != "open":
        raise WorkflowError("cannot evaluate rules for a closed evaluation run")
    raw_response = context["model_output"]["raw_response"]
    if raw_response is None:
        raise WorkflowError("cannot evaluate rules without an actual model response")
    if not isinstance(raw_response, str):
        raise WorkflowError("stored raw response must be text")

    domain_result = run_deterministic_rules(raw_response, contract, forbidden_claims)
    calculated_at = _utc_now()
    rows: list[dict[str, object]] = []
    for result in domain_result["rule_results"]:
        if not isinstance(result, Mapping):
            raise WorkflowError("Domain returned an invalid rule result")
        rows.append(
            {
                "rule_key": result["rule_key"],
                "rule_version": RULE_VERSION,
                "status": result["status"],
                "actual": result["actual"],
                "expected": result["expected"],
                "reason": result["reason"],
                "calculated_at": calculated_at,
            }
        )
    insert_rule_results(conn, model_output_id, rows)
    return rows


def _create_output_slot(
    conn: sqlite3.Connection,
    run_id: int,
    test_case_id: int,
    generation_packet_version: str,
    generation_packet_hash: str,
    raw_response: str | None,
    generated_at: str | None,
    technical_retry_reason: str | None,
) -> int:
    now = _utc_now()
    return insert_model_output_slot(
        conn,
        {
            "evaluation_run_id": run_id,
            "test_case_id": test_case_id,
            "candidate_id": _candidate_id(run_id, test_case_id),
            "generation_packet_version": generation_packet_version,
            "generation_packet_hash": generation_packet_hash,
            "raw_response": raw_response,
            "output_hash": _response_hash(raw_response) if raw_response is not None else None,
            "generated_at": generated_at,
            "technical_retry_count": 1 if raw_response is None else 0,
            "technical_retry_reasons": [technical_retry_reason] if raw_response is None else [],
            "created_at": now,
            "updated_at": now,
        },
    )


def _assert_open_run_and_matching_case(
    conn: sqlite3.Connection, run_id: int, test_case_id: int
) -> None:
    run = conn.execute(
        "SELECT status, split FROM evaluation_runs WHERE id = ?", (run_id,)
    ).fetchone()
    if run is None:
        raise WorkflowError("evaluation run or test case was not found")
    if run["status"] != "open":
        raise WorkflowError("evaluation run is closed or unavailable for writes")
    row = conn.execute(
        "SELECT split FROM test_cases WHERE id = ?", (test_case_id,)
    ).fetchone()
    if row is None:
        raise WorkflowError("evaluation run or test case was not found")
    if run["split"] != row["split"]:
        raise WorkflowError("test case split does not match evaluation run split")


def _validate_capture_arguments(
    raw_response: str | None,
    generated_at: str | None,
    technical_retry_reason: str | None,
) -> None:
    if raw_response is not None and not isinstance(raw_response, str):
        raise WorkflowError("raw_response must be text or None")
    if raw_response is None:
        _require_non_empty(technical_retry_reason, "technical reason")
        if generated_at is not None:
            raise WorkflowError("technical retry cannot have generated_at")
        return
    if technical_retry_reason is not None:
        raise WorkflowError("an actual response cannot include a technical retry reason")
    _require_non_empty(generated_at, "generated_at")


def _candidate_id(run_id: int, test_case_id: int) -> str:
    digest = hashlib.sha256(f"{run_id}:{test_case_id}".encode("utf-8")).hexdigest()
    return f"candidate-{digest[:16]}"


def _response_hash(raw_response: str) -> str:
    return hashlib.sha256(raw_response.encode("utf-8")).hexdigest()


def _require_non_empty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"{name} must be a non-empty string")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
