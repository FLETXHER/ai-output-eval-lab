from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from eval_lab.application.cases import register_approved_experiment_assets
from eval_lab.application.prompts import WorkflowError
from eval_lab.imports.test_cases import load_experiment_assets, validate_experiment_assets
from eval_lab.repositories.sqlite import connect, initialize_database


NOW = "2026-08-13T00:00:00Z"


@pytest.fixture
def conn(temporary_db_path: Path, repo_root: Path):
    connection = connect(temporary_db_path)
    initialize_database(connection, repo_root / "db" / "schema.sql")
    yield connection
    connection.close()


@pytest.fixture
def draft_assets(repo_root: Path) -> dict[str, object]:
    return json.loads(
        (repo_root / "db" / "seed_data" / "experiment_assets_v1.json").read_text(
            encoding="utf-8"
        )
    )


def _approved(payload: dict[str, object]) -> dict[str, object]:
    approved = deepcopy(payload)
    assets = approved["assets"]
    assert isinstance(assets, list)
    for asset in assets:
        assert isinstance(asset, dict)
        asset["status"] = "approved"
        asset["owner_approved_at"] = NOW
        content = asset["content"]
        assert isinstance(content, str)
        asset["content_hash"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return approved


def test_checked_in_assets_are_reproducible_drafts_not_formal(draft_assets) -> None:
    loaded = load_experiment_assets(
        Path(__file__).resolve().parents[2]
        / "db"
        / "seed_data"
        / "experiment_assets_v1.json"
    )
    assert loaded["ok"] is True
    assert validate_experiment_assets(draft_assets) == [
        "asset 'prompt_v1' must be owner-approved before formal registration",
        "asset 'grader_prompt_v1' must be owner-approved before formal registration",
        "asset 'rubric_v1' must be owner-approved before formal registration",
        "asset 'error_taxonomy_v1' must be owner-approved before formal registration",
    ]


def test_draft_assets_capture_the_full_blind_grader_contract_and_methodology(
    draft_assets: dict[str, object],
) -> None:
    by_type = {asset["asset_type"]: asset for asset in draft_assets["assets"]}
    grader_prompt = by_type["grader_prompt_v1"]["content"]
    rubric = by_type["rubric_v1"]["content"]
    taxonomy = by_type["error_taxonomy_v1"]["content"]
    assert "language_compliance" in grader_prompt
    assert "required_facts" in grader_prompt
    assert "unsupported_claims" in grader_prompt
    assert "readability" in grader_prompt
    assert "primary_error_type" in grader_prompt
    assert "secondary_error_types" in grader_prompt
    assert "grader_reason" in grader_prompt
    assert "只能包含" in grader_prompt
    assert "not_met 或 indeterminate" in grader_prompt
    assert "source_facts 中存在的 fact_id" in grader_prompt
    assert "source_material 是唯一事实来源" in rubric
    assert "同义改写" in rubric and "合并表达" in rubric
    assert "source 未表达某事实不等于 source 表达了该事实的否定" in rubric
    assert "因果关系" in rubric and "比较关系" in rubric and "程度或性能" in rubric
    assert "unsupported_claim > required_fact_missing" in taxonomy
    assert "secondary_error_types 不得包含 primary_error_type" in taxonomy
    assert "不替代 deterministic schema" in taxonomy


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda payload: payload.__setitem__("assets", payload["assets"][:-1]), "missing required asset types"),
        (
            lambda payload: payload["assets"][0].pop("version_label"),
            "missing required keys",
        ),
        (
            lambda payload: payload["assets"][0].__setitem__("content_hash", "0" * 64),
            "content_hash does not match content",
        ),
        (
            lambda payload: payload["assets"][0].__setitem__("version_label", "v2"),
            "must use version_label 'v1'",
        ),
    ],
)
def test_asset_validation_rejects_incomplete_or_non_v1_manifest(
    draft_assets: dict[str, object], mutate, expected: str
) -> None:
    payload = deepcopy(draft_assets)
    mutate(payload)
    assert any(expected in error for error in validate_experiment_assets(payload))


def test_only_owner_approved_v1_assets_can_register_formal_snapshots(
    conn: sqlite3.Connection, draft_assets: dict[str, object]
) -> None:
    with pytest.raises(WorkflowError, match="owner-approved"):
        register_approved_experiment_assets(conn, draft_assets)
    assert conn.execute("SELECT COUNT(*) FROM prompt_versions").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM grader_conditions").fetchone()[0] == 0

    registered = register_approved_experiment_assets(conn, _approved(draft_assets))
    assert set(registered) == {"prompt_version_id", "grader_condition_id"}
    prompt = conn.execute(
        "SELECT * FROM prompt_versions WHERE id = ?", (registered["prompt_version_id"],)
    ).fetchone()
    condition = conn.execute(
        "SELECT * FROM grader_conditions WHERE id = ?", (registered["grader_condition_id"],)
    ).fetchone()
    assert prompt["version_label"] == "v1"
    assert prompt["status"] == "frozen"
    assert prompt["owner_approved_at"] == NOW
    assert condition["owner_approved_at"] == NOW

    by_type = {asset["asset_type"]: asset for asset in _approved(draft_assets)["assets"]}
    assert prompt["prompt_text"] == by_type["prompt_v1"]["content"]
    assert prompt["content_hash"] == by_type["prompt_v1"]["content_hash"]
    assert condition["grader_prompt"] == by_type["grader_prompt_v1"]["content"]
    assert condition["grader_prompt_hash"] == by_type["grader_prompt_v1"]["content_hash"]
    assert condition["rubric"] == by_type["rubric_v1"]["content"]
    assert condition["rubric_hash"] == by_type["rubric_v1"]["content_hash"]
    assert condition["error_taxonomy"] == by_type["error_taxonomy_v1"]["content"]
    assert condition["error_taxonomy_hash"] == by_type["error_taxonomy_v1"]["content_hash"]
