from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import re


GENERATION_PACKET_VERSION = "generation-1.0"
BLIND_GRADER_PACKET_VERSION = "blind-grader-1.0"
BLIND_HUMAN_REVIEW_PACKET_VERSION = "blind-human-review-1.0"

HUMAN_REVIEW_RUBRIC = (
    "请仅依据给定来源材料、任务说明、约束和候选回答独立判断：回答是否满足格式、"
    "必需事实、来源忠实性与语言要求。证据不足或无法可靠判断时选择 indeterminate。"
)
HUMAN_REVIEW_DECISION_OPTIONS = ("pass", "fail", "indeterminate")


def render_generation_packet(
    case: Mapping[str, object],
    task_pack_contract: Mapping[str, object],
    prompt_version: Mapping[str, object],
) -> dict[str, object]:
    """Render only the content an output-generating model is allowed to see."""
    payload: dict[str, object] = {
        "user_task_output_contract": _task_pack_contract_text(task_pack_contract),
        "case_instructions": _case_instructions(case),
        "source_material": _required_text(case, "source_material"),
        "prompt_text": _required_text(prompt_version, "prompt_text"),
    }
    text = _render_sections(
        (
            ("用户任务与输出要求", payload["user_task_output_contract"]),
            ("Case 可见说明与约束", payload["case_instructions"]),
            ("来源材料", payload["source_material"]),
            ("当前提示词", payload["prompt_text"]),
        )
    )
    return _packet(GENERATION_PACKET_VERSION, text, payload)


def render_blind_grader_packet(
    candidate_id: str,
    task_pack_contract: Mapping[str, object],
    source_material: str,
    source_facts: Sequence[Mapping[str, str]],
    required_fact_ids: Sequence[str],
    constraints: Mapping[str, object],
    raw_model_response: str,
    grader_prompt: str,
    rubric: str,
    error_taxonomy: str,
) -> dict[str, object]:
    """Render one anonymous, pointwise Grader context from an explicit allowlist."""
    _validate_anonymous_candidate_id(candidate_id)
    facts = [
        {
            "fact_id": _required_mapping_text(fact, "fact_id"),
            "text": _required_mapping_text(fact, "text"),
        }
        for fact in source_facts
    ]
    required_ids = [_required_string(fact_id, "required_fact_ids item") for fact_id in required_fact_ids]
    payload: dict[str, object] = {
        "candidate_id": candidate_id,
        "user_task_output_contract": _task_pack_contract_text(task_pack_contract),
        "source_material": _required_string(source_material, "source_material"),
        "source_facts": facts,
        "required_fact_ids": required_ids,
        "constraints": _visible_constraints(constraints),
        "raw_model_response": _required_string(
            raw_model_response, "raw_model_response", allow_empty=True
        ),
        "grader_prompt": _required_string(grader_prompt, "grader_prompt"),
        "rubric": _required_string(rubric, "rubric"),
        "error_taxonomy": _required_string(error_taxonomy, "error_taxonomy"),
    }
    text = _render_sections(
        (
            ("匿名候选编号", payload["candidate_id"]),
            ("用户任务与输出要求", payload["user_task_output_contract"]),
            ("来源材料", payload["source_material"]),
            ("来源事实", payload["source_facts"]),
            ("必需事实 ID", payload["required_fact_ids"]),
            ("适用约束", payload["constraints"]),
            ("原始模型回答", payload["raw_model_response"]),
            ("Grader Prompt", payload["grader_prompt"]),
            ("Rubric", payload["rubric"]),
            ("Error Taxonomy", payload["error_taxonomy"]),
        ),
        preserve_raw_heading="原始模型回答",
    )
    return _packet(BLIND_GRADER_PACKET_VERSION, text, payload)


def render_blind_human_review_packet(
    candidate_id: str,
    source_material: str,
    task_instructions: str,
    constraints: Mapping[str, object],
    raw_model_response: str,
    human_review_rubric: str,
    decision_options: Sequence[str],
) -> dict[str, object]:
    """Render the independent pre-submit Human Review context."""
    _validate_anonymous_candidate_id(candidate_id)
    payload: dict[str, object] = {
        "candidate_id": candidate_id,
        "source_material": _required_string(source_material, "source_material"),
        "task_instructions": _required_string(
            task_instructions, "task_instructions", allow_empty=True
        ),
        "constraints": _visible_constraints(constraints),
        "raw_model_response": _required_string(
            raw_model_response, "raw_model_response", allow_empty=True
        ),
        "human_review_rubric": _required_string(
            human_review_rubric, "human_review_rubric"
        ),
        "decision_options": [
            _required_string(option, "decision_options item") for option in decision_options
        ],
    }
    text = _render_sections(
        (
            ("匿名候选编号", payload["candidate_id"]),
            ("来源材料", payload["source_material"]),
            ("用户可见任务说明", payload["task_instructions"]),
            ("用户可见约束", payload["constraints"]),
            ("原始模型回答", payload["raw_model_response"]),
            ("Human Review Rubric", payload["human_review_rubric"]),
            ("Decision Options", payload["decision_options"]),
        ),
        preserve_raw_heading="原始模型回答",
    )
    return _packet(BLIND_HUMAN_REVIEW_PACKET_VERSION, text, payload)


def _task_pack_contract_text(contract: Mapping[str, object]) -> str:
    explicit_task = contract.get("user_task") or contract.get("task_description")
    if explicit_task is None:
        task = "请根据给定来源材料生成一份忠实、结构化的简报。"
    else:
        task = _required_string(explicit_task, "user_task")

    explicit_output = contract.get("output_contract")
    if explicit_output is not None:
        output = _required_string(explicit_output, "output_contract")
    else:
        root_keys = contract.get("root_keys")
        if not isinstance(root_keys, Sequence) or isinstance(root_keys, (str, bytes)):
            raise ValueError("root_keys must be a sequence")
        keys = [_required_string(key, "root_keys item") for key in root_keys]
        output = (
            "仅返回严格 JSON，不要使用 Markdown 代码围栏。JSON 根对象必须且只能包含 "
            f"{_canonical_json(keys)}；title 为 {_required_int(contract, 'title_min_chars')}–"
            f"{_required_int(contract, 'title_max_chars')} 个字符，summary 为 "
            f"{_required_int(contract, 'summary_min_chars')}–"
            f"{_required_int(contract, 'summary_max_chars')} 个字符，key_points 必须包含 "
            f"{_required_int(contract, 'key_points_count')} 个字符串，每项 "
            f"{_required_int(contract, 'key_point_min_chars')}–"
            f"{_required_int(contract, 'key_point_max_chars')} 个字符；自然语言内容使用"
            f"{_language_name(contract.get('language'))}。"
        )
    return _normalize_block(f"{task}\n{output}")


def _case_instructions(case: Mapping[str, object]) -> str:
    for key in ("task_notes", "task_instructions", "instructions"):
        value = case.get(key)
        if isinstance(value, str):
            return _normalize_block(value)
    return ""


def _required_text(mapping: Mapping[str, object], key: str) -> str:
    return _required_string(mapping.get(key), key)


def _required_mapping_text(mapping: Mapping[str, str], key: str) -> str:
    return _required_string(mapping.get(key), key)


def _required_string(value: object, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value if allow_empty else _normalize_block(value)


def _required_int(mapping: Mapping[str, object], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    return value


def _language_name(value: object) -> str:
    language = _required_string(value, "language")
    return "简体中文" if language == "zh-CN" else language


def _validate_anonymous_candidate_id(candidate_id: str) -> None:
    candidate = _required_string(candidate_id, "candidate_id")
    if re.fullmatch(r"candidate-[0-9a-f]{6,64}", candidate) is None:
        raise ValueError(
            "candidate_id must use the anonymous opaque format candidate-<lowercase hex>"
        )


def _render_sections(
    sections: Sequence[tuple[str, object]], *, preserve_raw_heading: str | None = None
) -> str:
    blocks: list[str] = []
    for heading, value in sections:
        if isinstance(value, str):
            if heading == preserve_raw_heading and _is_clean_raw_block(value):
                body = value
            elif heading == preserve_raw_heading:
                body = _canonical_json(value)
            else:
                body = _normalize_block(value)
        else:
            body = _canonical_json(value)
        blocks.append(f"## {heading}" if body == "" else f"## {heading}\n{body}")
    return "\n\n".join(blocks)


def _is_clean_raw_block(value: str) -> bool:
    return (
        "\r" not in value
        and not value.endswith("\n")
        and all(line == line.rstrip() for line in value.split("\n"))
    )


def _normalize_block(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.split("\n")).strip("\n")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _visible_constraints(constraints: Mapping[str, object]) -> dict[str, object]:
    """Copy only the two Case constraint fields approved for blind contexts."""
    visible: dict[str, object] = {}
    if "task_instructions" in constraints:
        visible["task_instructions"] = _required_string(
            constraints["task_instructions"], "constraints.task_instructions", allow_empty=True
        )

    if "explicit_forbidden_claims" in constraints:
        claims = constraints["explicit_forbidden_claims"]
        if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
            raise ValueError("constraints.explicit_forbidden_claims must be a sequence")
        visible["explicit_forbidden_claims"] = [
            _required_string(claim, "constraints.explicit_forbidden_claims item")
            for claim in claims
        ]
    return visible


def _packet(version: str, text: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "packet_version": version,
        "text": text,
        "payload": payload,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
