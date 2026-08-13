from __future__ import annotations

import sqlite3

import streamlit as st

from eval_lab.analysis.reports import (
    failure_breakdown,
    review_coverage,
    run_summary,
    status_distribution,
)


def render(conn: sqlite3.Connection) -> None:
    st.title("Analysis")
    runs = list(conn.execute("SELECT id, comparison_group_id FROM evaluation_runs ORDER BY id"))
    if not runs:
        st.info("No Evaluation Runs are available for descriptive analysis.")
        return
    run_by_id = {int(row["id"]): row for row in runs}
    run_id = st.selectbox("Evaluation Run", list(run_by_id), format_func=lambda value: f"Run {value}")
    comparison_group_id = str(run_by_id[run_id]["comparison_group_id"])
    try:
        summary = run_summary(conn, run_id)
        statuses = status_distribution(conn, run_id)
        failures = failure_breakdown(conn, run_id)
        coverage = review_coverage(conn, comparison_group_id)
    except ValueError as error:
        st.info(f"Analysis is unavailable: {error}")
        return

    record = summary.iloc[0].to_dict()
    st.markdown("### Automatic calculated_status summary")
    first, second, third = st.columns(3)
    first.metric("Total cases", record["total_assigned"])
    second.metric("Determinate cases", record["determinate_count"])
    third.metric("Indeterminate rate", _percent(record["indeterminate_rate"]))
    st.caption(
        "determinate denominator: pass/fail automatic results only; "
        "indeterminate rate remains visible and is never silently excluded."
    )
    st.dataframe(summary, hide_index=True)

    st.markdown("### calculated_status and final_decision")
    st.dataframe(statuses, hide_index=True)
    st.markdown("### Human Review coverage")
    st.dataframe(coverage, hide_index=True)

    st.markdown("### Rule, required-fact, claim, error-type, and Bad Case diagnostics")
    for label, table in failures.items():
        with st.expander(label.replace("_", " ").title()):
            st.dataframe(table, hide_index=True)


def _percent(value: object) -> str:
    if value is None:
        return "not available"
    return f"{float(value):.1%}"
