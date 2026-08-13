from __future__ import annotations

import sqlite3

import streamlit as st

from eval_lab.application.grading import (
    build_blind_grader_packet_for_output,
    calculate_output_status,
    import_grader_result_text,
)
from eval_lab.application.prompts import WorkflowError
from eval_lab.application.reviews import (
    build_blind_human_review_packet_for_result,
    record_human_review,
)
from eval_lab.application.ui_queries import (
    get_decision_layer_comparison,
    get_grader_condition,
    list_captured_model_outputs,
    list_grader_condition_ids,
    list_unreviewed_evaluation_results,
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
    outputs = list_captured_model_outputs(conn)
    condition_ids = list_grader_condition_ids(conn)
    if not outputs or not condition_ids:
        st.info("A captured response and a Grader Condition are required before import.")
        return
    output_by_id = {int(row["id"]): row for row in outputs}
    output_id = st.selectbox(
        "Anonymous candidate", list(output_by_id),
        format_func=lambda value: str(output_by_id[value]["candidate_id"]),
    )
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
        condition = get_grader_condition(conn, condition_id)
        if condition is None:
            raise WorkflowError("grader condition was not found")
        grader_result_id = import_grader_result_text(conn, output_id, dict(condition), raw_json)
        calculate_output_status(conn, output_id, grader_result_id, condition_id)
    except (WorkflowError, LookupError, ValueError, TypeError) as error:
        show_validation_errors([str(error)])
    else:
        st.success("Imported the blind Grader result and calculated automatic status.")


def _render_blind_human_review(conn: sqlite3.Connection) -> None:
    rows = list_unreviewed_evaluation_results(conn)
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
    row = get_decision_layer_comparison(conn, evaluation_result_id)
    if row is None:
        return
    st.markdown("### Post-submission decision layers")
    st.caption(f"calculated_status: {row['calculated_status']}")
    st.caption(f"final_decision: {row['final_decision']}")
