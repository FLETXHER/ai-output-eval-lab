from __future__ import annotations

import json
import sqlite3

import pandas as pd
import streamlit as st

from eval_lab.repositories.sqlite import list_task_packs, list_test_cases


def render(conn: sqlite3.Connection) -> None:
    st.title("测试用例")
    packs = list_task_packs(conn)
    if not packs:
        st.info("请先创建固定任务包记录，再添加或查看测试用例。")
        return

    pack_names = {int(pack["id"]): str(pack["pack_key"]) for pack in packs}
    selected_pack_id = st.selectbox(
        "任务包", list(pack_names), format_func=lambda pack_id: pack_names[pack_id]
    )
    split = st.selectbox(
        "数据集切分",
        ["all", "dev", "holdout"],
        format_func={"all": "全部", "dev": "Dev", "holdout": "Holdout"}.get,
    )
    selected_split = None if split == "all" else split
    cases = list_test_cases(conn, selected_pack_id, selected_split)
    if not cases:
        st.info("没有匹配的测试用例。")
        return

    table_rows = []
    for case in cases:
        table_rows.append(
            {
                "case_key": case["case_key"],
                "revision": case["revision"],
                "split": case["split"],
                "required_fact_ids": ", ".join(json.loads(case["required_fact_ids_json"])),
                "feasibility_qa_status": case["feasibility_qa_status"],
            }
        )
    st.dataframe(pd.DataFrame(table_rows), hide_index=True)
