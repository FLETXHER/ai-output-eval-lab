from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3

import streamlit as st

from eval_lab.application.grading import (
    build_blind_grader_packet_for_output,
    calculate_output_status,
    import_grader_result,
)
from eval_lab.application.prompts import WorkflowError
from eval_lab.application.reviews import (
    build_blind_human_review_packet_for_result,
    record_human_review,
)
from eval_lab.ui.components import show_validation_errors


def render(conn: sqlite3.Connection) -> None:
    st.title("Evaluation")
    mode = st.radio("Evaluation mode", ["Blind Grader Import", "Blind Human Review"])
    if mode == "Blind Grader Import":
        _render_blind_grader_import(conn)
    else:
        _render_blind_human_review(conn)


def _render_blind_grader_import(conn: sqlite3.Connection) -> None:
    outputs = list(conn.execute(
        """SELECT id, candidate_id FROM model_outputs
        WHERE raw_response IS NOT NULL ORDER BY id"""
    ))
    conditions = list(conn.execute("SELECT id FROM grader_conditions ORDER BY id"))
    if not outputs or not conditions:
        st.info("A captured response and a Grader Condition are required before import.")
        return
    output_by_id = {int(row["id"]): row for row in outputs}
    output_id = st.selectbox(
        "Anonymous candidate", list(output_by_id),
        format_func=lambda value: str(output_by_id[value]["candidate_id"]),
    )
    condition_ids = [int(row["id"]) for row in conditions]
    condition_id = st.selectbox("Grader Condition", condition_ids, format_func=lambda value: f"Condition {value}")
    try:
        packet = build_blind_grader_packet_for_output(conn, output_id, condition_id)
    except (LookupError, ValueError) as error:
        show_validation_errors([str(error)])
        return
    st.subheader("Copy-ready blind Grader packet")
    st.code(str(packet["text"]), language="text")
    st.caption(f"Blind Grader packet version: {packet['packet_version']}")
    st.caption(f"Blind Grader packet hash: {packet['content_hash']}")
    with st.form("import_blind_grader_result"):
        raw_json = st.text_area("Returned Grader JSON", height=220)
        submitted = st.form_submit_button("Import Grader JSON")
    if not submitted:
        return
    try:
        parsed = json.loads(raw_json)
        if not isinstance(parsed, dict):
            raise WorkflowError("grader JSON must be an object")
        condition = dict(conn.execute("SELECT * FROM grader_conditions WHERE id = ?", (condition_id,)).fetchone())
        grader_result_id = import_grader_result(conn, output_id, condition, parsed)
        calculate_output_status(conn, output_id, grader_result_id, condition_id)
    except (json.JSONDecodeError, WorkflowError, LookupError, ValueError, TypeError) as error:
        show_validation_errors([str(error)])
    else:
        st.success("Imported the blind Grader result and calculated automatic status.")


def _render_blind_human_review(conn: sqlite3.Connection) -> None:
    rows = list(conn.execute(
        """SELECT er.id, mo.candidate_id
        FROM evaluation_results AS er
        JOIN model_outputs AS mo ON mo.id = er.model_output_id
        LEFT JOIN human_reviews AS hr ON hr.evaluation_result_id = er.id
        WHERE hr.id IS NULL
        ORDER BY er.id"""
    ))
    if not rows:
        st.info("No unreviewed automatic Evaluation Result is available.")
        return
    by_id = {int(row["id"]): row for row in rows}
    result_id = st.selectbox(
        "Anonymous candidate for independent review",
        list(by_id),
        format_func=lambda value: str(by_id[value]["candidate_id"]),
    )
    try:
        packet = build_blind_human_review_packet_for_result(conn, result_id)
    except (LookupError, ValueError) as error:
        show_validation_errors([str(error)])
        return

    # This branch intentionally does not fetch or render automatic outcomes before submission.
    st.subheader("Copy-ready blind Human Review packet")
    st.code(str(packet["text"]), language="text")
    with st.form("submit_blind_human_review"):
        final_decision = st.selectbox("Independent final decision", ["pass", "fail", "indeterminate"])
        evidence = st.text_area("Independent review evidence")
        reason = st.text_area("Independent review reason")
        submitted = st.form_submit_button("Submit independent review")
    if not submitted:
        return
    try:
        record_human_review(
            conn,
            result_id,
            "manual",
            True,
            {"reviewer_evidence": evidence},
            reason,
            final_decision,
        )
    except (WorkflowError, LookupError, ValueError) as error:
        show_validation_errors([str(error)])
        return
    st.success("Saved independent Human Review without changing automatic evaluation.")
    _render_post_submission_comparison(conn, result_id)


def _render_post_submission_comparison(conn: sqlite3.Connection, evaluation_result_id: int) -> None:
    row = conn.execute(
        """SELECT er.calculated_status, hr.final_decision
        FROM evaluation_results AS er
        JOIN human_reviews AS hr ON hr.evaluation_result_id = er.id
        WHERE er.id = ?""",
        (evaluation_result_id,),
    ).fetchone()
    if row is None:
        return
    st.markdown("### Post-submission decision layers")
    st.caption(f"calculated_status: {row['calculated_status']}")
    st.caption(f"final_decision: {row['final_decision']}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
