from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import streamlit as st

from eval_lab.application.cases import load_case
from eval_lab.application.outputs import evaluate_output_rules, record_model_output
from eval_lab.application.packets import build_generation_packet
from eval_lab.application.prompts import WorkflowError
from eval_lab.application.runs import record_generator_visible_model
from eval_lab.application.ui_queries import (
    get_open_run_capture_context,
    get_model_output_slot,
    list_open_evaluation_runs,
    list_test_cases_for_split,
)
from eval_lab.ui.components import show_validation_errors


def render(conn: sqlite3.Connection) -> None:
    st.title("模型输出")
    context = _select_open_run_and_case(conn)
    if context is None:
        return
    run_id, case_id = context
    if not _render_generator_condition_control(conn, run_id):
        return
    output = get_model_output_slot(conn, run_id, case_id)
    if output is not None and output["raw_response"] is not None:
        st.info("第一条实际回答已作为不可变证据保存。")
        st.caption(f"生成任务包版本：{output['generation_packet_version']}")
        st.caption(f"生成任务包哈希：{output['generation_packet_hash']}")
        st.code(str(output["raw_response"]), language="text")
        return
    try:
        packet = build_generation_packet(conn, run_id, case_id)
    except (LookupError, ValueError) as error:
        show_validation_errors([str(error)])
        return

    st.subheader("可直接复制的生成任务包")
    st.code(str(packet["text"]), language="text")
    st.caption(f"生成任务包版本：{packet['packet_version']}")
    st.caption(f"生成任务包哈希：{packet['content_hash']}")

    _render_actual_response_form(conn, run_id, case_id, packet)
    _render_technical_retry_form(conn, run_id, case_id, packet, output)


def _render_generator_condition_control(conn: sqlite3.Connection, run_id: int) -> bool:
    run = get_open_run_capture_context(conn, run_id)
    if run is None or run["split"] != "dev":
        return True
    output_count = int(run["model_output_count"])
    if output_count or run["generator_visible_model"] != "not_visible":
        return True

    st.subheader("正式采集前确认生成模型条件")
    st.caption("记录第一条回答前，请确认 not_visible，或填写生成产品界面显示的准确模型名称。")
    with st.form("record_generator_visible_model"):
        visible_model = st.text_input("可见模型（只有界面未显示模型名称时才保留 not_visible）", value="not_visible")
        submitted = st.form_submit_button("确认生成模型条件")
    if not submitted:
        return False
    try:
        recorded = record_generator_visible_model(conn, run_id, visible_model)
    except (WorkflowError, LookupError, ValueError) as error:
        show_validation_errors([str(error)])
        return False
    st.success(f"已记录生成模型条件：{recorded}")
    return True


def _select_open_run_and_case(conn: sqlite3.Connection) -> tuple[int, int] | None:
    runs = list_open_evaluation_runs(conn)
    if not runs:
        st.info("没有可用于采集模型输出的开放评测运行。")
        return None
    run_by_id = {int(run["id"]): run for run in runs}
    run_id = st.selectbox("评测运行", list(run_by_id), format_func=lambda value: f"Run {value}")
    cases = list_test_cases_for_split(conn, str(run_by_id[run_id]["split"]))
    if not cases:
        st.info("当前运行的切分中没有测试用例。")
        return None
    case_by_id = {int(case["id"]): case for case in cases}
    case_id = st.selectbox(
        "测试用例",
        list(case_by_id),
        format_func=lambda value: f"{case_by_id[value]['case_key']} r{case_by_id[value]['revision']}",
    )
    return run_id, case_id


def _render_actual_response_form(
    conn: sqlite3.Connection, run_id: int, case_id: int, packet: dict[str, object]
) -> None:
    st.subheader("记录第一条实际回答")
    st.caption("如果没有生成实际回答，请不要提交空回答，改用下面的技术故障重试记录。")
    with st.form("record_actual_model_response"):
        raw_response = st.text_area("模型原始回答", height=180)
        generated_at = st.text_input("生成时间（UTC ISO 8601）", value=_utc_now())
        submitted = st.form_submit_button("保存实际回答")
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
        st.success("已保存模型原始回答，并完成确定性规则检查。")


def _render_technical_retry_form(
    conn: sqlite3.Connection,
    run_id: int,
    case_id: int,
    packet: dict[str, object],
    output: sqlite3.Row | None,
) -> None:
    retry_count = int(output["technical_retry_count"]) if output is not None else 0
    st.subheader("记录技术故障重试")
    st.caption(f"技术故障重试次数：{retry_count}。这不属于输出质量判定。")
    with st.form("record_technical_retry"):
        reason = st.text_area("技术故障重试原因")
        submitted = st.form_submit_button("保存技术故障重试")
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
        st.success("已单独保存技术故障重试记录，不计入模型输出质量。")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
