# Methodology and data boundary

AI Output Eval Lab evaluates one fixed task: Grounded Structured Brief
Generation. The checked-in `db/seed_data/task_pack.json` records the fixed
Simplified-Chinese JSON contract and its reproducible hash. The checked-in
`db/seed_data/test_cases.json` is now the owner-approved formal Case Set: 24
fictional, self-contained Cases with 18 Dev and 6 Holdout Cases.

## Formal Case Set approval record

Owner approval date: **2026-08-13**. The owner approved the reviewed Case
content at case-set hash
`a55dea2a4f2b24897edc720f548109e21da4733f58e88f57cc2f96c46ebaaf09`.
Finalization then recorded `feasibility_qa_status: pass` for all 24 Cases and
recomputed every affected Case content hash. Because the feasibility status is
part of the canonical Case content, the resulting formal case-set hash is
`c2555bafffd6d8ac0730a438fe0963530676d63beb7cea7b13a3116ae59f6bb5`.
Dataset QA reports 24 total Cases, an 18/6 Dev/Holdout split, valid
source-fact traceability, feasibility QA pass, and `formal_ready: true`.

## Case annotations and source precedence

For every future Case, `source_material` is the final source of truth. Its
`source_facts` are manually maintained atomic annotations that must be
traceable back to that material; they are an index for review, not a competing
or higher-priority truth source. Every `required_fact_id` must be a subset of
the annotated fact IDs and is a hard requirement. A fact present in source
material but accidentally missing from `source_facts` is an annotation issue,
not automatic evidence of an unsupported model claim.

The evaluation is closed-world: factual assertions in an output require direct
support from `source_material`. A real ambiguity in the source or annotation is
reported as indeterminate rather than guessed. The system does not require
citations, character offsets, span labels, gold answers, or per-Case length
exceptions.

## Dataset QA and feasibility

Before any Case becomes formal, an owner reviews that a reasonable output can
cover all required facts, avoid unsupported claims, meet the fixed strict JSON
contract, and meet the shared title, summary, and key-point character limits.
The recorded `feasibility_qa_status` is evidence of this human QA; the software
does not attempt semantic feasibility solving. A Case marked `pending` or
`fail` cannot make a collection formal-ready.

Each Case carries a canonical content hash, source/fact traceability metadata,
and the shared Task Pack contract hash. Dataset QA validates annotations and
hashes, then computes an order-independent case-set hash. These hashes make a
reviewed collection reproducible; they do not turn the collection into a
benchmark.

The formal Case Set currently has an empty `explicit_forbidden_claims` list for
every Case. The formal experiment must therefore not claim to have tested
literal forbidden-claim detection; unsupported factual claims are primarily
assessed by the closed-world AI Grader.

## Experiment asset approval gate

`db/seed_data/experiment_assets_v1.json` contains four reproducible snapshots:
Prompt v1, Grader Prompt v1, Rubric v1, and Error Taxonomy v1. Each snapshot
has its exact content, SHA-256 content hash, version label, status, and owner
approval timestamp. The owner formally approved the four snapshots on
`2026-08-13T13:29:27Z`; each checked-in entry is therefore
`status: "approved"` with that timestamp. The approved hashes are Prompt v1
`07aa48853dbe0ed54ff88a2476ce6ec9be2cac4d2680dc2b41d0fc36c392ae4f`, Grader
Prompt v1 `c14dfcfde0d5902e2b42bdee399bb12d4eb81c62f546bee65cec9f215eb810b1`,
Rubric v1 `719cbba979f3657f5c164d947a03b02b77b8818c487259b8c850f68dd577b8eb`,
and Error Taxonomy v1
`ea8324fe5e865c1bb5bba755925b1fca452c90a49070d15dcfad32865a5d6338`.
Changing any snapshot content requires a new owner-approval gate.

Only an owner-reviewed manifest whose four v1 assets have matching hashes and
explicit approval timestamps can register one frozen Prompt v1 and one
owner-approved Grader Condition in SQLite. Prompt v1 or v2 cannot freeze
without owner approval. Prompt v2 may be drafted only after a closed Dev
Prompt v1 run has stored evaluation results and a non-empty evidence-based
change reason; it is still a draft until separately owner-approved and frozen.

The owner-approved Grader Prompt v1 records the strict pointwise JSON result contract:
the root contains exactly the seven semantic fields, required facts appear
exactly once, `met` requires non-empty output evidence while `not_met` and
`indeterminate` may use an empty evidence string, and `readability.label` is
one of `pass`, `fail`, or `indeterminate`. Unsupported-claim evidence may
reference any legal `source_facts.fact_id`, not only required facts; unknown
fact IDs are rejected at the Imports/Domain boundary. The rubric and taxonomy
also preserve the closed-world source precedence, ambiguity handling, fixed
diagnostic priority, and the separation from deterministic schema/length
checks.

## Split discipline and interpretation

The formal collection, after owner approval only, must contain exactly 18 Dev
Cases and 6 Holdout Cases under the same contract. Dev Cases support baseline
failure analysis and Prompt v2 design. Holdout Cases are first used after Prompt
v2 is approved and frozen, to reduce tuning leakage. This is personal-MVP
experiment discipline, not a strict blind test, formal benchmark, or
statistical validation.

Results remain descriptive and are reported with raw counts, denominators,
indeterminate rates, and the separation between calculated status and any
Human Review final decision. The project has no production traffic, live A/B
test, automated model API call, or claim of general model capability. Codex may
assist engineering and drafting, while the owner approves formal cases,
experiment assets, result review, and conclusions.

## Final experiment state

The owner-approved Formal Case Set contains 24 fictional, self-contained Cases:
18 Dev and 6 Holdout. Its full Case Set hash is
`c2555bafffd6d8ac0730a438fe0963530676d63beb7cea7b13a3116ae59f6bb5`.
The per-run hashes are split-specific: the Dev run uses the Dev-only hash
`a23f8d88ad1e35443d3b31bfcd0c60274b204cdbd0738d4ab21eefd24db3cb1c`, while the
Formal Holdout pair uses the Holdout-only hash
`b22b44b58162a69e74de8af7ab93f9f8507caf3f665f70a68ad630ead004bd6f`. A run's
`case_set_hash` is therefore not automatically the full 24-Case hash.

Prompt v1 is frozen under hash
`07aa48853dbe0ed54ff88a2476ce6ec9be2cac4d2680dc2b41d0fc36c392ae4f`.
After the closed Dev v1 run and failure analysis, the owner approved and froze
Prompt v2 under hash
`46198292143fa675fc9ad2cb0e724b6811aa3f2455b05f19a75f12e04aeaae74`.
The v2 change was deliberately narrow: it kept the formal summary range at
60--120 characters, added an approximate 70--100 generation target, and added
a silent check that may only use directly supported source facts when adjusting
length. The 70--100 range is a generation target, not a hard rule.

Formal Run 1 is the closed Dev v1 baseline (18 outputs, 12 pass, 6 fail,
0 indeterminate). All six failures were `summary_length` failures with
55--59-character summaries; JSON/schema, title, key-point, required-fact,
groundedness, language, and readability checks did not fail. The only valid
Prompt v2 design evidence came from this Dev failure analysis; Holdout was not
used to tune the prompt.

The superseded Holdout shells, Run 2 and Run 3 in `HOLDOUT-COMP-01`, used the
Dev-only hash, contained zero outputs and zero evaluations, and remain closed
for provenance history. They are not Formal Holdout evidence. The valid pair is
Run 4 (v1) and Run 5 (v2) in `HOLDOUT-COMP-02`, both closed, using the Holdout
hash, the same generator condition (`ChatGPT web UI (manual)`, visible model
`GPT-5.6 Sol`), `manual-generation-v1`, and Grader Condition 2.

## Evaluation layers and final interpretation

The primary comparison layer is the persisted automatic
`evaluation_results.calculated_status`. It is computed from deterministic Rule
Results and the pointwise blind Grader only; Human Review never recalculates or
overwrites it. The Human Review layer is reported separately as original
decision, correction decision (if any), and effective decision.

The Formal Holdout automatic result was 1 improved, 5 unchanged, 0 regressed,
and 0 indeterminate across six paired Cases. The sole improvement was
`brief-holdout-03`, where `summary_length` changed from fail to pass. v1 had
one summary-length failure and 5/6 summaries within 60--120; v2 had zero
summary-length failures and 6/6 within 60--120. Only 2/6 v2 summaries fell in
the 70--100 generation target, so the hard-rule improvement and the exact target
hit rate must not be conflated.

Across the Holdout pair, all 36 required facts were met, unsupported-claim
outputs were zero, language was 12/12 pass, and readability was 12/12 pass.
No new JSON/schema, title, key-point, language, readability, groundedness, or
other deterministic regression was observed. These are descriptive results for
this six-Case Formal Holdout, not statistical validation or a benchmark.

## Human Review correction methodology

Four sampled Holdout Human Reviews (reviews 5--8, evaluations 21, 22, 24, and
30) were later classified as procedure-invalid. The review packet renderer used
JSON-string encoding for raw responses with a trailing newline, and reviewers
mistook the display-layer quotes and escapes for the stored response's root
type. The original reviews remain immutable historical records.

An owner-authorized, append-only correction workflow recorded four correction
targets and four corrections with `review_mode: corrective-re-review`. All four
corrected decisions and effective decisions are `pass`. This correction layer
does not modify model outputs, Rules, Grader results, evaluation results, or
automatic `calculated_status`.

## Grader reliability and provenance artifacts

Two Holdout Grader records have `primary_error_type: other`:
`candidate-8ef4e1268d13f5f7` and `candidate-ffa603f79e0d6631`. Their reasons
contain JSON wrapper/format interpretations that are inconsistent with the
deterministic layer, so they are recorded as possible Grader diagnostic
overreach. This lowers confidence in those diagnostic explanations but does
not change the independently persisted automatic results or paired outcome.

Prompt v2's lifecycle call order was create, approve, then freeze. A caller
pre-captured timestamps, producing a microsecond-scale ordering artifact in
which approval/freeze can precede `created_at`; this is not a lifecycle-order
failure and the historical timestamps are not rewritten. The project also
retains the superseded empty Run 2/3 records rather than deleting provenance.

## Owner decision and claim boundary

The owner decision for this project is **Recommend Prompt v2**, with
**Moderate** confidence, for this Grounded Structured Brief Generation setup.
The recommendation is based on the isolated Dev failure mode, the matching
Holdout v1 failure and v2 repair, zero observed regressions, and stable semantic
guardrails. It does not claim statistical significance, universal superiority,
all-domain generalization, production performance, permanent elimination of
summary-length errors, or reliable 70--100 targeting. Broader validation is
optional future work, not a prerequisite to conclude this current experiment.
