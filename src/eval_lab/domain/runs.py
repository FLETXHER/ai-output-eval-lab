from __future__ import annotations


def validate_generator_visible_model_update(
    *,
    current_visible_model: object,
    proposed_visible_model: object,
    run_status: object,
    split: object,
    model_output_count: object,
) -> list[str]:
    """Validate the one permitted pre-capture generator provenance update."""
    errors: list[str] = []
    if not isinstance(proposed_visible_model, str) or not proposed_visible_model.strip():
        errors.append("visible model must be a non-empty string")
    if run_status != "open":
        errors.append("only an open evaluation run can record a visible model")
    if split != "dev":
        errors.append("visible model recording is only available for a dev run")
    if not isinstance(model_output_count, int) or model_output_count != 0:
        errors.append("visible model cannot change after a model output exists")
    if current_visible_model != "not_visible":
        errors.append("generator visible model must start as not_visible and is otherwise immutable")
    return errors
