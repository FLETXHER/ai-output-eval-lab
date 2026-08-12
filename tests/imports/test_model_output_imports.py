from eval_lab.imports.model_outputs import parse_model_output_payload


def _valid_payload() -> dict[str, object]:
    return {
        "generation_packet_version": "generation-1.0",
        "generation_packet_hash": "a" * 64,
        "raw_response": '{"title":"原样保留"}',
        "generated_at": "2026-08-13T10:00:00Z",
    }


def test_model_output_preserves_raw_response_exactly() -> None:
    payload = _valid_payload()
    payload["raw_response"] = '  {"title":"原样  "}\n'

    result = parse_model_output_payload(payload)

    assert result["ok"] is True
    assert result["value"] is not payload
    assert result["value"]["raw_response"] == '  {"title":"原样  "}\n'


def test_model_output_rejects_non_string_response_and_missing_packet_provenance() -> None:
    payload = _valid_payload()
    payload["raw_response"] = {"title": "不是原始文本"}
    del payload["generation_packet_hash"]

    result = parse_model_output_payload(payload)

    assert result["ok"] is False
    assert any("raw_response" in error for error in result["errors"])
    assert any("generation_packet_hash" in error for error in result["errors"])


def test_model_output_does_not_accept_unknown_import_fields() -> None:
    payload = _valid_payload()
    payload["prompt_version"] = "v2"

    result = parse_model_output_payload(payload)

    assert result["ok"] is False
    assert any("unsupported keys" in error for error in result["errors"])
