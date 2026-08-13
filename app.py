from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from eval_lab.repositories.sqlite import connect, initialize_database, table_names
from pages.overview import render as render_overview
from pages.prompt_versions import render as render_prompt_versions
from pages.task_pack import render as render_task_pack
from pages.test_cases import render as render_test_cases


st.set_page_config(page_title="AI Output Eval Lab", layout="wide")
_APP_ROOT = Path(__file__).resolve().parent


def _database_path() -> Path:
    configured = os.environ.get("EVAL_LAB_DB_PATH")
    return Path(configured) if configured else _APP_ROOT / "db" / "eval_lab.sqlite3"


def _open_database() -> object:
    db_path = _database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    if not table_names(conn):
        initialize_database(conn, _APP_ROOT / "db" / "schema.sql")
    return conn


def main() -> None:
    conn = _open_database()
    st.title("AI Output Eval Lab")
    st.caption("Prompt evaluation workbench")

    def overview_page() -> None:
        render_overview(conn)

    def task_packs_page() -> None:
        render_task_pack(conn)

    def test_cases_page() -> None:
        render_test_cases(conn)

    def prompt_versions_page() -> None:
        render_prompt_versions(conn)

    navigation = st.navigation(
        [
            st.Page(overview_page, title="Overview"),
            st.Page(task_packs_page, title="Task Packs"),
            st.Page(test_cases_page, title="Test Cases"),
            st.Page(prompt_versions_page, title="Prompt Versions"),
        ]
    )
    navigation.run()


main()
