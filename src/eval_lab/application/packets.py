from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import sqlite3

from eval_lab.domain.packets import (
    HUMAN_REVIEW_DECISION_OPTIONS,
    HUMAN_REVIEW_RUBRIC,
    render_blind_grader_packet,
    render_blind_human_review_packet,
    render_generation_packet,
)
from eval_lab.repositories.sqlite import transaction


_CONTRACT_COLUMNS = (
    "pack_key",
    "contract_version",
    "language",
    "title_min_chars",
    "title_max_chars",
    "summary_min_chars",
    "summary_max_chars",
    "key_points_count",
    "key_point_min_chars",
    "key_point_max_chars",
)


def build_generation_packet(
    conn: sqlite3.Connection, run_id: int, test_case_id: int
) -> dict[str, object]:
    """Build a copy-ready generation packet and refresh existing slot provenance."""
    row = conn.execute(
        """
        SELECT
            tc.source_material,
            tc.task_notes,
            pv.prompt_text,
            tp.pack_key,
            tp.contract_version,
            tp.language,
            tp.title_min_chars,
            tp.title_max_chars,
            tp.summary_min_chars,
            tp.summary_max_chars,
            tp.key_points_count,
            tp.key_point_min_chars,
            tp.key_point_max_chars
        FROM evaluation_runs AS er
        JOIN prompt_versions AS pv ON pv.id = er.prompt_version_id
        JOIN test_cases AS tc ON tc.id = ?
        JOIN task_packs AS tp ON tp.id = tc.task_pack_id
        WHERE er.id = ?
        """,
        (test_case_id, run_id),
    ).fetchone()
    if row is None:
        raise LookupError("generation packet context was not found")

    packet = render_generation_packet(
        {
            "source_material": row["source_material"],
            "task_notes": row["task_notes"],
        },
        _contract_from_row(row),
        {"prompt_text": row["prompt_text"]},
    )
    with transaction(conn):
        conn.execute(
            """
            UPDATE model_outputs
            SET generation_packet_version = ?, generation_packet_hash = ?
            WHERE evaluation_run_id = ? AND test_case_id = ?
            """,
            (
                packet["packet_version"],
                packet["content_hash"],
                run_id,
                test_case_id,
            ),
        )
    return packet


def build_blind_grader_packet(
    conn: sqlite3.Connection, model_output_id: int, grader_condition_id: int
) -> dict[str, object]:
    """Build one pointwise blind Grader packet without loading Run metadata."""
    row = conn.execute(
        """
        SELECT
            mo.candidate_id,
            mo.raw_response,
            tc.source_material,
            tc.source_facts_json,
            tc.required_fact_ids_json,
            tc.explicit_forbidden_claims_json,
            tc.task_notes,
            gc.grader_prompt,
            gc.rubric,
            gc.error_taxonomy,
            tp.pack_key,
            tp.contract_version,
            tp.language,
            tp.title_min_chars,
            tp.title_max_chars,
            tp.summary_min_chars,
            tp.summary_max_chars,
            tp.key_points_count,
            tp.key_point_min_chars,
            tp.key_point_max_chars
        FROM model_outputs AS mo
        JOIN test_cases AS tc ON tc.id = mo.test_case_id
        JOIN task_packs AS tp ON tp.id = tc.task_pack_id
        JOIN grader_conditions AS gc ON gc.id = ?
        WHERE mo.id = ?
        """,
        (grader_condition_id, model_output_id),
    ).fetchone()
    if row is None:
        raise LookupError("blind Grader packet context was not found")
    if row["raw_response"] is None:
        raise ValueError("cannot build a Grader packet without a model response")

    packet = render_blind_grader_packet(
        candidate_id=row["candidate_id"],
        task_pack_contract=_contract_from_row(row),
        source_material=row["source_material"],
        source_facts=_json_list_of_mappings(row["source_facts_json"], "source_facts_json"),
        required_fact_ids=_json_list_of_strings(
            row["required_fact_ids_json"], "required_fact_ids_json"
        ),
        constraints=_case_constraints(row),
        raw_model_response=row["raw_response"],
        grader_prompt=row["grader_prompt"],
        rubric=row["rubric"],
        error_taxonomy=row["error_taxonomy"],
    )
    with transaction(conn):
        conn.execute(
            """
            UPDATE grader_results
            SET blind_packet_version = ?, blind_packet_hash = ?
            WHERE model_output_id = ? AND grader_condition_id = ?
            """,
            (
                packet["packet_version"],
                packet["content_hash"],
                model_output_id,
                grader_condition_id,
            ),
        )
    return packet


def build_blind_human_review_packet(
    conn: sqlite3.Connection, evaluation_result_id: int
) -> dict[str, object]:
    """Build the independent reviewer-facing context before a decision is submitted."""
    row = conn.execute(
        """
        SELECT
            mo.candidate_id,
            mo.raw_response,
            tc.source_material,
            tc.task_notes,
            tc.explicit_forbidden_claims_json,
            tp.pack_key,
            tp.contract_version,
            tp.language,
            tp.title_min_chars,
            tp.title_max_chars,
            tp.summary_min_chars,
            tp.summary_max_chars,
            tp.key_points_count,
            tp.key_point_min_chars,
            tp.key_point_max_chars
        FROM evaluation_results AS er
        JOIN model_outputs AS mo ON mo.id = er.model_output_id
        JOIN test_cases AS tc ON tc.id = mo.test_case_id
        JOIN task_packs AS tp ON tp.id = tc.task_pack_id
        WHERE er.id = ?
        """,
        (evaluation_result_id,),
    ).fetchone()
    if row is None:
        raise LookupError("blind Human Review packet context was not found")
    if row["raw_response"] is None:
        raise ValueError("cannot build a Human Review packet without a model response")

    return render_blind_human_review_packet(
        candidate_id=row["candidate_id"],
        task_pack_contract=_contract_from_row(row),
        source_material=row["source_material"],
        task_instructions=row["task_notes"],
        constraints=_case_constraints(row, include_task_instructions=False),
        raw_model_response=row["raw_response"],
        human_review_rubric=HUMAN_REVIEW_RUBRIC,
        decision_options=HUMAN_REVIEW_DECISION_OPTIONS,
    )


def _contract_from_row(row: Mapping[str, object]) -> dict[str, object]:
    contract = {column: row[column] for column in _CONTRACT_COLUMNS}
    contract["root_keys"] = ["title", "summary", "key_points"]
    return contract


def _case_constraints(
    row: Mapping[str, object], *, include_task_instructions: bool = True
) -> dict[str, object]:
    constraints: dict[str, object] = {}
    if include_task_instructions:
        constraints["task_instructions"] = row["task_notes"]
    constraints["explicit_forbidden_claims"] = _json_list_of_strings(
        row["explicit_forbidden_claims_json"], "explicit_forbidden_claims_json"
    )
    return constraints


def _json_list(raw_json: object, name: str) -> list[object]:
    if not isinstance(raw_json, str):
        raise ValueError(f"{name} must be JSON text")
    try:
        value = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must contain valid JSON") from exc
    if not isinstance(value, list):
        raise ValueError(f"{name} must contain a JSON list")
    return value


def _json_list_of_strings(raw_json: object, name: str) -> list[str]:
    value = _json_list(raw_json, name)
    if any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must contain only strings")
    return value  # type: ignore[return-value]


def _json_list_of_mappings(
    raw_json: object, name: str
) -> Sequence[Mapping[str, str]]:
    value = _json_list(raw_json, name)
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{name} must contain only objects")
    return value  # type: ignore[return-value]
