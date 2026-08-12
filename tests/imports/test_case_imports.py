from eval_lab.domain.task_pack import TASK_PACK_CONTRACT
from eval_lab.imports.test_cases import (
    parse_json_text,
    parse_task_pack_payload,
    parse_test_case_payload,
)


def _valid_case() -> dict[str, object]:
    return {
        "case_key": "brief-001",
        "revision": 1,
        "split": "dev",
        "source_material": "青岚公司在2026年8月发布了云雀智能灯。",
        "source_facts": [
            {"fact_id": "F01", "text": "青岚公司在2026年8月发布了云雀智能灯。"}
        ],
        "required_fact_ids": ["F01"],
        "explicit_forbidden_claims": [],
        "task_notes": "必须说明发布时间。",
        "feasibility_qa_status": "pending",
    }


def test_parse_json_text_accepts_strict_object() -> None:
    assert parse_json_text('{"name":"青岚"}') == {"name": "青岚"}


def test_malformed_json_and_markdown_fence_are_invalid_and_retain_exact_text() -> None:
    malformed = '{"case_key":'
    fenced = '```json\n{"case_key":"brief-001"}\n```'

    malformed_result = parse_json_text(malformed)
    fenced_result = parse_json_text(fenced)

    assert malformed_result == {
        "ok": False,
        "value": None,
        "errors": ["invalid JSON"],
        "raw_text": malformed,
    }
    assert fenced_result["ok"] is False
    assert fenced_result["raw_text"] == fenced
    assert fenced_result["errors"] == ["invalid JSON"]


def test_valid_task_pack_and_case_payloads_are_structured_without_mutating_input() -> None:
    task_pack = dict(TASK_PACK_CONTRACT)
    case = _valid_case()

    pack_result = parse_task_pack_payload(task_pack)
    case_result = parse_test_case_payload(case)

    assert pack_result == {"ok": True, "value": task_pack, "errors": [], "raw_text": None}
    assert case_result == {"ok": True, "value": case, "errors": [], "raw_text": None}
    assert case_result["value"] is not case


def test_test_case_rejects_invalid_split_and_feasibility_status() -> None:
    case = _valid_case()
    case["split"] = "training"
    case["feasibility_qa_status"] = "ready"

    result = parse_test_case_payload(case)

    assert result["ok"] is False
    assert "split must be 'dev' or 'holdout'" in result["errors"]
    assert "feasibility_qa_status must be 'pending', 'pass', or 'fail'" in result["errors"]


def test_task_pack_rejects_missing_or_wrong_typed_contract_fields() -> None:
    payload = dict(TASK_PACK_CONTRACT)
    del payload["language"]
    payload["title_min_chars"] = "4"

    result = parse_task_pack_payload(payload)

    assert result["ok"] is False
    assert any("language" in error for error in result["errors"])
    assert any("title_min_chars" in error for error in result["errors"])
