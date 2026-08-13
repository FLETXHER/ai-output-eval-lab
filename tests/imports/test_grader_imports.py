from eval_lab.imports.grader_results import parse_grader_payload


def _valid_payload() -> dict[str, object]:
    return {
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
        "readability": {"label": "pass", "reason": "清晰", "evidence": "结构完整"},
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


def test_grader_rejects_internal_packet_provenance_fields_in_external_json() -> None:
    payload = _valid_payload()
    payload["blind_packet_hash"] = "b" * 64

    result = parse_grader_payload(payload, ["F01"])

    assert result["ok"] is False
    assert any("unsupported keys" in error for error in result["errors"])


def test_import_validation_accepts_supporting_non_required_source_fact() -> None:
    payload = _valid_payload()
    payload["unsupported_claims"] = [
        {
            "claim": "The package includes a cable.",
            "output_evidence": "包装包含数据线。",
            "supporting_fact_ids": ["F02"],
            "reason": "F02 was checked but is insufficient support.",
        }
    ]
    payload["primary_error_type"] = "unsupported_claim"
    result = parse_grader_payload(payload, ["F01"], ["F01", "F02"])
    assert result["ok"] is True

    payload["unsupported_claims"][0]["supporting_fact_ids"] = ["UNKNOWN"]  # type: ignore[index]
    result = parse_grader_payload(payload, ["F01"], ["F01", "F02"])
    assert result["ok"] is False
    assert any("UNKNOWN" in error for error in result["errors"])
