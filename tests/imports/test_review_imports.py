from eval_lab.imports.human_reviews import parse_human_review_payload


def _valid_payload() -> dict[str, object]:
    return {
        "review_scope": "sampled",
        "blind_review": True,
        "evidence": {"source": "支持事实 F01", "response": "输出中包含发布时间"},
        "reason": "独立复核通过。",
        "final_decision": "pass",
        "reviewed_at": "2026-08-13T11:00:00Z",
    }


def test_valid_human_review_payload_is_structured() -> None:
    payload = _valid_payload()

    result = parse_human_review_payload(payload)

    assert result == {"ok": True, "value": payload, "errors": [], "raw_text": None}
    assert result["value"] is not payload


def test_human_review_rejects_missing_decision_or_reason() -> None:
    payload = _valid_payload()
    del payload["final_decision"]
    payload["reason"] = ""

    result = parse_human_review_payload(payload)

    assert result["ok"] is False
    assert any("final_decision" in error for error in result["errors"])
    assert any("reason" in error for error in result["errors"])


def test_human_review_rejects_invalid_decision_and_automatic_metadata() -> None:
    payload = _valid_payload()
    payload["final_decision"] = "unclear"
    payload["grader_reason"] = "泄漏"

    result = parse_human_review_payload(payload)

    assert result["ok"] is False
    assert any("final_decision" in error for error in result["errors"])
    assert any("unsupported keys" in error for error in result["errors"])
