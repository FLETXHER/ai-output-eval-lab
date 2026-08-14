# DeepSeek Grader Pilot Abort Audit

- Condition ID: `2`
- Grader product: `DeepSeek Web`
- Visible model: `not_visible`
- UI mode: `Expert`
- DeepThink: `ON`
- Search: `OFF`
- Old blind packet template: `blind-grader-1.0`
- Abort reason: blind Grader packet instruction collision. The packet placed
  the original generation task before the Grader instruction, so the Grader
  could execute the generation task instead of evaluating the existing answer.

## Pilot candidates

| candidate_id | old packet version | old packet hash | grader_result_id | evaluation_result_id | grader_fact_result_ids |
| --- | --- | ---: | ---: | ---: | --- |
| `candidate-d6b5915c46057bcb` | `blind-grader-1.0` | `5fdd5e6f473711377d9cd7b0eec18834721c122ff906e0f4cebaaf6328b13b50` | `1` | `1` | `1, 2, 3` |
| `candidate-673aeeb08cfbb00b` | `blind-grader-1.0` | `265410a07a1ac63ea1e0329d132b1308d72a4eb71b4d1efb45ab25a6d93658d1` | `3` | `3` | `7, 8, 9` |
| `candidate-85f2ef987b76f4c3` | `blind-grader-1.0` | `691479804e47458546e22468d3464c1ceaab937e0417f37b4abd9c96d5e3b459` | none | none | none |

For `candidate-85f2ef987b76f4c3`, the first response was the original
generation-task JSON with root keys `title`, `summary`, and `key_points`, not
the approved Grader JSON contract. It was not imported as a Grader result.

The formal generator outputs and deterministic Rule Checks are retained. The
pilot-derived Grader rows above are aborted setup data and are removed before
the new formal Grader execution. The formal Grader will restart from the first
candidate using the new blind packet template.

## Cleanup record

- Cleanup time: `2026-08-14T05:09:43Z`
- Removed evaluation result IDs: `1`, `3`
- Removed grader fact result IDs: `1`, `2`, `3`, `7`, `8`, `9`
- Removed Grader result IDs: `1`, `3`
- Removed Human Review IDs: none
- Cleanup used one SQLite transaction with foreign-key checks enabled.
