# Methodology and data boundary

AI Output Eval Lab evaluates one fixed task: Grounded Structured Brief
Generation. The checked-in `db/seed_data/task_pack.json` records the fixed
Simplified-Chinese JSON contract and its reproducible hash. At this engineering
stage, `db/seed_data/test_cases.json` contains a 24-Case draft (18 Dev and 6
Holdout Cases). Every Case remains `feasibility_qa_status: pending`: the file
is not the formal dataset and must not be presented as owner-approved or ready
for an experiment. Owner review of every Case is required before any status can
be changed to `pass` or any formal Case-set hash/date is recorded.

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
