from __future__ import annotations

import sqlite3

import streamlit as st

from eval_lab.repositories.sqlite import metadata_counts


def render(conn: sqlite3.Connection) -> None:
    st.title("概览")
    counts = metadata_counts(conn)
    first, second, third = st.columns(3)
    first.metric("任务包", counts["task_packs"])
    second.metric("测试用例", counts["test_cases"])
    third.metric("Prompt 版本", counts["prompt_versions"])
    st.caption("这是一个本地 MVP，用于记录可复用的 Prompt 实验；不会自动调用模型。")
