from __future__ import annotations

from collections.abc import Sequence

import streamlit as st


def show_validation_errors(errors: Sequence[str]) -> None:
    """Show validation failures without silently changing external input."""
    for error in errors:
        st.error(f"操作未完成：{error}")


def status_badge(status: str | None) -> None:
    """Render a concise status label suitable for simple local metadata views."""
    st.caption(f"状态：{status or '未设置'}")
