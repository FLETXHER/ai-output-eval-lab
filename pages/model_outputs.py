from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import streamlit as st

from eval_lab.application.cases import load_case
from eval_lab.application.outputs import evaluate_output_rules, record_model_output
from eval_lab.application.packets import build_generation_packet
from eval_lab.application.prompts import WorkflowError
from eval_lab.ui.components import show_validation_errors


def render(conn: sqlite3.Connection) -> None:
    st.title("Model Outputs")
    context = _select_open_run_and_case(conn)
    if context is None:
        return
    run_id, case_id = context
    output = conn.execute(
        """SELECT id, raw_response, generation_packet_version, generation_packet_hash,
                  technical_retry_count, technical_retry_reasons_json
        FROM model_outputs WHERE evaluation_run_id = ? AND test_case_id = ?""",
        (run_id, case_id),
    ).fetchone()
    if output is not None and output["raw_response"] is not None:
        st.info("The first actual response is saved as immutable evidence.")
        st.caption(f"Generation packet version: {output['generation_packet_version']}")
        st.caption(f"Generation packet hash: {output['generation_packet_hash']}")
        st.code(str(output["raw_response"]), language="text")
        return
    try:
        packet = build_generation_packet(conn, run_id, case_id)
    except (LookupError, ValueError) as error:
        show_validation_errors([str(error)])
        return

    st.subheader("Copy-ready generation packet")
    st.code(str(packet["text"]), language="text")
    st.caption(f"Generation packet version: {packet['packet_version']}")
    st.caption(f"Generation packet hash: {packet['content_hash']}")

    _render_actual_response_form(conn, run_id, case_id, packet)
    _render_technical_retry_form(conn, run_id, case_id, packet, output)


def _select_open_run_and_case(conn: sqlite3.Connection) -> tuple[int, int] | None:
    runs = list(conn.execute(
        "SELECT id, split FROM evaluation_runs WHERE status = 'open' ORDER BY id"
    ))
    if not runs:
        st.info("No open Evaluation Run is available for model-output capture.")
        return None
    run_by_id = {int(run["id"]): run for run in runs}
    run_id = st.selectbox("Evaluation Run", list(run_by_id), format_func=lambda value: f"Run {value}")
    cases = list(conn.execute(
        "SELECT id, case_key, revision FROM test_cases WHERE split = ? ORDER BY case_key, revision",
        (run_by_id[run_id]["split"],),
    ))
    if not cases:
        st.info("The selected run has no Cases in its split.")
        return None
    case_by_id = {int(case["id"]): case for case in cases}
    case_id = st.selectbox(
        "Test Case",
        list(case_by_id),
        format_func=lambda value: f"{case_by_id[value]['case_key']} r{case_by_id[value]['revision']}",
    )
    return run_id, case_id


def _render_actual_response_form(
    conn: sqlite3.Connection, run_id: int, case_id: int, packet: dict[str, object]
) -> None:
    st.subheader("Record first actual response")
    with st.form("record_actual_model_response"):
        raw_response = st.text_area("Raw model response", height=180)
        generated_at = st.text_input("Generated at (UTC ISO 8601)", value=_utc_now())
        submitted = st.form_submit_button("Record actual response")
    if not submitted:
        return
    try:
        output_id = record_model_output(
            conn,
            run_id,
            case_id,
            str(packet["packet_version"]),
            str(packet["content_hash"]),
            raw_response,
            generated_at,
        )
        case = load_case(conn, case_id)
        evaluate_output_rules(
            conn,
            output_id,
            case["task_pack_contract"],
            case["explicit_forbidden_claims"],
        )
    except (WorkflowError, LookupError, ValueError) as error:
        show_validation_errors([str(error)])
    else:
        st.success("Saved the raw response and deterministic Rule Checks.")


def _render_technical_retry_form(
    conn: sqlite3.Connection,
    run_id: int,
    case_id: int,
    packet: dict[str, object],
    output: sqlite3.Row | None,
) -> None:
    retry_count = int(output["technical_retry_count"]) if output is not None else 0
    st.subheader("Record technical retry")
    st.caption(f"Technical retry count: {retry_count}. This is not an output-quality judgment.")
    with st.form("record_technical_retry"):
        reason = st.text_area("Technical retry reason")
        submitted = st.form_submit_button("Record technical retry")
    if not submitted:
        return
    try:
        record_model_output(
            conn,
            run_id,
            case_id,
            str(packet["packet_version"]),
            str(packet["content_hash"]),
            None,
            None,
            reason,
        )
    except (WorkflowError, LookupError, ValueError) as error:
        show_validation_errors([str(error)])
    else:
        st.success("Saved the technical retry separately from model-output quality.")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
