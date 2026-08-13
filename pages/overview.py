from __future__ import annotations

import sqlite3

import streamlit as st

from eval_lab.repositories.sqlite import metadata_counts


def render(conn: sqlite3.Connection) -> None:
    st.title("Overview")
    counts = metadata_counts(conn)
    first, second, third = st.columns(3)
    first.metric("Task Packs", counts["task_packs"])
    second.metric("Test Cases", counts["test_cases"])
    third.metric("Prompt Versions", counts["prompt_versions"])
    st.caption("This local MVP records reusable Prompt experiments; it does not run models automatically.")
