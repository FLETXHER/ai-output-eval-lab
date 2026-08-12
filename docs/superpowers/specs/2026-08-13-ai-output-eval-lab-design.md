# AI Output Eval Lab — Design Specification

Status: design approved for implementation planning
Date: 2026-08-13
Scope: first MVP only

## 1. Product purpose

AI Output Eval Lab is a lightweight, reusable local workbench for prompt experiments and output evaluation. It demonstrates an end-to-end, explainable workflow:

```text
Task Pack
→ Test Cases
→ Prompt Versions
→ Model Outputs
→ Rule Checks
→ AI Grader Results
→ Human Review
→ Bad Case / Error Analysis
→ SQL Analysis
```

The first MVP contains one fixed task family, Grounded Structured Brief Generation, and compares Prompt v1 and Prompt v2 on paired cases. It is a personal LLM Evaluation / AI product analysis exercise, not a production platform, formal benchmark, online experiment, or claim about general model capability.

The project may use Codex for architecture, database, Python, Streamlit, tests, debugging, SQL, and documentation. The project owner participates in task design, case selection, evaluation criteria, result review, and conclusions; the repository must describe this boundary honestly.

## 2. MVP scope and non-goals

### In scope

- Python, Streamlit, SQLite, Pandas, and Python `sqlite3`.
- One fixed Task Pack: Grounded Structured Brief Generation.
- Twenty-four fictional, self-contained test cases: 18 Dev and 6 Holdout.
- Prompt v1, a Dev iteration, Prompt v2, and a Holdout comparison.
- Manual model-output collection from existing AI products.
- Structured import of AI Grader and Human Review results.
- Deterministic rule checks, semantic grading, tri-state aggregation, SQL analysis, Bad Case review, README, methodology/limitations documentation, and screenshots.

### Explicitly out of scope

React/Next.js, login, permissions, cloud databases, vector databases, RAG, agent frameworks, model training or fine-tuning, commercial model APIs, multi-user collaboration, live production A/B tests, complex plugin systems, a general-purpose DSL, and a generic Task Pack configuration platform.

The UI may display and edit the single fixed Task Pack's metadata and cases, but it must not become a general Task Pack Builder.

## 3. Locked evaluation protocol

### 3.1 Task definition and output contract

All 24 cases use the same task definition and the same output contract. Cases vary only in source facts and constraints; the MVP does not mix in rewriting, summarization, extraction, marketing copy, or another task family.

The required response is strict JSON:

```json
{
  "title": "string",
  "summary": "string",
  "key_points": ["string", "string", "string"]
}
```

After `strip()`, the raw response must be parsed directly by a standard strict JSON parser. The evaluator must not remove Markdown fences, extract a JSON substring, repair syntax, accept comments/trailing commas/single quotes/Python literals, or request a corrected response.

The root must be an object with exactly `title`, `summary`, and `key_points`. `title` and `summary` must be non-empty strings after trimming. `key_points` must contain exactly three non-empty strings after trimming. Parse validity and schema validity are recorded separately.

The fixed Task Pack length contract is:

- `title`: 4–20 characters;
- `summary`: 60–120 characters;
- every `key_point`: 6–40 characters;
- `key_points`: exactly 3 items.

Every length check uses `len(text.strip())`. Chinese characters, Latin letters, digits, punctuation, and internal spaces count as actual Python string characters. Token counts, word counts, and model tokenizers are not used. These values are this Task Pack's contract, not an industry standard, and cannot be relaxed for an individual case.

### 3.2 Case data and closed-world groundedness

`source_material` is the final source of truth that the model receives. `source_facts` is a human-maintained atomic index used for required fact IDs, grader evidence, and review; it never outranks the source material.

The MVP uses simple facts such as:

```json
[
  {"fact_id": "F01", "text": "..."},
  {"fact_id": "F02", "text": "..."}
]
```

`required_fact_ids` is a subset of `source_facts`. Every required fact is a critical hard requirement. Optional required facts, importance levels, weights, and partial credit do not exist in this MVP. Facts retained only for context or diagnostic analysis stay in `source_facts` and do not enter `required_fact_ids`.

For every case:

- every fact index entry must be traceable to `source_material`;
- a missing or incorrect annotation is a case-data issue, not automatically an unsupported model claim;
- every required fact must be accurately expressible by semantic equivalence, without requiring word-for-word matching;
- a factual proposition that can be judged true or false must be directly supported by `source_material`;
- this includes entity/event information, dates, numbers, attributes, causality, comparisons, degree/performance claims, outside background knowledge, and unsupported evaluative factual statements;
- natural connective language and faithful paraphrase are allowed;
- outside knowledge is never used to rescue a claim;
- genuine ambiguity, insufficient source wording, or conflicting case annotations produces `indeterminate`.

Before a case enters the formal Dev/Holdout set, Dataset QA must confirm that a reasonable output can satisfy the JSON schema, all required facts, the closed-world rule, and the fixed lengths. An infeasible case is edited; its length rules are not relaxed.

### 3.3 Language criterion

Source material, case instructions, prompts, and natural-language output values use Simplified Chinese. The JSON keys are fixed English schema keys and are excluded from language compliance.

Brand names, product models, necessary proper nouns, common abbreviations such as AI/USB-C/Wi-Fi, numbers, units, and source-provided foreign strings may remain. The body of the natural-language content must otherwise be Simplified Chinese.

`language_compliance` is a semantic Grader result with `pass`, `fail`, or `indeterminate`:

- `pass`: Simplified Chinese is the main natural-language expression and other characters are reasonably necessary;
- `fail`: English, Traditional Chinese, or another language is the main expression, or there is a long unnecessary mixed-language passage;
- `indeterminate`: the language boundary cannot be judged reliably.

It is a hard criterion. `fail` makes `calculated_status = fail`; `indeterminate` makes it indeterminate unless another deterministic hard failure already makes the result fail.

### 3.4 Dev/Holdout discipline

The 24 fixed cases are split into 18 Dev and 6 Holdout. This is an experiment-discipline device to reduce tuning leakage, not a strict blind test, formal benchmark, statistical validation, or independent external test set.

The required order is:

1. Freeze the complete case set, split, contract, and grader protocol.
2. Run Prompt v1 on Dev.
3. Use Dev failures and Bad Cases to design Prompt v2.
4. Optionally run exploratory Dev v2 iterations.
5. Freeze Prompt v2, recording its content hash and `frozen_at`.
6. Only then first use Holdout, creating separate v1 and v2 runs in a comparison group and viewing their outputs for comparison.
7. If Holdout results later drive another prompt change, that work is exploratory v3; it is not a second validation of the same Holdout.

Dev v1/v2 differences describe the tuning process. Holdout differences provide only directional, descriptive evidence on cases excluded from result-driven tuning. Results are reported with raw counts and paired changes, not statistical significance.

### 3.5 Generator protocol

For a primary v1/v2 paired comparison:

- use the same source product;
- use the same visible model name where available, otherwise record `not_visible`;
- use a clean new conversation for every Case × Prompt Version;
- do not ask follow-up questions or manually correct the response;
- record actual generation time and environment notes;
- perform corresponding runs in as short a time window as practical;
- do not select a better response from repeated generations.

The first actual generated response is the evaluation response even when it is invalid JSON, violates length, or is semantically poor. Only technical failures such as page load failure, network error, or no actual generated response permit a retry; retry count and reasons are recorded. A changed product, model, or materially changed environment is a different experimental condition and must not be treated as a prompt-only effect.

### 3.6 AI Grader protocol

Grading is pointwise and independent. Each candidate is evaluated in a clean, isolated Grader context. A Grader context may see only the fixed evaluation contract, source material, source facts/fact IDs, required fact IDs, applicable constraints, raw model response, rubric, and error taxonomy.

It must not see Prompt Version, v1/v2 labels, Dev/Holdout split, generator product, model name, run purpose, candidate order meaning, previous Grader results, calculated status, Human Review, analysis conclusions, or desired improvement directions. An internal anonymous `candidate_id` connects the result to the database.

The Grader must not compare v1 and v2 outputs. Candidate order may be randomized or at least not processed as all v1 followed by all v2, but isolation and metadata blindness are the primary controls.

Each applicable semantic result stores a label or score, concise reason, and evidence. Required facts use `fact_id` plus output evidence or an explicit statement that no evidence was found. Unsupported claims are stored as JSON objects containing the claim, raw output evidence, supporting fact IDs (empty when none support it), and reason. No span/offset system is required.

`grader_prompt`, rubric, and error taxonomy are versioned. A `grader_condition` records their actual reproducible snapshots or content, content hashes, version labels, product, visible model name or `not_visible`, and `created_at`. A primary comparison should use the same `grader_condition_id`; a changed condition is a distinct experiment and is not silently merged.

Generator and Grader products should be separated when practical. If not, the limitation is recorded and the conclusion is weakened accordingly.

### 3.7 Human Review protocol

Human Review never overwrites Rule, Grader, or calculated results. `final_decision` is stored only in `human_reviews` and is NULL until an actual review is completed.

The predeclared review queue is:

- every `calculated_status = indeterminate` result;
- every result with a detected unsupported factual claim;
- approximately 20% random sampling of remaining results with no obvious anomaly;
- sampling balanced as far as practical across Prompt v1/v2 and Dev/Holdout.

The sampling rule is fixed before viewing experimental results and is not chosen after seeing outcomes. Reviewers should not see Prompt Version or prior Grader conclusions when making an independent judgment. The application displays calculated status, review coverage, and final decision separately.

### 3.8 Three-state decision protocol

`calculated_status` is one of `pass`, `fail`, or `indeterminate` and is computed only from deterministic Rule Results and AI Grader semantic results by Domain aggregation rules. Human Review never participates in recalculating it and never creates a human-based calculated-status snapshot.

`pass` requires:

- every applicable schema, field, count, length, and explicit-forbidden-claim hard rule to pass;
- every `required_fact_id` to be `met`;
- no established unsupported factual claim;
- language compliance to pass.

`fail` occurs on any deterministic hard failure, or on a valid Grader result that confirms a required fact is missing, an unsupported factual claim exists, or language compliance fails.

`indeterminate` occurs when a required Grader result is missing or structurally invalid, semantic evidence is insufficient, or applicable Rule and Grader results conflict without a valid automatic resolution. A deterministic hard failure takes precedence over an otherwise indeterminate semantic result.

Technical failure is not a quality `fail`. If no model response exists, the case is reported as technical failure/not evaluated rather than silently counted as a quality result.

`final_decision` is independent and may remain NULL, or be `pass`, `fail`, or `indeterminate` after Human Review. For example, an automatic `indeterminate` and a human `pass` are both retained and displayed.

Readability, non-critical expression preferences, and `primary_error_type` are diagnostic by default. They do not compensate for a missing required fact and do not determine pass/fail in this Task Pack.

## 4. Architecture and components

The MVP is a lightly layered monolith. The layers clarify responsibility but do not introduce enterprise-style interfaces, abstract base classes, dependency injection, factories, ORM, or Web APIs.

```text
                         ┌→ Domain Evaluation Rules
Streamlit UI → Application Services
                         └→ Repositories → SQLite

External raw input → Imports → Application Services
Analysis → read-only SQL queries / Pandas → SQLite
```

### Streamlit UI

Multipage Streamlit UI handles forms, filters, import entry points, review forms, and display. It calls Application functions and does not implement evaluation rules.

### Application Services

Application functions orchestrate run lifecycle, prompt freeze, output import, Grader import, Human Review, final adjudication, candidate/run associations, and allowed-operation checks. They call Domain functions and Repositories; they do not duplicate status logic.

### Domain

Pure Python functions and only necessary small classes implement the fixed Task Pack contract, deterministic Rule Checks, Grader-result schema/normalization, required-fact and groundedness result data rules, language result normalization, calculated-status aggregation, and immutable final-decision constraints. Domain does not access Streamlit, SQLite, Repositories, or external AI products.

### Imports

Imports parse JSON/file structure, validate basic types and required fields, retain raw input, and return explicit validation errors. Imports never write SQLite directly or bypass Application lifecycle checks.

### Repositories

Repositories use Python `sqlite3` directly. They expose simple query/write functions, not an interface hierarchy, and do not implement evaluation rules. Every connection explicitly executes:

```sql
PRAGMA foreign_keys = ON;
```

Schema initialization is reproducible from a checked-in SQL file. No ORM or migration framework is required for the MVP.

### Analysis

Analysis is read-only. Versioned SQL queries and Pandas formatting produce descriptive paired comparisons, status distributions, error summaries, Bad Cases, and Human Review coverage. Analysis never modifies data or recalculates evaluation outcomes.

## 5. Database schema

The MVP uses exactly these tables:

1. `task_packs`
2. `test_cases`
3. `prompt_versions`
4. `evaluation_runs`
5. `model_outputs`
6. `rule_results`
7. `grader_conditions`
8. `grader_results`
9. `grader_fact_results`
10. `evaluation_results`
11. `human_reviews`

### 5.1 Common rules

- Primary keys and foreign keys are structured columns.
- Statuses, split, version labels, hashes, timestamps, IDs, and query dimensions are structured columns.
- Variable collections and raw payloads are JSON TEXT validated by Application/Domain functions.
- Raw model responses, raw Grader payloads, Rule results, Grader results, calculated results, and Human Reviews are append-only records from the perspective of later workflow steps.
- A Case or Prompt used by a run cannot be edited in place; a changed Case revision or Prompt version gets a new content hash and identity.
- A run has at most one model-output slot per Test Case; a model-output slot has at most one Grader result per Grader condition and one automatic evaluation result for that output/condition.
- All SQLite connections use `PRAGMA foreign_keys = ON`.

### 5.2 Table responsibilities

`task_packs` stores the fixed Pack metadata, Simplified Chinese requirement, contract version/hash, `title` min/max, `summary` min/max, `key_points` count, and key-point min/max.

`test_cases` stores Task Pack ID, case key/revision, split, source material, `source_facts_json`, `required_fact_ids_json`, explicit forbidden claims JSON, task notes, feasibility-QA status, and content hash.

`prompt_versions` stores prompt text, version label, change reason, content hash, draft/frozen status, and `frozen_at`. Referenced content is immutable.

`evaluation_runs` stores one Prompt Version per run, `comparison_group_id`, split, Case set hash, contract hash, generator product, visible model name or `not_visible`, environment notes, protocol version, lifecycle status, and timestamps. Prompt v1 and v2 are separate runs associated by `comparison_group_id`; `evaluation_run_prompts` does not exist.

`model_outputs` stores run ID, Test Case ID, anonymous candidate ID, raw response, output hash, generation time, technical retry count, and technical retry reasons. The raw response is unchanged. If technical failure produces no actual response, raw response and output hash may be NULL and the slot is reported as technical failure/not evaluated; no quality conclusion is fabricated. `model_outputs` does not repeat `prompt_version_id`; it is derived through `run_id → evaluation_runs.prompt_version_id`.

`rule_results` stores one deterministic Rule result per applicable Rule: Rule key/version, pass/fail/not-applicable status, actual/expected values where useful, reason, and calculation time. Parse, schema, field-length, count, and other checks remain separately queryable.

`grader_conditions` stores the actual Grader prompt snapshot, rubric snapshot, error taxonomy snapshot, their content hashes, version labels, product, visible model name or `not_visible`, and creation time.

`grader_results` stores a model-output ID, Grader condition ID, raw imported Grader JSON, import/normalization status, normalized semantic fields, language compliance, readability, error types, unsupported-claims JSON, reasons, evidence, and timestamps. Unsupported claims are not a separate table.

`primary_error_type` is retained as the single diagnostic category used by the default charts. The normalized result may also retain a JSON list of additional error types when one output has more than one failure; this list never changes the hard-status rules.

`grader_fact_results` stores one result per Grader result and required fact: fact ID, met/not-met/indeterminate label, output evidence, and reason. It exists so required-fact failure is directly queryable in SQL.

`evaluation_results` stores the automatic Domain aggregation for a model output and Grader condition: model-output ID, Grader result ID (nullable when a required Grader result is absent), Grader condition ID, aggregation-rule version, calculated status, blocking reasons JSON, and calculation time. Human Review never changes this table and never creates a human-based status snapshot.

`human_reviews` stores evaluation-result ID, review scope, blind-review status, review evidence JSON, review reason, final decision, and review time. `final_decision` is NULL until a review exists and never overwrites Rule, Grader, or evaluation records.

## 6. End-to-end data flow

1. Dataset QA creates the fixed Pack and 24 cases, validates source/fact relationships and feasibility, and records hashes.
2. Prompt v1 is saved and frozen for the baseline experiment.
3. A Dev run is created for Prompt v1 and its generator condition.
4. Manual model responses are imported unchanged; first actual responses are retained and technical retries are recorded separately.
5. Domain Rule Checks run on each raw response.
6. Pointwise Grader results are entered through Imports using an isolated, blind condition.
7. Application calls Domain aggregation and saves `evaluation_results`.
8. Dev Bad Cases and failure patterns inform Prompt v2. Each revision is a new Prompt Version.
9. Prompt v2 is frozen with hash and `frozen_at` before Holdout is first viewed.
10. Separate v1 and v2 Holdout runs are created in a comparison group and run under matching generator conditions.
11. Human Review applies the predeclared queue and saves independent final decisions.
12. Analysis reads only from SQLite, uses versioned SQL/Pandas queries, and reports Dev and Holdout separately.

## 7. Error handling and lifecycle rules

### Raw output and Rule errors

Raw output is never repaired. A parse failure is a Rule failure; a schema failure does not suppress semantic diagnosis. Field-level checks are `not_applicable` only when the relevant field cannot be read reliably.

### Grader import errors

Invalid Grader input is retained with an invalid import/normalization status and explicit errors. It does not produce guessed semantic labels. If no valid required Grader result exists, calculated status is indeterminate unless an independent deterministic hard failure already makes it fail.

### Semantic ambiguity

Insufficient evidence, source ambiguity, annotation conflict, and unresolved Rule/Grader conflict remain indeterminate. The system never guesses pass or fail.

### Technical failures

Retries are allowed only for explicit technical failure and must record count/reasons. Bad quality is never a retry reason. A missing response is shown as technical failure/not evaluated, not silently excluded and not converted to quality fail.

### Lifecycle violations

Application blocks Holdout runs before Prompt v2 freeze, edits to referenced immutable content, mismatched Case/run associations, ordinary output imports after a run is closed, and paired analyses with mismatched split/hash/generator conditions. A later prompt change driven by Holdout is labeled exploratory v3.

### Persistence failures

Multi-record writes use SQLite transactions. Errors roll back the transaction and return an actionable UI error; partial evaluation records are not committed.

## 8. Analysis contract

Analysis queries are checked-in and read-only. Primary reports include:

- total assigned cases;
- model responses received;
- technical failure/not-evaluated count;
- determinate cases;
- pass rate among determinate cases;
- indeterminate count and rate;
- calculated-status distribution;
- final-decision distribution and Human Review coverage;
- paired improved/regressed/unchanged/indeterminate counts;
- Rule failures, required-fact failures, unsupported claims, error types, and Bad Cases.

The denominator and exclusions are shown explicitly. Dev and Holdout are never silently pooled. No statistical significance test, confidence claim, benchmark score, or generalization claim is included.

## 9. Testing strategy

### Domain unit tests

Tests cover strict parsing, schema/field-check separation, length counting, language labels, required-fact and groundedness normalization, Grader evidence validation, status precedence, indeterminate behavior, and immutable Human Review separation.

### Repository integration tests

Temporary SQLite databases verify schema initialization, foreign keys, JSON round trips, relationships, uniqueness, transactions, rollback, and analysis queries. Tests assert that each connection enables `PRAGMA foreign_keys = ON`.

### Application workflow tests

Tests cover Prompt freeze, Dev/Holdout lifecycle gates, comparison-group comparability, first-response capture, technical retries, Grader-condition association, invalid imports, calculated-status generation, and NULL-to-final-decision review flow.

### Streamlit smoke/AppTest tests

Small tests verify startup, navigation, visible validation errors, import flow, status separation, and Analysis rendering. No additional Web API or frontend testing framework is introduced.

Representative fixtures include valid pass, schema failure, readable fields with an extra schema field, required-fact failure, unsupported claim, language failure, semantic indeterminate, invalid Grader JSON, and technical failure.

## 10. MVP acceptance criteria

The MVP is complete when all of the following are true:

- Streamlit starts locally against a reproducibly initialized SQLite database.
- The repository contains one fixed Task Pack, 24 cases, 18 Dev cases, and 6 Holdout cases.
- Dataset QA records source traceability, feasibility, and hashes.
- Prompt v1, Dev analysis, Prompt v2, v2 freeze, and separate v1/v2 Holdout runs can be demonstrated.
- Raw model responses can be entered/imported without repair or quality-based retries.
- Strict parsing, schema, field-level length, required-fact, closed-world, and language evaluation are visible and testable.
- Versioned, blind, pointwise Grader results can be imported with reason/evidence.
- `calculated_status` is automatically reproducible from Rule and Grader data and remains separate from `final_decision`.
- Human Review sampling and coverage are visible, including automatic indeterminate and final human decisions.
- SQL/Pandas analysis shows paired changes, statuses, indeterminate rates, failures, Bad Cases, and limitations without significance claims.
- Domain, Repository, Application, and UI tests pass.
- README, methodology, limitations, SQL analysis, representative Bad Cases, and screenshots are included.
- Documentation states the personal constructed-data boundary, lack of production traffic/API/benchmark/statistical validation, and the role of Codex assistance honestly.

## 11. Recommended project structure

```text
AI Output Eval Lab/
├─ app.py
├─ README.md
├─ pyproject.toml
│
├─ src/
│  └─ eval_lab/
│     ├─ domain/
│     │  ├─ task_pack.py
│     │  ├─ rules.py
│     │  ├─ grader_contract.py
│     │  └─ status.py
│     ├─ application/
│     │  ├─ runs.py
│     │  ├─ prompts.py
│     │  ├─ outputs.py
│     │  ├─ grading.py
│     │  └─ reviews.py
│     ├─ repositories/
│     │  └─ sqlite.py
│     ├─ imports/
│     │  ├─ model_outputs.py
│     │  ├─ grader_results.py
│     │  └─ human_reviews.py
│     ├─ analysis/
│     │  ├─ queries.sql
│     │  └─ reports.py
│     └─ ui/
│        ├─ pages/
│        │  ├─ overview.py
│        │  ├─ task_pack.py
│        │  ├─ test_cases.py
│        │  ├─ prompt_versions.py
│        │  ├─ model_outputs.py
│        │  ├─ evaluation.py
│        │  └─ analysis.py
│        └─ components.py
├─ db/
│  ├─ schema.sql
│  └─ seed_data/
│     ├─ task_pack.json
│     └─ test_cases.json
├─ tests/
│  ├─ domain/
│  ├─ repositories/
│  ├─ application/
│  └─ ui/
└─ docs/
   ├─ methodology.md
   ├─ limitations.md
   ├─ screenshots/
   └─ superpowers/
      └─ specs/
```

Modules should remain simple Python functions unless a small class is genuinely useful. A small module may be merged with a neighboring module if its responsibilities remain clear; no generic framework layer should be added.

## 12. Design invariants

- Domain has no persistence or UI dependency.
- UI never implements evaluation rules.
- Imports never bypass Application Services.
- Repositories never implement evaluation rules.
- Raw inputs are preserved and never silently repaired.
- Prompt Version is derived through `model_outputs.run_id → evaluation_runs.prompt_version_id`.
- v1/v2 runs are linked by `comparison_group_id`, not an extra prompt-run join table.
- Unsupported claims are JSON in `grader_results`; required fact results are rows in `grader_fact_results`.
- Human Review produces only `final_decision` and review evidence; it never modifies calculated status.
- Technical failures remain separate from quality outcomes.
- Analysis is read-only and descriptive.
