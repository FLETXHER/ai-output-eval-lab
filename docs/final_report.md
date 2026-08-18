# AI Output Eval Lab — Final Experiment Report

## Executive summary

This experiment asked whether a minimal, evidence-driven Prompt revision could
reduce the observed summary-length failures in a fixed Grounded Structured
Brief Generation task without introducing structural or semantic regressions.

Dev v1 produced 12 pass and 6 fail results out of 18 Cases. All six failures
were `summary_length` failures, with summaries between 55 and 59 characters.
Prompt v2 kept the formal 60–120-character contract, added an approximate
70–100-character generation target, and added a source-grounded silent length
check.

In the six-Case Formal Holdout, v1 produced 5/6 pass and v2 produced 6/6
pass. The paired result was 1 improved, 5 unchanged, 0 regressed, and 0
indeterminate. The only improvement was a `summary_length` fail → pass
transition. No new deterministic or semantic regression was observed.

Owner decision: **Recommend Prompt v2** for this task setup, with **Moderate**
confidence. This is a bounded recommendation, not a statistical or universal
claim.

## Experiment question

Can a minimal, evidence-driven Prompt revision reduce the observed
summary-length failures without introducing new structural or semantic
regressions?

## Formal scope and provenance

- Task: Grounded Structured Brief Generation
- Formal Case Set: 24 fictional Cases, 18 Dev and 6 Holdout
- Full Case Set hash: `c2555bafffd6d8ac0730a438fe0963530676d63beb7cea7b13a3116ae59f6bb5`
- Dev-only hash: `a23f8d88ad1e35443d3b31bfcd0c60274b204cdbd0738d4ab21eefd24db3cb1c`
- Holdout-only hash: `b22b44b58162a69e74de8af7ab93f9f8507caf3f665f70a68ad630ead004bd6f`
- Task Pack contract hash: `ae273822b78d16cba4df5d784d611313f788353229d1b95166047cc1254a2c59`
- Prompt v1 hash: `07aa48853dbe0ed54ff88a2476ce6ec9be2cac4d2680dc2b41d0fc36c392ae4f`
- Prompt v2 hash: `46198292143fa675fc9ad2cb0e724b6811aa3f2455b05f19a75f12e04aeaae74`

The `case_set_hash` stored on a run is the hash for that run's split subset;
it is not automatically the full 24-Case hash.

## Dev findings

Formal Run 1 was a closed Dev v1 run with 18 outputs:

| Status | Count |
| --- | ---: |
| Pass | 12 |
| Fail | 6 |
| Indeterminate | 0 |

All six failures were caused solely by `summary_length`, with failing summaries
at 55–59 characters. There were no JSON/schema, title, key-point count/length,
required-fact, unsupported-claim, language, or readability failures.

Required facts were 54/54 met and unsupported claims were zero.

## Prompt v2 hypothesis

The intervention was deliberately narrow:

- formal hard rule remains `summary = 60–120 characters`;
- generation target is approximately 70–100 characters;
- a silent source-grounded length check may add only directly supported,
  relevant facts when a summary is too short;
- repetition, filler, inference, evaluation, and unsupported facts remain
  prohibited;
- no JSON, schema, groundedness, language, title, or key-point rules changed.

The 70–100 range is a generation target, not a pass/fail criterion.

## Formal Holdout design

The valid Formal Holdout pair is `HOLDOUT-COMP-02`:

- Run 4: Prompt v1, Holdout, closed;
- Run 5: Prompt v2, Holdout, closed;
- six paired Cases;
- same contract hash, Holdout-only Case Set hash, generator condition, and
  protocol;
- same approved Grader Condition 2: DeepSeek Web, visible model `not_visible`.

The superseded Run 2 and Run 3 in `HOLDOUT-COMP-01` were closed empty shells
with the Dev-only hash. They are retained for provenance but are not Formal
Holdout evidence.

## Paired results

| Outcome | Count |
| --- | ---: |
| Improved | 1 |
| Unchanged | 5 |
| Regressed | 0 |
| Indeterminate | 0 |

| Case | v1 | v2 | Outcome |
| --- | --- | --- | --- |
| brief-holdout-01 | pass | pass | unchanged |
| brief-holdout-02 | pass | pass | unchanged |
| brief-holdout-03 | fail | pass | improved |
| brief-holdout-04 | pass | pass | unchanged |
| brief-holdout-05 | pass | pass | unchanged |
| brief-holdout-06 | pass | pass | unchanged |

The sole improved Case was `brief-holdout-03`; its only deterministic
transition was `summary_length: fail → pass`.

## Failure-mode analysis

| Case | v1 summary chars | v2 summary chars | v1 rule | v2 rule |
| --- | ---: | ---: | --- | --- |
| brief-holdout-01 | 95 | 67 | pass | pass |
| brief-holdout-02 | 84 | 82 | pass | pass |
| brief-holdout-03 | 58 | 62 | fail | pass |
| brief-holdout-04 | 60 | 60 | pass | pass |
| brief-holdout-05 | 71 | 83 | pass | pass |
| brief-holdout-06 | 63 | 63 | pass | pass |

Formal 60–120 compliance was 5/6 for v1 and 6/6 for v2. The v2 generation
target was hit by only 2/6 summaries. The evidence supports the narrow
length-safe intervention more strongly than it supports 70–100 as a stable
target interval.

## Guardrails

| Guardrail | Run 4 / v1 | Run 5 / v2 |
| --- | ---: | ---: |
| Required facts met | 18/18 | 18/18 |
| Unsupported-claim outputs | 0 | 0 |
| Language pass | 6/6 | 6/6 |
| Readability pass | 6/6 | 6/6 |
| JSON/schema regressions | 0 | 0 |
| Title regressions | 0 | 0 |
| Key-point regressions | 0 | 0 |
| Other deterministic regressions | 0 | 0 |

No new required-fact, groundedness, language, readability, structural, or
deterministic regression was observed.

## Human Review provenance

The sampled Holdout reviews were:

| Original review | Evaluation | Original | Corrective mode | Corrected | Effective |
| ---: | ---: | --- | --- | --- | --- |
| 5 | 21 | fail | corrective-re-review | pass | pass |
| 6 | 22 | fail | corrective-re-review | pass | pass |
| 7 | 24 | fail | corrective-re-review | pass | pass |
| 8 | 30 | fail | corrective-re-review | pass | pass |

All four originals were classified as procedure-invalid because the blind
Human Review renderer encoded raw responses containing a trailing newline as a
JSON string for display. Reviewers mistook the display-layer quotes and
escapes for the stored raw response's root type.

The original Human Reviews remain immutable. The append-only correction layer
records four authorized targets and four corrections. Corrective decisions are
separate from automatic `calculated_status` and did not alter any model
output, Rule, Grader, or evaluation record.

## Grader reliability

Two records were marked possible Grader diagnostic overreach:

- `candidate-8ef4e1268d13f5f7` — a real `summary_length` failure co-occurred
  with a wrapper/format interpretation inconsistent with the deterministic
  layer;
- `candidate-ffa603f79e0d6631` — deterministic rules passed, while the Grader
  reason still described a JSON/root-wrapper issue.

This limits confidence in those diagnostic explanations. It does not change
the independently persisted `calculated_status` or the formal paired result.

## Final recommendation

**Recommend Prompt v2**
**Confidence: Moderate**

The recommendation is limited to the current Grounded Structured Brief
Generation setup. It is supported by:

1. a clear, isolated Dev failure mode;
2. a minimal Prompt change directly targeting that mode;
3. recurrence of the same failure in Holdout v1;
4. repair of the paired failure in v2;
5. zero observed regressions;
6. stable required-fact, groundedness, language, and readability guardrails.

## Limitations

- Formal Holdout n=6;
- fixed fictional Case Set;
- one manual generator environment;
- one approved Grader Condition;
- no production traffic or online A/B test;
- no statistical significance or benchmark claim;
- 70–100 generation target hit only 2/6 times;
- two Grader diagnostic overreach records;
- Human Review renderer incident and corrective re-review;
- Prompt v2 timestamp capture artifact;
- superseded empty Run 2/3 history.

## Future validation

Broader validation is optional future work, not required to finish this current
experiment. A future study could use more Cases, additional fictional domains,
and repeated generator/Grader conditions to test whether the length-safe
intervention and the 70–100 target remain stable.

## Claims not supported by this experiment

This experiment does not establish that:

- Prompt v2 is statistically significantly better;
- Prompt v2 is universally superior;
- Prompt v2 improves overall model capability;
- Prompt v2 works across all domains or task families;
- Prompt v2 permanently solves summary-length failures;
- Prompt v2 reliably forces summaries into 70–100 characters;
- the project is a production or industry benchmark;
- the results represent real online traffic.

## Final integrity state

At the time of this report:

- Run 4 and Run 5 are closed;
- Prompt v1 and Prompt v2 remain frozen under the hashes above;
- `PRAGMA foreign_key_check` returned no violations;
- formal record counts remain 30 model outputs, 210 Rule results, 30 Grader
  results, 90 fact results, 30 evaluation results, 8 Human Reviews, 4
  correction targets, and 4 corrections;
- the formal SQLite database remains ignored by Git and was not modified by
  documentation work.
