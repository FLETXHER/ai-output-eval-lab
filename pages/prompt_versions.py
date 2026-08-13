from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from eval_lab.application.prompts import (
    WorkflowError,
    approve_prompt_version,
    create_prompt_version,
    freeze_prompt_version,
)
from eval_lab.repositories.sqlite import list_prompt_versions
from eval_lab.ui.components import show_validation_errors, status_badge


def render(conn: sqlite3.Connection) -> None:
    st.title("Prompt Versions")
    _render_create_form(conn)
    st.divider()
    _render_existing_versions(conn)


def _render_create_form(conn: sqlite3.Connection) -> None:
    st.subheader("Create Prompt Version")
    with st.form("create_prompt_version"):
        version_label = st.text_input("Version label")
        prompt_text = st.text_area("Prompt text")
        change_reason = st.text_area("Change reason")
        submitted = st.form_submit_button("Create Prompt Version")
    if not submitted:
        return
    try:
        prompt_id = create_prompt_version(conn, prompt_text, version_label, change_reason)
    except WorkflowError as error:
        show_validation_errors([str(error)])
    else:
        st.success(f"Created Prompt {version_label}.")
        st.caption(f"Prompt record ID: {prompt_id}")


def _render_existing_versions(conn: sqlite3.Connection) -> None:
    prompts = list_prompt_versions(conn)
    if not prompts:
        st.info("No Prompt Versions yet.")
        return

    table = pd.DataFrame(
        [
            {
                "version_label": prompt["version_label"],
                "status": prompt["status"],
                "change_reason": prompt["change_reason"],
                "content_hash": prompt["content_hash"],
                "owner_approved_at": prompt["owner_approved_at"],
                "frozen_at": prompt["frozen_at"],
            }
            for prompt in prompts
        ]
    )
    st.dataframe(table, hide_index=True)
    prompt_by_label = {str(prompt["version_label"]): prompt for prompt in prompts}
    selected_label = st.selectbox("Select Prompt Version", list(prompt_by_label))
    selected = prompt_by_label[selected_label]
    st.code(str(selected["prompt_text"]), language=None)
    status_badge(str(selected["status"]))
    if selected["status"] == "draft":
        if selected["owner_approved_at"] is None:
            if st.button("Record owner approval"):
                try:
                    approve_prompt_version(conn, int(selected["id"]), _utc_now())
                except WorkflowError as error:
                    show_validation_errors([str(error)])
                else:
                    st.success(f"Recorded owner approval for Prompt {selected['version_label']}.")
            st.info("Owner approval must be recorded before this Prompt can be frozen.")
            return
        if st.button("Freeze selected Prompt"):
            try:
                freeze_prompt_version(conn, int(selected["id"]), _utc_now())
            except WorkflowError as error:
                show_validation_errors([str(error)])
            else:
                st.success(f"Frozen Prompt {selected['version_label']}.")
    else:
        st.info("Frozen Prompt text is immutable. Create a new draft for any change.")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
