CREATE TABLE task_packs (
    id INTEGER PRIMARY KEY,
    pack_key TEXT NOT NULL UNIQUE,
    contract_version TEXT NOT NULL,
    contract_hash TEXT NOT NULL,
    language TEXT NOT NULL,
    title_min_chars INTEGER NOT NULL,
    title_max_chars INTEGER NOT NULL,
    summary_min_chars INTEGER NOT NULL,
    summary_max_chars INTEGER NOT NULL,
    key_points_count INTEGER NOT NULL,
    key_point_min_chars INTEGER NOT NULL,
    key_point_max_chars INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE test_cases (
    id INTEGER PRIMARY KEY,
    task_pack_id INTEGER NOT NULL REFERENCES task_packs(id),
    case_key TEXT NOT NULL,
    revision INTEGER NOT NULL,
    split TEXT NOT NULL CHECK (split IN ('dev', 'holdout')),
    source_material TEXT NOT NULL,
    source_facts_json TEXT NOT NULL,
    required_fact_ids_json TEXT NOT NULL,
    explicit_forbidden_claims_json TEXT NOT NULL,
    task_notes TEXT NOT NULL,
    feasibility_qa_status TEXT NOT NULL CHECK (feasibility_qa_status IN ('pending', 'pass', 'fail')),
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (task_pack_id, case_key, revision)
);

CREATE TABLE prompt_versions (
    id INTEGER PRIMARY KEY,
    version_label TEXT NOT NULL UNIQUE,
    prompt_text TEXT NOT NULL,
    change_reason TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'frozen')),
    owner_approved_at TEXT,
    frozen_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE evaluation_runs (
    id INTEGER PRIMARY KEY,
    comparison_group_id TEXT NOT NULL,
    prompt_version_id INTEGER NOT NULL REFERENCES prompt_versions(id),
    split TEXT NOT NULL CHECK (split IN ('dev', 'holdout')),
    case_set_hash TEXT NOT NULL,
    contract_hash TEXT NOT NULL,
    generator_product TEXT NOT NULL,
    generator_visible_model TEXT NOT NULL CHECK (
        generator_visible_model = 'not_visible' OR length(trim(generator_visible_model)) > 0
    ),
    environment_notes TEXT NOT NULL,
    protocol_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'open', 'closed', 'cancelled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE model_outputs (
    id INTEGER PRIMARY KEY,
    evaluation_run_id INTEGER NOT NULL REFERENCES evaluation_runs(id),
    test_case_id INTEGER NOT NULL REFERENCES test_cases(id),
    candidate_id TEXT NOT NULL,
    generation_packet_version TEXT NOT NULL,
    generation_packet_hash TEXT NOT NULL,
    raw_response TEXT,
    output_hash TEXT,
    generated_at TEXT,
    technical_retry_count INTEGER NOT NULL DEFAULT 0 CHECK (technical_retry_count >= 0),
    technical_retry_reasons_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (evaluation_run_id, test_case_id)
);

CREATE TABLE rule_results (
    id INTEGER PRIMARY KEY,
    model_output_id INTEGER NOT NULL REFERENCES model_outputs(id),
    rule_key TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pass', 'fail', 'not_applicable')),
    actual_json TEXT NOT NULL,
    expected_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    UNIQUE (model_output_id, rule_key, rule_version)
);

CREATE TABLE grader_conditions (
    id INTEGER PRIMARY KEY,
    grader_product TEXT NOT NULL,
    grader_visible_model TEXT NOT NULL CHECK (
        grader_visible_model = 'not_visible' OR length(trim(grader_visible_model)) > 0
    ),
    grader_prompt TEXT NOT NULL,
    grader_prompt_hash TEXT NOT NULL,
    grader_prompt_version_label TEXT NOT NULL,
    rubric TEXT NOT NULL,
    rubric_hash TEXT NOT NULL,
    rubric_version_label TEXT NOT NULL,
    error_taxonomy TEXT NOT NULL,
    error_taxonomy_hash TEXT NOT NULL,
    error_taxonomy_version_label TEXT NOT NULL,
    owner_approved_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE grader_results (
    id INTEGER PRIMARY KEY,
    model_output_id INTEGER NOT NULL REFERENCES model_outputs(id),
    grader_condition_id INTEGER NOT NULL REFERENCES grader_conditions(id),
    blind_packet_version TEXT NOT NULL,
    blind_packet_hash TEXT NOT NULL,
    raw_payload_json TEXT NOT NULL,
    import_status TEXT NOT NULL CHECK (import_status IN ('pending', 'valid', 'invalid')),
    normalized_semantic_json TEXT,
    language_compliance TEXT CHECK (language_compliance IN ('pass', 'fail', 'indeterminate')),
    readability TEXT,
    primary_error_type TEXT,
    secondary_error_types_json TEXT,
    unsupported_claims_json TEXT,
    reason_json TEXT,
    evidence_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (model_output_id, grader_condition_id)
);

CREATE TABLE grader_fact_results (
    id INTEGER PRIMARY KEY,
    grader_result_id INTEGER NOT NULL REFERENCES grader_results(id),
    fact_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('met', 'not_met', 'indeterminate')),
    output_evidence TEXT NOT NULL,
    reason TEXT NOT NULL,
    UNIQUE (grader_result_id, fact_id)
);

CREATE TABLE evaluation_results (
    id INTEGER PRIMARY KEY,
    model_output_id INTEGER NOT NULL REFERENCES model_outputs(id),
    grader_result_id INTEGER REFERENCES grader_results(id),
    grader_condition_id INTEGER NOT NULL REFERENCES grader_conditions(id),
    aggregation_rule_version TEXT NOT NULL,
    calculated_status TEXT NOT NULL CHECK (calculated_status IN ('pass', 'fail', 'indeterminate')),
    blocking_reasons_json TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    UNIQUE (model_output_id, grader_condition_id)
);

CREATE TABLE human_reviews (
    id INTEGER PRIMARY KEY,
    evaluation_result_id INTEGER NOT NULL REFERENCES evaluation_results(id),
    review_scope TEXT NOT NULL CHECK (review_scope IN ('required', 'sampled', 'manual')),
    blind_review INTEGER NOT NULL CHECK (blind_review IN (0, 1)),
    evidence_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    final_decision TEXT CHECK (final_decision IN ('pass', 'fail', 'indeterminate')),
    reviewed_at TEXT NOT NULL,
    UNIQUE (evaluation_result_id)
);

CREATE TABLE human_review_corrections (
    id INTEGER PRIMARY KEY,
    original_human_review_id INTEGER NOT NULL REFERENCES human_reviews(id),
    evaluation_result_id INTEGER NOT NULL REFERENCES evaluation_results(id),
    review_mode TEXT NOT NULL CHECK (review_mode = 'corrective-re-review'),
    correction_reason TEXT NOT NULL CHECK (length(trim(correction_reason)) > 0),
    reviewer_evidence_json TEXT NOT NULL,
    reviewer_reason TEXT NOT NULL CHECK (length(trim(reviewer_reason)) > 0),
    corrected_final_decision TEXT NOT NULL CHECK (
        corrected_final_decision IN ('pass', 'fail', 'indeterminate')
    ),
    corrected_at TEXT NOT NULL CHECK (length(trim(corrected_at)) > 0),
    UNIQUE (original_human_review_id)
);

CREATE TRIGGER human_review_corrections_match_evaluation
BEFORE INSERT ON human_review_corrections
FOR EACH ROW
WHEN (SELECT evaluation_result_id FROM human_reviews WHERE id = NEW.original_human_review_id) IS NULL
  OR (SELECT evaluation_result_id FROM human_reviews WHERE id = NEW.original_human_review_id) != NEW.evaluation_result_id
BEGIN
    SELECT RAISE(ABORT, 'human review correction evaluation_result_id must match original review');
END;

CREATE TRIGGER human_review_corrections_no_update
BEFORE UPDATE ON human_review_corrections
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'human review corrections are append-only');
END;

CREATE TRIGGER human_review_corrections_no_delete
BEFORE DELETE ON human_review_corrections
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'human review corrections are append-only');
END;
