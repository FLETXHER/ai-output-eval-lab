from eval_lab.domain.task_pack import TASK_PACK_CONTRACT
from eval_lab.imports.test_cases import (
    load_task_pack_seed,
    load_test_case_seed,
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
        "content_hash": "a" * 64,
        "contract_hash": "b" * 64,
        "traceability_metadata": {
            "source_of_truth": "source_material",
            "source_facts_traceable": True,
        },
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


def test_case_requires_hashes_and_traceability_metadata() -> None:
    case = _valid_case()
    del case["content_hash"]
    case["contract_hash"] = "uppercase-is-invalid"
    case["traceability_metadata"] = {"source_of_truth": "source_facts"}

    result = parse_test_case_payload(case)

    assert result["ok"] is False
    assert any("content_hash" in error for error in result["errors"])
    assert any("contract_hash" in error for error in result["errors"])
    assert any("traceability_metadata" in error for error in result["errors"])


def test_seed_loaders_reject_invalid_file_shapes(tmp_path) -> None:
    task_pack_path = tmp_path / "task-pack.json"
    cases_path = tmp_path / "cases.json"
    task_pack_path.write_text("[]", encoding="utf-8")
    cases_path.write_text("{}", encoding="utf-8")

    assert load_task_pack_seed(task_pack_path)["ok"] is False
    assert load_test_case_seed(cases_path)["ok"] is False
