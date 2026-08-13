-- name: run_summary
SELECT
    COUNT(mo.id) AS total_assigned,
    COALESCE(SUM(CASE WHEN mo.raw_response IS NOT NULL THEN 1 ELSE 0 END), 0) AS responses_received,
    COALESCE(SUM(CASE WHEN mo.raw_response IS NULL AND mo.technical_retry_count > 0 THEN 1 ELSE 0 END), 0) AS technical_failure_count,
    COALESCE(SUM(CASE WHEN ev.id IS NULL THEN 1 ELSE 0 END), 0) AS not_evaluated_count,
    COALESCE(SUM(CASE WHEN ev.calculated_status IN ('pass', 'fail') THEN 1 ELSE 0 END), 0) AS determinate_count,
    COALESCE(SUM(CASE WHEN ev.calculated_status = 'pass' THEN 1 ELSE 0 END), 0) AS calculated_pass_count,
    CASE
        WHEN COALESCE(SUM(CASE WHEN ev.calculated_status IN ('pass', 'fail') THEN 1 ELSE 0 END), 0) = 0 THEN NULL
        ELSE CAST(SUM(CASE WHEN ev.calculated_status = 'pass' THEN 1 ELSE 0 END) AS REAL)
             / SUM(CASE WHEN ev.calculated_status IN ('pass', 'fail') THEN 1 ELSE 0 END)
    END AS pass_rate_among_determinate,
    COALESCE(SUM(CASE WHEN ev.calculated_status = 'indeterminate' THEN 1 ELSE 0 END), 0) AS indeterminate_count,
    CASE
        WHEN COALESCE(SUM(CASE WHEN ev.id IS NOT NULL THEN 1 ELSE 0 END), 0) = 0 THEN NULL
        ELSE CAST(SUM(CASE WHEN ev.calculated_status = 'indeterminate' THEN 1 ELSE 0 END) AS REAL)
             / SUM(CASE WHEN ev.id IS NOT NULL THEN 1 ELSE 0 END)
    END AS indeterminate_rate
FROM model_outputs AS mo
LEFT JOIN evaluation_results AS ev ON ev.model_output_id = mo.id
WHERE mo.evaluation_run_id = ?;

-- name: status_distribution
SELECT 'calculated_status' AS decision_layer, ev.calculated_status AS status, COUNT(*) AS count
FROM evaluation_results AS ev
JOIN model_outputs AS mo ON mo.id = ev.model_output_id
WHERE mo.evaluation_run_id = ?
GROUP BY ev.calculated_status
UNION ALL
SELECT 'final_decision' AS decision_layer, hr.final_decision AS status, COUNT(*) AS count
FROM human_reviews AS hr
JOIN evaluation_results AS ev ON ev.id = hr.evaluation_result_id
JOIN model_outputs AS mo ON mo.id = ev.model_output_id
WHERE mo.evaluation_run_id = ? AND hr.final_decision IS NOT NULL
GROUP BY hr.final_decision
ORDER BY decision_layer, status;

-- name: paired_comparison
WITH case_ids AS (
    SELECT test_case_id FROM model_outputs WHERE evaluation_run_id = ?
    UNION
    SELECT test_case_id FROM model_outputs WHERE evaluation_run_id = ?
), left_results AS (
    SELECT mo.test_case_id, ev.calculated_status, hr.final_decision
    FROM model_outputs AS mo
    LEFT JOIN evaluation_results AS ev ON ev.model_output_id = mo.id
    LEFT JOIN human_reviews AS hr ON hr.evaluation_result_id = ev.id
    WHERE mo.evaluation_run_id = ?
), right_results AS (
    SELECT mo.test_case_id, ev.calculated_status, hr.final_decision
    FROM model_outputs AS mo
    LEFT JOIN evaluation_results AS ev ON ev.model_output_id = mo.id
    LEFT JOIN human_reviews AS hr ON hr.evaluation_result_id = ev.id
    WHERE mo.evaluation_run_id = ?
)
SELECT
    case_ids.test_case_id,
    left_results.calculated_status AS left_calculated_status,
    right_results.calculated_status AS right_calculated_status,
    left_results.final_decision AS left_final_decision,
    right_results.final_decision AS right_final_decision
FROM case_ids
LEFT JOIN left_results ON left_results.test_case_id = case_ids.test_case_id
LEFT JOIN right_results ON right_results.test_case_id = case_ids.test_case_id
ORDER BY case_ids.test_case_id;

-- name: rule_failures
SELECT rr.rule_key, COUNT(*) AS count
FROM rule_results AS rr
JOIN model_outputs AS mo ON mo.id = rr.model_output_id
WHERE mo.evaluation_run_id = ? AND rr.status = 'fail'
GROUP BY rr.rule_key
ORDER BY rr.rule_key;

-- name: required_fact_failures
SELECT gfr.fact_id, gfr.status, COUNT(*) AS count
FROM grader_fact_results AS gfr
JOIN grader_results AS gr ON gr.id = gfr.grader_result_id
JOIN model_outputs AS mo ON mo.id = gr.model_output_id
WHERE mo.evaluation_run_id = ? AND gfr.status IN ('not_met', 'indeterminate')
GROUP BY gfr.fact_id, gfr.status
ORDER BY gfr.fact_id, gfr.status;

-- name: unsupported_claims
SELECT gr.model_output_id, COUNT(*) AS unsupported_claim_count
FROM grader_results AS gr
JOIN model_outputs AS mo ON mo.id = gr.model_output_id
JOIN json_each(COALESCE(gr.unsupported_claims_json, '[]')) AS claim
WHERE mo.evaluation_run_id = ?
GROUP BY gr.model_output_id
ORDER BY gr.model_output_id;

-- name: error_types
SELECT gr.primary_error_type, COUNT(*) AS count
FROM grader_results AS gr
JOIN model_outputs AS mo ON mo.id = gr.model_output_id
WHERE mo.evaluation_run_id = ? AND gr.primary_error_type IS NOT NULL
GROUP BY gr.primary_error_type
ORDER BY gr.primary_error_type;

-- name: bad_cases
SELECT
    mo.id AS model_output_id,
    mo.candidate_id,
    ev.calculated_status,
    hr.final_decision,
    gr.primary_error_type
FROM model_outputs AS mo
JOIN evaluation_results AS ev ON ev.model_output_id = mo.id
LEFT JOIN human_reviews AS hr ON hr.evaluation_result_id = ev.id
LEFT JOIN grader_results AS gr ON gr.id = ev.grader_result_id
WHERE mo.evaluation_run_id = ? AND ev.calculated_status <> 'pass'
ORDER BY mo.id;

-- name: review_coverage
SELECT
    COUNT(ev.id) AS total_evaluation_results,
    COALESCE(SUM(CASE WHEN hr.id IS NOT NULL THEN 1 ELSE 0 END), 0) AS human_reviewed_count,
    CASE
        WHEN COUNT(ev.id) = 0 THEN NULL
        ELSE CAST(SUM(CASE WHEN hr.id IS NOT NULL THEN 1 ELSE 0 END) AS REAL) / COUNT(ev.id)
    END AS human_review_coverage_rate
FROM evaluation_results AS ev
JOIN model_outputs AS mo ON mo.id = ev.model_output_id
JOIN evaluation_runs AS er ON er.id = mo.evaluation_run_id
LEFT JOIN human_reviews AS hr ON hr.evaluation_result_id = ev.id
WHERE er.comparison_group_id = ?;
