from __future__ import annotations

from eval_lab.domain.packets import (
    CORRECTIVE_HUMAN_REVIEW_PACKET_VERSION,
    render_corrective_human_review_packet,
)
from eval_lab.domain.task_pack import TASK_PACK_CONTRACT


def test_corrective_packet_displays_raw_response_literally_even_with_trailing_newline() -> None:
    raw_response = '{"title":"真实回答","summary":"这是保存在数据库中的 JSON object。","key_points":["第一条","第二条","第三条"]}\n'
    packet = render_corrective_human_review_packet(
        candidate_id="candidate-a1b2c3",
        task_pack_contract=TASK_PACK_CONTRACT,
        source_material="来源材料",
        task_instructions="按任务说明完成输出。",
        constraints={"explicit_forbidden_claims": []},
        raw_model_response=raw_response,
        human_review_rubric="独立复核实际回答。",
        decision_options=["pass", "fail", "indeterminate"],
    )

    assert packet["packet_version"] == CORRECTIVE_HUMAN_REVIEW_PACKET_VERSION
    assert "## 原始模型回答（逐字文本）\n{" in packet["text"]
    assert raw_response in packet["text"]
    assert '"{\\"title\\"' not in packet["text"]
    assert "corrective-re-review" in packet["text"]
    assert packet["payload"]["raw_model_response"] == raw_response
