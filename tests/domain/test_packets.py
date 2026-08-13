from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from eval_lab.domain.packets import (
    render_blind_grader_packet,
    render_blind_human_review_packet,
    render_generation_packet,
)
from eval_lab.domain.task_pack import TASK_PACK_CONTRACT


def _contract_with_internal_sentinels() -> dict[str, object]:
    contract = deepcopy(TASK_PACK_CONTRACT)
    contract.update(
        {
            "contract_hash": "FORBIDDEN_CONTRACT_HASH",
            "analysis": "FORBIDDEN_ANALYSIS",
            "grader_result": "FORBIDDEN_PRIOR_GRADER_RESULT",
        }
    )
    return contract


def _generation_case() -> dict[str, object]:
    return {
        "source_material": "来源材料：星河计划将于九月九日启动。",
        "task_notes": "可见说明：标题需突出启动日期。",
        "source_facts": [
            {"fact_id": "FORBIDDEN_FACT_ID_F01", "text": "九月九日启动"}
        ],
        "required_fact_ids": ["FORBIDDEN_REQUIRED_FACT_ID"],
        "split": "FORBIDDEN_HOLDOUT_SPLIT",
        "revision": "FORBIDDEN_CASE_REVISION",
        "content_hash": "FORBIDDEN_CASE_HASH",
        "comparison_group_id": "FORBIDDEN_COMPARISON_GROUP",
        "generator_product": "FORBIDDEN_GENERATOR_PRODUCT",
        "generator_visible_model": "FORBIDDEN_GENERATOR_MODEL",
        "rule_result": "FORBIDDEN_RULE_RESULT",
        "human_review": "FORBIDDEN_HUMAN_REVIEW",
        "calculated_status": "FORBIDDEN_CALCULATED_STATUS",
        "experiment_conclusion": "FORBIDDEN_EXPERIMENT_CONCLUSION",
    }


def _prompt_version(prompt_text: str = "当前提示词：忠实依据材料并只输出 JSON。") -> dict[str, object]:
    return {
        "prompt_text": prompt_text,
        "version_label": "FORBIDDEN_PROMPT_V2_LABEL",
        "content_hash": "FORBIDDEN_PROMPT_HASH",
        "change_reason": "FORBIDDEN_DESIRED_IMPROVEMENT",
        "run_purpose": "FORBIDDEN_RUN_PURPOSE",
    }


def _assert_exact_text_hash(packet: dict[str, object]) -> None:
    text = packet["text"]
    assert isinstance(text, str)
    assert packet["content_hash"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert "\r" not in text
    assert text == "\n".join(line.rstrip() for line in text.split("\n"))
    assert not text.endswith("\n")


def test_generation_packet_is_repeatable_and_has_fixed_section_order() -> None:
    first = render_generation_packet(
        _generation_case(), _contract_with_internal_sentinels(), _prompt_version()
    )
    second = render_generation_packet(
        _generation_case(), _contract_with_internal_sentinels(), _prompt_version()
    )

    assert first == second
    assert set(first) == {"packet_version", "text", "payload", "content_hash"}
    assert list(first["payload"]) == [
        "user_task_output_contract",
        "case_instructions",
        "source_material",
        "prompt_text",
    ]
    section_positions = [
        first["text"].index("## 用户任务与输出要求"),
        first["text"].index("## Case 可见说明与约束"),
        first["text"].index("## 来源材料"),
        first["text"].index("## 当前提示词"),
    ]
    assert section_positions == sorted(section_positions)
    _assert_exact_text_hash(first)


@pytest.mark.parametrize("changed_input", ["prompt", "source", "instructions"])
def test_generation_hash_changes_when_model_facing_content_changes(
    changed_input: str,
) -> None:
    case = _generation_case()
    prompt = _prompt_version()
    original = render_generation_packet(case, TASK_PACK_CONTRACT, prompt)

    changed_case = deepcopy(case)
    changed_prompt = deepcopy(prompt)
    if changed_input == "prompt":
        changed_prompt["prompt_text"] = "另一条实际提示词"
    elif changed_input == "source":
        changed_case["source_material"] = "另一份来源材料"
    else:
        changed_case["task_notes"] = "另一条用户可见说明"

    changed = render_generation_packet(changed_case, TASK_PACK_CONTRACT, changed_prompt)

    assert changed["content_hash"] != original["content_hash"]
    assert changed["text"] != original["text"]


def test_generation_packet_strictly_allowlists_model_facing_values() -> None:
    packet = render_generation_packet(
        _generation_case(), _contract_with_internal_sentinels(), _prompt_version()
    )
    exposed = packet["text"] + json.dumps(
        packet["payload"], ensure_ascii=False, sort_keys=True
    )

    assert "当前提示词：忠实依据材料并只输出 JSON。" in exposed
    assert "来源材料：星河计划将于九月九日启动。" in exposed
    assert "可见说明：标题需突出启动日期。" in exposed
    for forbidden in (
        "FORBIDDEN_FACT_ID_F01",
        "FORBIDDEN_REQUIRED_FACT_ID",
        "FORBIDDEN_HOLDOUT_SPLIT",
        "FORBIDDEN_CASE_REVISION",
        "FORBIDDEN_CASE_HASH",
        "FORBIDDEN_PROMPT_V2_LABEL",
        "FORBIDDEN_PROMPT_HASH",
        "FORBIDDEN_COMPARISON_GROUP",
        "FORBIDDEN_GENERATOR_PRODUCT",
        "FORBIDDEN_GENERATOR_MODEL",
        "FORBIDDEN_RUN_PURPOSE",
        "FORBIDDEN_RULE_RESULT",
        "FORBIDDEN_PRIOR_GRADER_RESULT",
        "FORBIDDEN_HUMAN_REVIEW",
        "FORBIDDEN_CALCULATED_STATUS",
        "FORBIDDEN_ANALYSIS",
        "FORBIDDEN_EXPERIMENT_CONCLUSION",
        "FORBIDDEN_DESIRED_IMPROVEMENT",
        "FORBIDDEN_CONTRACT_HASH",
    ):
        assert forbidden not in exposed


def test_blind_grader_packet_contains_all_and_only_required_context() -> None:
    source_facts = [
        {"fact_id": "F01", "text": "九月九日启动"},
        {"fact_id": "F02", "text": "在北京举行发布会"},
    ]
    required_fact_ids = ["F01"]
    constraints = {
        "task_instructions": "标题需突出启动日期",
        "explicit_forbidden_claims": ["全球首发"],
        "calculated_status": "LEAK_STATUS",
        "prompt_version": "LEAK_VERSION",
    }
    raw_response = '{"title":"九月九日启动","summary":"原样回答"}'

    packet = render_blind_grader_packet(
        candidate_id="candidate-a7f3c2",
        task_pack_contract=_contract_with_internal_sentinels(),
        source_material="星河计划将于九月九日启动，并在北京举行发布会。",
        source_facts=source_facts,
        required_fact_ids=required_fact_ids,
        constraints=constraints,
        raw_model_response=raw_response,
        grader_prompt="逐项检查回答。",
        rubric="事实必须有来源支持。",
        error_taxonomy="missing_fact | unsupported_claim",
    )

    payload = packet["payload"]
    assert list(payload) == [
        "candidate_id",
        "user_task_output_contract",
        "source_material",
        "source_facts",
        "required_fact_ids",
        "constraints",
        "raw_model_response",
        "grader_prompt",
        "rubric",
        "error_taxonomy",
    ]
    assert payload["candidate_id"] == "candidate-a7f3c2"
    assert payload["source_facts"] == source_facts
    assert payload["required_fact_ids"] == required_fact_ids
    assert payload["constraints"] == {
        "task_instructions": "标题需突出启动日期",
        "explicit_forbidden_claims": ["全球首发"],
    }
    assert payload["raw_model_response"] == raw_response
    for allowed in (
        "candidate-a7f3c2",
        "F01",
        "F02",
        "全球首发",
        raw_response,
        "逐项检查回答。",
        "事实必须有来源支持。",
        "missing_fact | unsupported_claim",
    ):
        assert allowed in packet["text"]
    for forbidden in (
        "FORBIDDEN_CONTRACT_HASH",
        "FORBIDDEN_ANALYSIS",
        "FORBIDDEN_PRIOR_GRADER_RESULT",
        "LEAK_STATUS",
        "LEAK_VERSION",
    ):
        assert forbidden not in packet["text"]
        assert forbidden not in json.dumps(payload, ensure_ascii=False)
    _assert_exact_text_hash(packet)


def test_blind_packet_text_losslessly_encodes_raw_whitespace_without_rendered_trailing_space() -> None:
    raw_response = "first line  \r\nsecond line\t"

    packet = render_blind_grader_packet(
        candidate_id="candidate-d61a04",
        task_pack_contract=TASK_PACK_CONTRACT,
        source_material="来源",
        source_facts=[],
        required_fact_ids=[],
        constraints={},
        raw_model_response=raw_response,
        grader_prompt="评分提示",
        rubric="量表",
        error_taxonomy="错误分类",
    )

    assert packet["payload"]["raw_model_response"] == raw_response
    assert json.dumps(
        raw_response, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) in packet["text"]
    _assert_exact_text_hash(packet)


@pytest.mark.parametrize(
    "candidate_id",
    [
        "candidate-v1",
        "candidate_v2_001",
        "dev-candidate",
        "candidate-holdout",
        "candidate-hold-out",
        "candidate-version-2",
    ],
)
def test_blind_packets_reject_candidate_ids_that_encode_version_or_split(
    candidate_id: str,
) -> None:
    with pytest.raises(ValueError, match="anonymous"):
        render_blind_grader_packet(
            candidate_id,
            TASK_PACK_CONTRACT,
            "来源",
            [],
            [],
            {},
            "回答",
            "评分提示",
            "量表",
            "错误分类",
        )


def test_blind_human_review_packet_has_a_separate_strict_allowlist() -> None:
    raw_response = '{"title":"候选回答","summary":"保持原样"}'
    packet = render_blind_human_review_packet(
        candidate_id="candidate-b93de1",
        task_pack_contract=TASK_PACK_CONTRACT,
        source_material="仅供复核的来源材料",
        task_instructions="只依据来源，并以简体中文作答。",
        constraints={
            "explicit_forbidden_claims": ["行业第一"],
            "calculated_status": "LEAK_STATUS",
            "prompt_version": "LEAK_VERSION",
        },
        raw_model_response=raw_response,
        human_review_rubric="独立判断事实和格式是否满足任务。",
        decision_options=["pass", "fail", "indeterminate"],
    )

    assert list(packet["payload"]) == [
        "candidate_id",
        "user_task_output_contract",
        "source_material",
        "task_instructions",
        "constraints",
        "raw_model_response",
        "human_review_rubric",
        "decision_options",
    ]
    assert packet["payload"]["raw_model_response"] == raw_response
    contract_text = packet["payload"]["user_task_output_contract"]
    assert isinstance(contract_text, str)
    for expected in ("title", "summary", "key_points", "4", "20", "60", "120", "6", "40", "简体中文"):
        assert expected in contract_text
    assert packet["payload"]["constraints"] == {
        "explicit_forbidden_claims": ["行业第一"]
    }
    exposed = packet["text"] + json.dumps(packet["payload"], ensure_ascii=False)
    for allowed in (
        "candidate-b93de1",
        contract_text,
        "仅供复核的来源材料",
        "只依据来源，并以简体中文作答。",
        "行业第一",
        raw_response,
        "独立判断事实和格式是否满足任务。",
        "indeterminate",
    ):
        assert allowed in exposed
    for forbidden_key in (
        "prompt_version",
        "split",
        "generator_product",
        "generator_visible_model",
        "grader_result",
        "grader_reason",
        "grader_evidence",
        "calculated_status",
        "primary_error_type",
        "human_review",
        "analysis",
        "experiment_conclusion",
        "evaluation_result_id",
        "packet_version",
        "content_hash",
    ):
        assert forbidden_key not in packet["payload"]
        assert forbidden_key not in packet["text"]
    assert "LEAK_STATUS" not in exposed
    assert "LEAK_VERSION" not in exposed
    _assert_exact_text_hash(packet)
