from __future__ import annotations

import hashlib
import json
import sqlite3

from streamlit.testing.v1 import AppTest

from eval_lab.domain.task_pack import TASK_PACK_CONTRACT, canonical_json_hash
from eval_lab.repositories.sqlite import (
    connect,
    initialize_database,
    insert_task_pack,
    insert_test_case,
)


NOW = "2026-08-13T00:00:00Z"


def _page_test(page_module: str, db_path: str, repo_root: str) -> AppTest:
    source = f"""
import sqlite3
import sys
sys.path.insert(0, {repo_root!r})
from {page_module} import render
conn = sqlite3.connect({db_path!r})
conn.row_factory = sqlite3.Row
conn.execute('PRAGMA foreign_keys = ON')
render(conn)
"""
    return AppTest.from_string(source).run()


def _seed_metadata(db_path, repo_root) -> int:
    conn = connect(db_path)
    initialize_database(conn, repo_root / "db" / "schema.sql")
    task_pack_id = insert_task_pack(
        conn,
        {
            "pack_key": TASK_PACK_CONTRACT["pack_key"],
            "contract_version": TASK_PACK_CONTRACT["contract_version"],
            "contract_hash": canonical_json_hash(TASK_PACK_CONTRACT),
            "language": TASK_PACK_CONTRACT["language"],
            "title_min_chars": TASK_PACK_CONTRACT["title_min_chars"],
            "title_max_chars": TASK_PACK_CONTRACT["title_max_chars"],
            "summary_min_chars": TASK_PACK_CONTRACT["summary_min_chars"],
            "summary_max_chars": TASK_PACK_CONTRACT["summary_max_chars"],
            "key_points_count": TASK_PACK_CONTRACT["key_points_count"],
            "key_point_min_chars": TASK_PACK_CONTRACT["key_point_min_chars"],
            "key_point_max_chars": TASK_PACK_CONTRACT["key_point_max_chars"],
            "created_at": NOW,
            "updated_at": NOW,
        },
    )
    for case_key, split in (("case-dev", "dev"), ("case-holdout", "holdout")):
        source_material = "产品重量为120克，包装包含USB-C充电线。"
        source_facts = [
            {"fact_id": "F01", "text": "重量为120克"},
            {"fact_id": "F02", "text": "包装包含USB-C充电线"},
        ]
        insert_test_case(
            conn,
            {
                "task_pack_id": task_pack_id,
                "case_key": case_key,
                "revision": 1,
                "split": split,
                "source_material": source_material,
                "source_facts": source_facts,
                "required_fact_ids": ["F01"],
                "explicit_forbidden_claims": [],
                "task_notes": "必须包含重量。",
                "feasibility_qa_status": "pass",
                "content_hash": hashlib.sha256(case_key.encode()).hexdigest(),
                "created_at": NOW,
                "updated_at": NOW,
            },
        )
    conn.close()
    return task_pack_id


def test_overview_and_task_pack_show_counts_and_fixed_contract(temporary_db_path, repo_root) -> None:
    _seed_metadata(temporary_db_path, repo_root)

    overview = _page_test("pages.overview", str(temporary_db_path), str(repo_root))
    assert not overview.exception
    assert [(metric.label, metric.value) for metric in overview.metric] == [
        ("Task Packs", "1"),
        ("Test Cases", "2"),
        ("Prompt Versions", "0"),
    ]

    packs = _page_test("pages.task_pack", str(temporary_db_path), str(repo_root))
    assert not packs.exception
    assert packs.title[0].value == "Task Packs"
    assert packs.dataframe[0].value.iloc[0]["pack_key"] == TASK_PACK_CONTRACT["pack_key"]
    assert any("4–20" in item.value for item in packs.markdown)
    assert any("feasibility QA" in item.value for item in packs.markdown)


def test_task_pack_empty_state_still_shows_fixed_contract_and_qa(temporary_db_path, repo_root) -> None:
    conn = connect(temporary_db_path)
    initialize_database(conn, repo_root / "db" / "schema.sql")
    conn.close()

    packs = _page_test("pages.task_pack", str(temporary_db_path), str(repo_root))

    assert not packs.exception
    assert packs.info[0].value == "No Task Pack has been initialized yet."
    assert any("4–20" in item.value for item in packs.markdown)
    assert any("feasibility QA" in item.value for item in packs.markdown)


def test_test_case_split_filter_and_prompt_lifecycle_in_ui(temporary_db_path, repo_root) -> None:
    _seed_metadata(temporary_db_path, repo_root)

    cases = _page_test("pages.test_cases", str(temporary_db_path), str(repo_root))
    assert not cases.exception
    cases.selectbox[1].select("holdout").run()
    assert len(cases.dataframe[0].value.index) == 1
    assert cases.dataframe[0].value.iloc[0]["case_key"] == "case-holdout"

    prompts = _page_test("pages.prompt_versions", str(temporary_db_path), str(repo_root))
    assert not prompts.exception
    prompts.text_input[0].set_value("v1")
    prompts.text_area[0].set_value("根据材料生成 JSON")
    prompts.text_area[1].set_value("baseline")
    prompts.button[0].click().run()
    assert not prompts.exception
    assert prompts.success[0].value == "Created Prompt v1."

    conn = connect(temporary_db_path)
    row = conn.execute("SELECT id, prompt_text, status FROM prompt_versions WHERE version_label = 'v1'").fetchone()
    assert tuple(row) == (1, "根据材料生成 JSON", "draft")
    conn.close()

    prompts = _page_test("pages.prompt_versions", str(temporary_db_path), str(repo_root))
    prompts.selectbox[0].select("v1")
    prompts.button[1].click().run()
    conn = connect(temporary_db_path)
    frozen = conn.execute("SELECT prompt_text, status, frozen_at FROM prompt_versions WHERE id = 1").fetchone()
    assert frozen[0] == "根据材料生成 JSON"
    assert frozen[1] == "frozen"
    assert frozen[2]
    conn.close()


def test_invalid_prompt_form_shows_error_and_does_not_save(temporary_db_path, repo_root) -> None:
    _seed_metadata(temporary_db_path, repo_root)

    prompts = _page_test("pages.prompt_versions", str(temporary_db_path), str(repo_root))
    prompts.button[0].click().run()

    assert not prompts.exception
    assert prompts.error[0].value.endswith("must be a non-empty string")
    conn = connect(temporary_db_path)
    assert conn.execute("SELECT COUNT(*) FROM prompt_versions").fetchone()[0] == 0
    conn.close()
