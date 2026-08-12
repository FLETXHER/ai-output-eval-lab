from __future__ import annotations

import json

from eval_lab.domain.rules import parse_raw_json_response, run_deterministic_rules
from eval_lab.domain.task_pack import TASK_PACK_CONTRACT


def valid_response(**overrides: object) -> str:
    value: dict[str, object] = {
        "title": "测试标题",
        "summary": "简" * 60,
        "key_points": ["关键点内容一", "关键点内容二", "关键点内容三"],
    }
    value.update(overrides)
    return json.dumps(value, ensure_ascii=False)


def rule_results(result: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        item["rule_key"]: item
        for item in result["rule_results"]
        if isinstance(item, dict)
    }


def test_parser_rejects_invalid_json_without_repairing_it() -> None:
    parsed, error = parse_raw_json_response("{'title': 'not json'}")

    assert parsed is None
    assert error is not None


def test_parser_does_not_strip_markdown_fences() -> None:
    fence = chr(96) * 3
    raw_response = f"{fence}json\n{valid_response()}\n{fence}"

    parsed, error = parse_raw_json_response(raw_response)

    assert parsed is None
    assert error is not None


def test_rules_allow_outer_whitespace_but_keep_trimmed_character_count() -> None:
    raw_response = " \n" + valid_response(title="  四字标题  ") + "\t"

    result = run_deterministic_rules(raw_response, TASK_PACK_CONTRACT, [])
    rules = rule_results(result)

    assert result["parsed_value"] is not None
    assert rules["json_parse_pass"]["status"] == "pass"
    assert rules["schema_pass"]["status"] == "pass"
    assert rules["title_length"]["actual"] == 4
    assert rules["title_length"]["status"] == "pass"


def test_rules_enforce_exact_root_keys_separately_from_parse() -> None:
    result = run_deterministic_rules(
        valid_response(extra="not allowed"), TASK_PACK_CONTRACT, []
    )
    rules = rule_results(result)

    assert rules["json_parse_pass"]["status"] == "pass"
    assert rules["schema_pass"]["status"] == "fail"
    assert rules["title_length"]["status"] == "pass"


def test_rules_fail_schema_for_wrong_root_and_field_type() -> None:
    root_result = run_deterministic_rules("[]", TASK_PACK_CONTRACT, [])
    type_result = run_deterministic_rules(
        valid_response(title=7), TASK_PACK_CONTRACT, []
    )

    root_rules = rule_results(root_result)
    type_rules = rule_results(type_result)
    assert root_rules["json_parse_pass"]["status"] == "fail"
    assert root_rules["schema_pass"]["status"] == "not_applicable"
    assert type_rules["schema_pass"]["status"] == "fail"
    assert type_rules["title_length"]["status"] == "not_applicable"


def test_rules_reject_empty_strings_and_four_key_points() -> None:
    empty_result = run_deterministic_rules(
        valid_response(summary="  "), TASK_PACK_CONTRACT, []
    )
    four_points_result = run_deterministic_rules(
        valid_response(
            key_points=["关键点内容一", "关键点内容二", "关键点内容三", "关键点内容四"]
        ),
        TASK_PACK_CONTRACT,
        [],
    )

    empty_rules = rule_results(empty_result)
    four_rules = rule_results(four_points_result)
    assert empty_rules["schema_pass"]["status"] == "fail"
    assert empty_rules["summary_length"]["status"] == "fail"
    assert four_rules["schema_pass"]["status"] == "fail"
    assert four_rules["key_points_count"]["actual"] == 4
    assert four_rules["key_points_count"]["status"] == "fail"


def test_rules_enforce_exact_length_boundaries_for_all_fields() -> None:
    minimum = run_deterministic_rules(valid_response(), TASK_PACK_CONTRACT, [])
    maximum = run_deterministic_rules(
        valid_response(
            title="标" * 20,
            summary="简" * 120,
            key_points=["点" * 40, "点" * 40, "点" * 40],
        ),
        TASK_PACK_CONTRACT,
        [],
    )
    too_short = run_deterministic_rules(
        valid_response(title="短题", summary="简" * 59), TASK_PACK_CONTRACT, []
    )
    too_long = run_deterministic_rules(
        valid_response(key_points=["点" * 41, "关键点内容二", "关键点内容三"]),
        TASK_PACK_CONTRACT,
        [],
    )

    assert all(rule_results(minimum)[key]["status"] == "pass" for key in (
        "title_length", "summary_length", "key_points_count", "key_point_lengths"
    ))
    assert all(rule_results(maximum)[key]["status"] == "pass" for key in (
        "title_length", "summary_length", "key_points_count", "key_point_lengths"
    ))
    assert rule_results(too_short)["title_length"]["status"] == "fail"
    assert rule_results(too_short)["summary_length"]["status"] == "fail"
    assert rule_results(too_long)["key_point_lengths"]["status"] == "fail"


def test_rules_check_forbidden_claims_as_literal_phrases_only() -> None:
    result = run_deterministic_rules(
        valid_response(summary=("简" * 54) + "全球首发"),
        TASK_PACK_CONTRACT,
        ["全球首发", "市场第一"],
    )
    rules = rule_results(result)

    assert rules["forbidden_claims"]["status"] == "fail"
    assert rules["forbidden_claims"]["actual"] == ["全球首发"]
