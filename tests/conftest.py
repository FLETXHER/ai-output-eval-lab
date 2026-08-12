from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def temporary_db_path(tmp_path: Path) -> Path:
    return tmp_path / "eval_lab.sqlite3"
