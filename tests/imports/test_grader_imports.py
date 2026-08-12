from eval_lab.imports.grader_results import parse_grader_payload


def _valid_payload() -> dict[str, object]:
    return {
        "blind_packet_version": "blind-grader-1.0",
        "blind_packet_hash": "b" * 64,
        "language_compliance": {
            "label": "pass",
            "reason": "主体为简体中文。",
            "evidence": "标题和摘要均为简体中文。",
        },
        "required_facts": [
            {
                "fact_id": "F01",
                "label": "met",
                "output_evidence": "2026年8月发布",
                "reason": "准确表达发布时间。",
            }
        ],
        "unsupported_claims": [],
        "readability": {"label": "good", "reason": "清晰", "evidence": "结构完整"},
        "primary_error_type": None,
        "secondary_error_types": [],
        "grader_reason": "所有关键事实均已覆盖。",
    }


def test_valid_grader_payload_has_blind_packet_provenance_and_structured_value() -> None:
    payload = _valid_payload()

    result = parse_grader_payload(payload, ["F01"])

    assert result == {"ok": True, "value": payload, "errors": [], "raw_text": None}
    assert result["value"] is not payload


def test_grader_rejects_invalid_labels_unknown_fact_ids_and_invalid_evidence_shape() -> None:
    payload = _valid_payload()
    payload["language_compliance"] = {"label": "maybe", "reason": "x", "evidence": "y"}
    payload["required_facts"] = [
        {"fact_id": "F99", "label": "present", "output_evidence": [], "reason": "x"}
    ]

    result = parse_grader_payload(payload, ["F01"])

    assert result["ok"] is False
    assert any("language_compliance.label" in error for error in result["errors"])
    assert any("unsupported fact_id" in error for error in result["errors"])
    assert any("output_evidence" in error for error in result["errors"])


def test_grader_rejects_forbidden_blind_metadata() -> None:
    payload = _valid_payload()
    payload["prompt_version"] = "v2"
    payload["calculated_status"] = "pass"

    result = parse_grader_payload(payload, ["F01"])

    assert result["ok"] is False
    assert any("blind metadata" in error for error in result["errors"])


def test_grader_rejects_missing_packet_provenance() -> None:
    payload = _valid_payload()
    del payload["blind_packet_hash"]

    result = parse_grader_payload(payload, ["F01"])

    assert result["ok"] is False
    assert any("blind_packet_hash" in error for error in result["errors"])
