from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from eval_lab.application.cases import compute_case_set_hash, qa_case_set
from eval_lab.domain.task_pack import TASK_PACK_CONTRACT, canonical_json_hash
from eval_lab.imports.test_cases import load_task_pack_seed, load_test_case_seed


def _task_pack() -> dict[str, object]:
    contract = dict(TASK_PACK_CONTRACT)
    return {**contract, "contract_hash": canonical_json_hash(contract)}


def _case(index: int, split: str = "dev") -> dict[str, object]:
    source_material = f"星河随身灯{index}号重量为{index}20克，包装内含USB-C充电线。"
    source_facts = [
        {"fact_id": "F01", "text": f"重量为{index}20克"},
        {"fact_id": "F02", "text": "包装内含USB-C充电线"},
    ]
    case_without_hash = {
        "case_key": f"brief-{index:03d}",
        "revision": 1,
        "split": split,
        "source_material": source_material,
        "source_facts": source_facts,
        "required_fact_ids": ["F01"],
        "explicit_forbidden_claims": [],
        "task_notes": "请生成结构化短内容，必须包含重量。",
        "feasibility_qa_status": "pass",
        "traceability_metadata": {
            "source_of_truth": "source_material",
            "source_facts_traceable": True,
        },
        "contract_hash": canonical_json_hash(TASK_PACK_CONTRACT),
    }
    return {**case_without_hash, "content_hash": canonical_json_hash(case_without_hash)}


def test_checked_in_seed_files_are_valid_but_explicitly_non_final(repo_root: Path) -> None:
    task_pack = load_task_pack_seed(repo_root / "db" / "seed_data" / "task_pack.json")
    cases = load_test_case_seed(repo_root / "db" / "seed_data" / "test_cases.json")

    assert task_pack["ok"] is True
    assert cases == {"ok": True, "value": [], "errors": [], "raw_text": None}

    result = qa_case_set(cases["value"], task_pack["value"])

    assert result["total_cases"] == 0
    assert result["formal_ready"] is False
    assert any("exactly 24" in error for error in result["errors"])


def test_formal_ready_requires_valid_18_dev_6_holdout_set_and_shared_contract() -> None:
    task_pack = _task_pack()
    cases = [_case(index, "dev" if index <= 18 else "holdout") for index in range(1, 25)]

    result = qa_case_set(cases, task_pack)

    assert result["errors"] == []
    assert result["formal_ready"] is True
    assert result["total_cases"] == 24
    assert result["dev_cases"] == 18
    assert result["holdout_cases"] == 6

    cases[0]["contract_hash"] = "0" * 64
    mismatch = qa_case_set(cases, task_pack)
    assert mismatch["formal_ready"] is False
    assert any("contract_hash" in error for error in mismatch["errors"])


def test_qa_rejects_duplicate_revisions_unreviewed_cases_and_invalid_traceability() -> None:
    task_pack = _task_pack()
    first = _case(1)
    duplicate = deepcopy(first)
    pending = _case(2)
    pending["feasibility_qa_status"] = "pending"
    untraceable = _case(3)
    untraceable["traceability_metadata"] = {
        "source_of_truth": "source_facts",
        "source_facts_traceable": False,
    }

    result = qa_case_set([first, duplicate, pending, untraceable], task_pack)

    assert result["formal_ready"] is False
    assert any("duplicate case_key/revision" in error for error in result["errors"])
    assert any("feasibility_qa_status must be 'pass'" in error for error in result["errors"])
    assert any("source_of_truth" in error for error in result["errors"])


def test_case_set_hash_is_deterministic_across_input_order_and_qa_is_pure(tmp_path: Path) -> None:
    task_pack = _task_pack()
    first = _case(1)
    second = _case(2)
    missing_db = tmp_path / "qa-must-not-write.sqlite"

    assert compute_case_set_hash([first, second]) == compute_case_set_hash([second, first])
    result = qa_case_set([second, first], task_pack)

    assert result["case_set_hash"] == compute_case_set_hash([first, second])
    assert missing_db.exists() is False


def test_qa_reports_non_object_cases_instead_of_crashing() -> None:
    result = qa_case_set(["not-a-case"], _task_pack())

    assert result["formal_ready"] is False
    assert "case[0] must be an object" in result["errors"]


def test_qa_rejects_non_string_or_blank_task_notes() -> None:
    numeric_notes = _case(1)
    numeric_notes["task_notes"] = 42
    blank_notes = _case(2)
    blank_notes["task_notes"] = "  "

    result = qa_case_set([numeric_notes, blank_notes], _task_pack())

    assert result["formal_ready"] is False
    assert "case[0]: task_notes must be a non-empty string" in result["errors"]
    assert "case[1]: task_notes must be a non-empty string" in result["errors"]
