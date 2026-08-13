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
    st.title("评测")
    mode = st.radio("评测模式", ["盲化 Grader 导入", "盲化人工复核"])
    if mode == "盲化 Grader 导入":
        _render_blind_grader_import(conn)
    else:
        _render_blind_human_review(conn)


def _render_blind_grader_import(conn: sqlite3.Connection) -> None:
    outputs = list_captured_model_outputs(conn)
    condition_ids = list_grader_condition_ids(conn)
    if not outputs or not condition_ids:
        st.info("导入前需要先有已采集的回答和 Grader 条件。")
        return
    output_by_id = {int(row["id"]): row for row in outputs}
    output_id = st.selectbox(
        "匿名候选", list(output_by_id),
        format_func=lambda value: str(output_by_id[value]["candidate_id"]),
    )
    condition_id = st.selectbox("Grader 条件", condition_ids, format_func=lambda value: f"条件 {value}")
    try:
        packet = build_blind_grader_packet_for_output(conn, output_id, condition_id)
    except (LookupError, ValueError) as error:
        show_validation_errors([str(error)])
        return
    st.subheader("可直接复制的盲化 Grader 任务包")
    st.code(str(packet["text"]), language="text")
    st.caption(f"盲化 Grader 任务包版本：{packet['packet_version']}")
    st.caption(f"盲化 Grader 任务包哈希：{packet['content_hash']}")
    with st.form("import_blind_grader_result"):
        raw_json = st.text_area("Grader 返回的 JSON", height=220)
        submitted = st.form_submit_button("导入 Grader JSON")
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
        st.success("已导入盲化 Grader 结果，并计算自动状态。")


def _render_blind_human_review(conn: sqlite3.Connection) -> None:
    rows = list_unreviewed_evaluation_results(conn)
    if not rows:
        st.info("暂无待人工复核的自动评测结果。")
        return
    by_id = {int(row["id"]): row for row in rows}
    result_id = st.selectbox(
        "待独立复核的匿名候选",
        list(by_id),
        format_func=lambda value: str(by_id[value]["candidate_id"]),
    )
    try:
        packet = build_blind_human_review_packet_for_result(conn, result_id)
    except (LookupError, ValueError) as error:
        show_validation_errors([str(error)])
        return

    # This branch intentionally does not fetch or render automatic outcomes before submission.
    st.subheader("可直接复制的盲化人工复核任务包")
    st.code(str(packet["text"]), language="text")
    with st.form("submit_blind_human_review"):
        final_decision = st.selectbox(
            "人工最终裁决",
            ["pass", "fail", "indeterminate"],
            format_func={
                "pass": "通过（pass）",
                "fail": "失败（fail）",
                "indeterminate": "无法确定（indeterminate）",
            }.get,
        )
        evidence = st.text_area("人工复核证据")
        reason = st.text_area("人工复核原因")
        submitted = st.form_submit_button("提交人工复核")
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
    st.success("已保存独立人工复核，不会修改自动评测结果。")
    _render_post_submission_comparison(conn, result_id)


def _render_post_submission_comparison(conn: sqlite3.Connection, evaluation_result_id: int) -> None:
    row = get_decision_layer_comparison(conn, evaluation_result_id)
    if row is None:
        return
    st.markdown("### 提交后的判定层")
    st.caption(f"calculated_status（自动计算）：{row['calculated_status']}")
    st.caption(f"final_decision（人工最终裁决）：{row['final_decision']}")
