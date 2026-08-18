CREATE TABLE IF NOT EXISTS human_review_corrections (
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

CREATE TRIGGER IF NOT EXISTS human_review_corrections_match_evaluation
BEFORE INSERT ON human_review_corrections
FOR EACH ROW
WHEN (SELECT evaluation_result_id FROM human_reviews WHERE id = NEW.original_human_review_id) IS NULL
  OR (SELECT evaluation_result_id FROM human_reviews WHERE id = NEW.original_human_review_id) != NEW.evaluation_result_id
BEGIN
    SELECT RAISE(ABORT, 'human review correction evaluation_result_id must match original review');
END;

CREATE TRIGGER IF NOT EXISTS human_review_corrections_no_update
BEFORE UPDATE ON human_review_corrections
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'human review corrections are append-only');
END;

CREATE TRIGGER IF NOT EXISTS human_review_corrections_no_delete
BEFORE DELETE ON human_review_corrections
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'human review corrections are append-only');
END;

CREATE TABLE IF NOT EXISTS human_review_correction_targets (
    id INTEGER PRIMARY KEY,
    original_human_review_id INTEGER NOT NULL REFERENCES human_reviews(id),
    evaluation_result_id INTEGER NOT NULL REFERENCES evaluation_results(id),
    authorization_reason TEXT NOT NULL CHECK (length(trim(authorization_reason)) > 0),
    authorized_at TEXT NOT NULL CHECK (length(trim(authorized_at)) > 0),
    UNIQUE (original_human_review_id)
);

CREATE TRIGGER IF NOT EXISTS human_review_correction_targets_match_evaluation
BEFORE INSERT ON human_review_correction_targets
FOR EACH ROW
WHEN (SELECT evaluation_result_id FROM human_reviews WHERE id = NEW.original_human_review_id) IS NULL
  OR (SELECT evaluation_result_id FROM human_reviews WHERE id = NEW.original_human_review_id) != NEW.evaluation_result_id
BEGIN
    SELECT RAISE(ABORT, 'human review correction target evaluation_result_id must match original review');
END;

CREATE TRIGGER IF NOT EXISTS human_review_correction_targets_no_update
BEFORE UPDATE ON human_review_correction_targets
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'human review correction targets are append-only');
END;

CREATE TRIGGER IF NOT EXISTS human_review_correction_targets_no_delete
BEFORE DELETE ON human_review_correction_targets
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'human review correction targets are append-only');
END;
