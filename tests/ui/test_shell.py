from __future__ import annotations

from streamlit.testing.v1 import AppTest


def test_app_starts_with_official_metadata_navigation(monkeypatch, temporary_db_path, repo_root) -> None:
    """The local shell starts, initializes its database, and exposes approved pages."""
    monkeypatch.setenv("EVAL_LAB_DB_PATH", str(temporary_db_path))

    app = AppTest.from_file(repo_root / "app.py").run()

    assert not app.exception
    assert app.title[0].value == "AI Output Eval Lab"
    source = (repo_root / "app.py").read_text(encoding="utf-8")
    assert "st.navigation" in source
    for title in ("概览", "任务包", "测试用例", "Prompt 版本"):
        assert f'title="{title}"' in source
