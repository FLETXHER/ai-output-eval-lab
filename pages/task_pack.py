from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from eval_lab.repositories.sqlite import list_task_packs
from eval_lab.ui.components import status_badge


def render(conn: sqlite3.Connection) -> None:
    st.title("任务包")
    st.markdown(
        "**固定 MVP 合同：** `title` 4–20 个字符；`summary` 60–120 个字符；"
        "`key_points` 必须恰好 3 条，每条 6–40 个字符。"
    )
    st.markdown(
        "**数据集 QA：** 每个测试用例进入正式 Dev 或 Holdout 集合前，都必须完成可行性 QA。"
    )
    status_badge("固定合同")
    packs = list_task_packs(conn)
    if not packs:
        st.info("尚未初始化任务包。")
        return

    st.dataframe(pd.DataFrame([dict(pack) for pack in packs]), hide_index=True)
