from eval_lab.domain.runs import validate_generator_visible_model_update


def test_generator_visible_model_update_allows_only_pre_output_open_dev_not_visible_run() -> None:
    assert validate_generator_visible_model_update(
        current_visible_model="not_visible",
        proposed_visible_model="GPT-5",
        run_status="open",
        split="dev",
        model_output_count=0,
    ) == []


def test_generator_visible_model_update_rejects_invalid_state_or_value() -> None:
    errors = validate_generator_visible_model_update(
        current_visible_model="GPT-5",
        proposed_visible_model="GPT-5.1",
        run_status="closed",
        split="holdout",
        model_output_count=1,
    )

    assert any("open" in error for error in errors)
    assert any("dev" in error for error in errors)
    assert any("model output" in error for error in errors)
    assert any("not_visible" in error for error in errors)
