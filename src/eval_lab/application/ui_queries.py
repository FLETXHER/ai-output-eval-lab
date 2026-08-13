"""Small read-only query helpers used by the Streamlit page layer."""
from __future__ import annotations

import sqlite3


def list_open_evaluation_runs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute("SELECT id, split FROM evaluation_runs WHERE status = 'open' ORDER BY id")
    )


def list_test_cases_for_split(conn: sqlite3.Connection, split: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT id, case_key, revision FROM test_cases WHERE split = ? ORDER BY case_key, revision",
            (split,),
        )
    )


def get_model_output_slot(
    conn: sqlite3.Connection, run_id: int, case_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT id, raw_response, generation_packet_version, generation_packet_hash,
                  technical_retry_count, technical_retry_reasons_json
        FROM model_outputs WHERE evaluation_run_id = ? AND test_case_id = ?""",
        (run_id, case_id),
    ).fetchone()


def get_open_run_capture_context(
    conn: sqlite3.Connection, run_id: int
) -> sqlite3.Row | None:
    """Return only the provenance fields needed before output capture."""
    return conn.execute(
        """SELECT er.id, er.split, er.generator_visible_model,
                  COUNT(mo.id) AS model_output_count
        FROM evaluation_runs AS er
        LEFT JOIN model_outputs AS mo ON mo.evaluation_run_id = er.id
        WHERE er.id = ? AND er.status = 'open'
        GROUP BY er.id, er.split, er.generator_visible_model""",
        (run_id,),
    ).fetchone()


def list_captured_model_outputs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT id, candidate_id FROM model_outputs WHERE raw_response IS NOT NULL ORDER BY id"
        )
    )


def list_grader_condition_ids(conn: sqlite3.Connection) -> list[int]:
    return [int(row["id"]) for row in conn.execute("SELECT id FROM grader_conditions ORDER BY id")]


def get_grader_condition(conn: sqlite3.Connection, condition_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM grader_conditions WHERE id = ?", (condition_id,)).fetchone()


def list_unreviewed_evaluation_results(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """SELECT er.id, mo.candidate_id
            FROM evaluation_results AS er
            JOIN model_outputs AS mo ON mo.id = er.model_output_id
            LEFT JOIN human_reviews AS hr ON hr.evaluation_result_id = er.id
            WHERE hr.id IS NULL
            ORDER BY er.id"""
        )
    )


def get_decision_layer_comparison(
    conn: sqlite3.Connection, evaluation_result_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT er.calculated_status, hr.final_decision
        FROM evaluation_results AS er
        JOIN human_reviews AS hr ON hr.evaluation_result_id = er.id
        WHERE er.id = ?""",
        (evaluation_result_id,),
    ).fetchone()


def list_analysis_runs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute("SELECT id, comparison_group_id FROM evaluation_runs ORDER BY id")
    )
