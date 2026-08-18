from __future__ import annotations

import sqlite3

import streamlit as st

from eval_lab.analysis.reports import (
    failure_breakdown,
    review_coverage,
    run_summary,
    status_distribution,
)
from eval_lab.application.ui_queries import list_analysis_runs


def render(conn: sqlite3.Connection) -> None:
    st.title("分析")
    runs = list_analysis_runs(conn)
    if not runs:
        st.info("暂无可用于描述性分析的评测运行。")
        return
    run_by_id = {int(row["id"]): row for row in runs}
    run_id = st.selectbox("评测运行", list(run_by_id), format_func=lambda value: f"Run {value}")
    comparison_group_id = str(run_by_id[run_id]["comparison_group_id"])
    try:
        summary = run_summary(conn, run_id)
        statuses = status_distribution(conn, run_id)
        failures = failure_breakdown(conn, run_id)
        coverage = review_coverage(conn, comparison_group_id)
    except ValueError as error:
        st.info(f"当前无法进行分析：{error}")
        return

    record = summary.iloc[0].to_dict()
    st.markdown("### 自动 calculated_status 汇总")
    first, second, third = st.columns(3)
    first.metric("测试用例总数", record["total_assigned"])
    second.metric("可确定结果数", record["determinate_count"])
    third.metric("indeterminate 比例", _percent(record["indeterminate_rate"]))
    st.caption(
        "可确定结果分母仅包含 pass/fail 自动结果；indeterminate 比例始终展示，不会被静默排除。"
    )
    st.dataframe(summary, hide_index=True)

    st.markdown(
        "### calculated_status、original_final_decision、corrected_final_decision 与 effective_final_decision"
    )
    st.dataframe(statuses, hide_index=True)
    st.markdown("### 人工复核覆盖率")
    st.dataframe(coverage, hide_index=True)

    st.markdown("### 规则、必需事实、声明、错误类型与 Bad Case 诊断")
    failure_labels = {
        "rule_failures": "规则失败",
        "required_fact_failures": "必需事实失败",
        "unsupported_claims": "不受支持的声明",
        "error_types": "错误类型",
        "bad_cases": "Bad Case",
    }
    for label, table in failures.items():
        with st.expander(failure_labels.get(label, label)):
            st.dataframe(table, hide_index=True)


def _percent(value: object) -> str:
    if value is None:
        return "暂无数据"
    return f"{float(value):.1%}"
