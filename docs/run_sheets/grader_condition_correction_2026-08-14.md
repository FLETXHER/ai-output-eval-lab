# Grader Condition Correction Audit

- Candidate ID: `candidate-673aeeb08cfbb00b`
- Erroneously recorded condition ID: `1`
- Removed grader result ID: `2`
- Removed evaluation result ID: `2`
- Removed grader fact result IDs: `4`, `5`, `6`
- Human review rows removed: none
- Reason: UI refresh caused accidental Condition 1 submission.
- Formally retained condition ID: `2` (`DeepSeek Web`, visible model `not_visible`, `Expert`, DeepThink `ON`, Search `OFF`)
- Correction time: `2026-08-14T04:58:02Z`

The correction was executed in one SQLite transaction after verifying that
Condition 1 had no other formal Grader or evaluation results. The model output
and deterministic Rule Checks were not modified. Condition 1 itself and
Condition 2 were not modified.
