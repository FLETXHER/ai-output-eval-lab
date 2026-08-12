from __future__ import annotations

from copy import deepcopy

from eval_lab.domain.task_pack import (
    CONTRACT_VERSION,
    TASK_PACK_CONTRACT,
    TASK_PACK_KEY,
    canonical_json_hash,
    validate_case_record,
    validate_task_pack_contract,
)


def valid_case() -> dict[str, object]:
    return {
        "case_key": "case-001",
        "revision": 1,
        "split": "dev",
        "source_material": "星河计划将于9月1日启动，并在北京举行发布会。",
        "source_facts": [
            {"fact_id": "F01", "text": "星河计划将于9月1日启动"},
            {"fact_id": "F02", "text": "在北京举行发布会"},
        ],
        "required_fact_ids": ["F01"],
        "explicit_forbidden_claims": ["全球首发"],
        "feasibility_qa_status": "pending",
    }


def test_fixed_task_pack_contract_has_expected_identity_and_stable_hash() -> None:
    assert TASK_PACK_KEY == "grounded_structured_brief_generation"
    assert CONTRACT_VERSION == "1.0"
    assert TASK_PACK_CONTRACT["pack_key"] == TASK_PACK_KEY
    assert TASK_PACK_CONTRACT["contract_version"] == CONTRACT_VERSION
    assert TASK_PACK_CONTRACT["language"] == "zh-CN"
    assert validate_task_pack_contract(TASK_PACK_CONTRACT) == []
    assert (
        canonical_json_hash(TASK_PACK_CONTRACT)
        == "ae273822b78d16cba4df5d784d611313f788353229d1b95166047cc1254a2c59"
    )


def test_contract_rejects_changed_length_or_language() -> None:
    invalid = deepcopy(TASK_PACK_CONTRACT)
    invalid["language"] = "en-US"
    invalid["title_min_chars"] = 3

    errors = validate_task_pack_contract(invalid)

    assert "language must be 'zh-CN'" in errors
    assert "title_min_chars must be 4" in errors


def test_case_record_accepts_traceable_facts_and_required_subset() -> None:
    assert validate_case_record(valid_case()) == []


def test_case_record_rejects_missing_or_duplicate_fact_ids() -> None:
    missing_id = valid_case()
    missing_id["source_facts"] = [{"text": "星河计划将于9月1日启动"}]
    duplicate_id = valid_case()
    duplicate_id["source_facts"] = [
        {"fact_id": "F01", "text": "星河计划将于9月1日启动"},
        {"fact_id": "F01", "text": "在北京举行发布会"},
    ]

    assert "source_facts[0].fact_id must be a non-empty string" in validate_case_record(
        missing_id
    )
    assert "source_facts fact_id values must be unique" in validate_case_record(duplicate_id)


def test_case_record_rejects_required_id_outside_source_facts() -> None:
    case = valid_case()
    case["required_fact_ids"] = ["F03"]

    assert "required_fact_ids must be a subset of source_facts fact_id values" in validate_case_record(
        case
    )


def test_case_record_requires_nonempty_source_and_traceable_fact_text() -> None:
    empty_source = valid_case()
    empty_source["source_material"] = "  \n"
    untraceable_fact = valid_case()
    untraceable_fact["source_facts"] = [{"fact_id": "F01", "text": "上海发布会"}]

    assert "source_material must be a non-empty string" in validate_case_record(empty_source)
    assert "source_facts[0].text must appear in source_material" in validate_case_record(
        untraceable_fact
    )


def test_case_record_rejects_invalid_split_and_feasibility_status() -> None:
    case = valid_case()
    case["split"] = "test"
    case["feasibility_qa_status"] = "approved"

    errors = validate_case_record(case)

    assert "split must be 'dev' or 'holdout'" in errors
    assert "feasibility_qa_status must be 'pending', 'pass', or 'fail'" in errors
