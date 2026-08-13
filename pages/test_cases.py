from __future__ import annotations

import json
import sqlite3

import pandas as pd
import streamlit as st

from eval_lab.repositories.sqlite import list_task_packs, list_test_cases


def render(conn: sqlite3.Connection) -> None:
    st.title("Test Cases")
    packs = list_task_packs(conn)
    if not packs:
        st.info("Create the fixed Task Pack record before adding or viewing Cases.")
        return

    pack_names = {int(pack["id"]): str(pack["pack_key"]) for pack in packs}
    selected_pack_id = st.selectbox(
        "Task Pack", list(pack_names), format_func=lambda pack_id: pack_names[pack_id]
    )
    split = st.selectbox("Split", ["all", "dev", "holdout"])
    selected_split = None if split == "all" else split
    cases = list_test_cases(conn, selected_pack_id, selected_split)
    if not cases:
        st.info("No matching Test Cases.")
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
