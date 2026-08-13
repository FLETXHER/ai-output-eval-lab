from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from eval_lab.repositories.sqlite import list_task_packs
from eval_lab.ui.components import status_badge


def render(conn: sqlite3.Connection) -> None:
    st.title("Task Packs")
    packs = list_task_packs(conn)
    if not packs:
        st.info("No Task Pack has been initialized yet.")
        return

    st.dataframe(pd.DataFrame([dict(pack) for pack in packs]), hide_index=True)
    st.markdown("**Fixed MVP contract:** `title` 4–20 characters; `summary` 60–120 characters; exactly 3 `key_points`, each 6–40 characters.")
    st.markdown("**Dataset QA:** every Case must receive feasibility QA before it enters the formal Dev or Holdout set.")
    status_badge("fixed contract")
