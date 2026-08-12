# AI Output Eval Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved local AI Output Eval Lab MVP as a small, testable Streamlit + SQLite workbench that demonstrates Prompt v1 → Dev analysis → Prompt v2 → Holdout comparison for Grounded Structured Brief Generation.

**Architecture:** Streamlit UI calls Application Services. Application Services call pure Domain functions and simple Python sqlite3 Repository functions. Imports validate external raw data before Application persists it. Analysis is read-only SQL/Pandas. No API, ORM, Web API, DSL, plugin system, or complex frontend is introduced.

**Tech Stack:** Python, Streamlit, SQLite, sqlite3, Pandas, pytest, and Streamlit AppTest. Use standard-library JSON, hashing, datetime, and typing utilities. Do not add model SDKs or a network-dependent evaluator.

## Global Constraints

- Exactly one fixed Task Pack: Grounded Structured Brief Generation.
- Strict JSON object with exactly title, summary, and key_points; key_points has exactly three non-empty strings.
- Task Pack lengths: title 4–20, summary 60–120, each key_point 6–40 characters; use len(text.strip()), not tokens or words.
- Source material, instructions, prompts, and natural-language values use Simplified Chinese; necessary names, models, abbreviations, numbers, units, and source-provided foreign strings remain allowed.
- source_material is the final source of truth. source_facts is a traceable atomic index. Every required_fact_id is a critical hard requirement.
- Closed-world groundedness: every factual proposition must be directly supported by source_material; genuine ambiguity is indeterminate.
- Formal data is exactly 24 fictional self-contained cases: 18 Dev and 6 Holdout. Do not claim the dataset is complete until the owner reviews it.
- Holdout is first used only after Prompt v2 is frozen with content hash and frozen_at. It is tuning-excluded discipline, not a blind test, benchmark, or statistical validation.
- Each Case × Prompt Version stores the first actual response. No quality retry, correction, or follow-up. Technical failures alone may retry and must record reasons.
- v1/v2 use separate evaluation_runs linked by comparison_group_id. Each run has one prompt_version_id. model_outputs does not repeat it.
- AI Grader is pointwise, independent, isolated, version-blind, and candidate-anonymous; it sees raw output, never repaired output.
- Model-facing generation packets contain only the fixed user task/output contract, Case-visible instructions/constraints, source_material, and the actual prompt_text. Internal facts, IDs, split, hashes, labels, run metadata, and evaluation annotations stay outside the copied text.
- Formal blind Human Review has a separate allowlisted context and hides Grader/automatic results until the review decision is submitted; after submission, automatic results and final_decision may be shown together.
- calculated_status is pass, fail, or indeterminate and is computed only from deterministic Rules and Grader results. Human Review never recomputes it.
- final_decision lives only in human_reviews and is NULL until actual review. It never overwrites Rule, Grader, or calculated results.
- Analysis separately reports calculated status, final decision, review coverage, determinate denominators, and indeterminate rates. Dev and Holdout are not silently pooled.
- The only database tables are task_packs, test_cases, prompt_versions, evaluation_runs, model_outputs, rule_results, grader_conditions, grader_results, grader_fact_results, evaluation_results, and human_reviews.
- Every SQLite connection explicitly executes PRAGMA foreign_keys = ON.
- Raw inputs are preserved. Imports reject invalid input with explicit errors and never repair, extract, or rewrite it.
- Domain has no persistence/UI/external-AI dependency. Repositories do not implement evaluation rules. UI does not implement evaluation rules. Analysis is read-only.
- Do not add React/Next.js, auth, permissions, cloud DB, vector DB, RAG, Agent Framework, training/fine-tuning, commercial model APIs, collaboration, live A/B testing, plugins, a generic Task Pack Builder, or a general-purpose DSL.

---

## File map and vertical-slice order

The repository currently contains only the approved design specification. Add these focused files:

```text
app.py
pyproject.toml
.gitignore
src/eval_lab/{__init__.py,domain,application,repositories,imports,analysis,ui}
src/eval_lab/domain/{__init__.py,task_pack.py,rules.py,grader_contract.py,packets.py,status.py}
src/eval_lab/application/{__init__.py,cases.py,prompts.py,runs.py,outputs.py,packets.py,grading.py,reviews.py}
src/eval_lab/repositories/{__init__.py,sqlite.py}
src/eval_lab/imports/{__init__.py,test_cases.py,model_outputs.py,grader_results.py,human_reviews.py}
src/eval_lab/analysis/{__init__.py,queries.sql,reports.py}
src/eval_lab/ui/{__init__.py,components.py,pages}
src/eval_lab/ui/pages/{__init__.py,overview.py,task_pack.py,test_cases.py,prompt_versions.py,model_outputs.py,evaluation.py,analysis.py}
db/schema.sql
db/seed_data/task_pack.json
db/seed_data/test_cases.json
db/seed_data/experiment_assets_v1.json
db/seed_data/experiment_assets_final.json
tests/{conftest.py,fixtures,domain,repositories,application,imports,analysis,ui}
docs/{methodology.md,limitations.md,findings.md,screenshots}
```

Tasks 1–8 form a non-formal demo vertical slice. Official 24-case content is deliberately later.

## Task 1: Bootstrap package and test harness

**Files**

- Create pyproject.toml, .gitignore, app.py.
- Create package init files under src/eval_lab and its subpackages.
- Create tests/conftest.py and tests/test_import.py.

**Interfaces**

- tests/conftest.py provides repo_root: Path and temporary_db_path: Path.
- app.py is a minimal Streamlit shell and contains no evaluation rule.

- [ ] Write the failing import test:

```python
def test_package_imports():
    import eval_lab
    import eval_lab.domain
    import eval_lab.application
    import eval_lab.repositories
    import eval_lab.imports
    import eval_lab.analysis
    import eval_lab.ui
```

- [ ] Run before setup:

```powershell
python -m pytest tests/test_import.py -q
```

Expected: failure because the package does not exist.

- [ ] Add pyproject.toml with src layout, runtime dependencies streamlit and pandas, dev dependency pytest, and pytest pythonpath = ["src"]. Do not add an API client, ORM, or frontend framework.
- [ ] Add the minimal app shell:

```python
import streamlit as st
st.set_page_config(page_title="AI Output Eval Lab", layout="wide")
st.title("AI Output Eval Lab")
st.caption("Prompt evaluation workbench")
```

- [ ] Run:

```powershell
python -m pytest tests/test_import.py -q
python -m compileall -q app.py src
```

- [ ] Commit:

```powershell
git add pyproject.toml .gitignore app.py src tests
git commit -m "chore: bootstrap eval lab package"
```

**Completion standard:** Package imports, shell compiles, and pytest discovers tests without a manual PYTHONPATH override.

## Task 2: Implement exact SQLite schema and connection boundary

**Files**

- Create db/schema.sql and src/eval_lab/repositories/sqlite.py.
- Create tests/repositories/test_sqlite.py.
- Modify tests/conftest.py.

**Interfaces**

```python
def connect(db_path: str | Path) -> sqlite3.Connection: ...
def initialize_database(conn: sqlite3.Connection, schema_path: str | Path) -> None: ...
def transaction(conn: sqlite3.Connection) -> ContextManager[sqlite3.Connection]: ...
def table_names(conn: sqlite3.Connection) -> set[str]: ...
class SchemaInitializationError(RuntimeError): ...
```

- [ ] Write tests asserting PRAGMA foreign_keys is 1, schema initialization creates exactly the eleven approved tables, invalid foreign keys fail, transaction rollback leaves no rows, and a deliberately broken schema leaves an empty fresh database with no partially created tables.
- [ ] Run before implementation:

```powershell
python -m pytest tests/repositories/test_sqlite.py -q
```

- [ ] Write schema.sql with exactly the eleven tables. Use integer primary keys, foreign keys, JSON TEXT fields, and stable enum CHECK constraints. Include:

  - task_packs: Pack key, contract version/hash, language, title/summary/key-point min/max/count, timestamps.
  - test_cases: Pack FK, case key/revision, dev/holdout split, source material, source_facts_json, required_fact_ids_json, explicit_forbidden_claims_json, task notes, feasibility QA status, content hash, timestamps; unique Pack/case/revision.
  - prompt_versions: label, prompt text, change reason, content hash, draft/frozen status, nullable owner_approved_at, frozen_at, timestamps.
  - evaluation_runs: comparison group, Prompt FK, split, Case set hash, contract hash, generator product, visible model or not_visible, environment notes, protocol version, lifecycle status, timestamps.
  - model_outputs: Run FK, Case FK, anonymous candidate ID, generation packet version/hash, nullable raw response/hash/generation time, retry count/reasons JSON, timestamps; unique Run/Case.
  - rule_results: output FK, rule key/version, pass/fail/not_applicable, actual/expected JSON, reason, timestamp; unique output/rule/version.
  - grader_conditions: product, visible model or not_visible, actual grader prompt/rubric/error-taxonomy snapshots, hashes, version labels, nullable owner_approved_at, timestamp.
  - grader_results: output FK, condition FK, blind packet version/hash, raw payload, import status, normalized semantic JSON, language/readability/error fields, unsupported claims JSON, reason/evidence JSON, timestamp; unique output/condition.
  - grader_fact_results: Grader FK, fact ID, met/not_met/indeterminate, output evidence, reason; unique Grader/fact.
  - evaluation_results: output FK, nullable Grader FK, Grader condition FK, aggregation rule version, calculated status, blocking reasons JSON, timestamp; unique output/condition.
  - human_reviews: Evaluation FK, review scope, blind flag, evidence JSON, reason, nullable final decision, timestamp; unique Evaluation.

  Do not add a prompt-run join table or unsupported-claim table.
- [ ] Implement connect with row_factory = sqlite3.Row and explicit PRAGMA foreign_keys = ON. Do not call sqlite3.executescript for initialization because it can issue an implicit commit. Instead, read schema.sql, accumulate complete statements using sqlite3.complete_statement, execute each statement with conn.execute inside an explicit BEGIN/COMMIT transaction, and raise SchemaInitializationError on any parse or SQL error after rollback.
- [ ] Add a broken-schema test that appends an invalid CREATE statement after a valid table statement; assert initialize_database raises SchemaInitializationError and table_names(conn) remains empty. This proves a fresh initialization cannot silently leave a half-created database.
- [ ] Run:

```powershell
python -m pytest tests/repositories/test_sqlite.py -q
```

- [ ] Commit:

```powershell
git add db/schema.sql src/eval_lab/repositories/sqlite.py tests/conftest.py tests/repositories/test_sqlite.py
git commit -m "feat: add sqlite schema boundary"
```

**Completion standard:** A fresh DB has exactly eleven tables, foreign keys are enabled on every connection, and rollback is tested.

## Task 3: Implement Task Pack contract and deterministic Rules

**Files**

- Create src/eval_lab/domain/task_pack.py and rules.py.
- Create tests/domain/test_task_pack.py and test_rules.py.

**Interfaces**

```python
TASK_PACK_KEY: str = "grounded_structured_brief_generation"
CONTRACT_VERSION: str = "1.0"
TASK_PACK_CONTRACT: dict[str, object]
def canonical_json_hash(value: object) -> str: ...
def validate_case_record(case: Mapping[str, object]) -> list[str]: ...
def validate_task_pack_contract(pack: Mapping[str, object]) -> list[str]: ...
def parse_raw_json_response(raw_response: str) -> tuple[object | None, str | None]: ...
def run_deterministic_rules(raw_response: str, contract: Mapping[str, object], forbidden_claims: Sequence[str]) -> dict[str, object]: ...
```

Each Rule result has rule_key, status pass/fail/not_applicable, actual, expected, and reason; the function also returns parsed_value or None.

- [ ] Write tests for exact lengths, exact three key points, Simplified Chinese requirement, stable contract hash, missing/duplicate fact IDs, required subset, and source/fact traceability metadata.
- [ ] Write strict parser tests. A fence test may build the fence with chr(96) * 3 so the test itself does not auto-strip it. Add parse failure, extra field, wrong type, empty string, four key points, strip-based character count, and literal forbidden phrase tests.
- [ ] Run before implementation:

```powershell
python -m pytest tests/domain/test_task_pack.py tests/domain/test_rules.py -q
```

- [ ] Implement parsing as json.loads(raw_response.strip()) on a copy. Never remove fences, extract substrings, repair syntax, or change stored raw text. schema_pass requires exactly the three keys and fixed types. Field rules run whenever the relevant field is readable; otherwise not_applicable. Explicit forbidden claims are literal deterministic checks only.
- [ ] validate_case_record checks IDs, required subset, split, non-empty source, and feasibility status enum. It does not pretend to prove semantic feasibility.
- [ ] Run and inspect:

```powershell
python -m pytest tests/domain/test_task_pack.py tests/domain/test_rules.py -q
```

- [ ] Commit:

```powershell
git add src/eval_lab/domain/task_pack.py src/eval_lab/domain/rules.py tests/domain/test_task_pack.py tests/domain/test_rules.py
git commit -m "feat: add task pack contract and rule checks"
```

**Completion standard:** Strict parse/schema behavior, fixed lengths, literal forbidden-claim checks, annotation validation, and field applicability are deterministic and tested.

## Task 4: Implement Grader normalization and tri-state aggregation

**Files**

- Create src/eval_lab/domain/grader_contract.py and status.py.
- Create tests/domain/test_grader_contract.py and test_status.py.

**Interfaces**

```python
def normalize_grader_payload(payload: Mapping[str, object], required_fact_ids: Sequence[str]) -> dict[str, object]: ...
def validate_grader_payload(payload: Mapping[str, object], required_fact_ids: Sequence[str]) -> list[str]: ...
def aggregate_calculated_status(rule_results: Sequence[Mapping[str, object]], grader_result: Mapping[str, object] | None, required_fact_ids: Sequence[str], aggregation_rule_version: str = "1.0") -> dict[str, object]: ...
```

Normalized Grader payload must contain language_compliance, required_facts, unsupported_claims, readability, primary_error_type, secondary_error_types, and grader_reason. Required facts use fact_id, met/not_met/indeterminate, output_evidence, and reason. Unsupported claims use claim, output_evidence, supporting_fact_ids, and reason.

- [ ] Test valid payload, missing/duplicate required fact, invalid labels, unsupported blind metadata, unsupported fact ID, missing evidence/reason, unsupported claims, and explicit indeterminate reason.
- [ ] Include language hard-criterion cases: language fail makes calculated_status fail; language indeterminate makes it indeterminate unless another deterministic hard failure already makes it fail.
- [ ] Test status precedence:

```python
def test_schema_failure_wins_over_indeterminate_grader():
    result = aggregate_calculated_status(
        [{"rule_key": "schema_pass", "status": "fail", "reason": "extra field"}],
        {"language_compliance": {"label": "indeterminate"}, "required_facts": []},
        ["F01"],
    )
    assert result["calculated_status"] == "fail"

def test_missing_grader_is_indeterminate_without_hard_failure():
    result = aggregate_calculated_status(
        [{"rule_key": "schema_pass", "status": "pass"}], None, ["F01"]
    )
    assert result["calculated_status"] == "indeterminate"
```

- [ ] Run before implementation:

```powershell
python -m pytest tests/domain/test_grader_contract.py tests/domain/test_status.py -q
```

- [ ] Implement precedence: deterministic hard failure → fail; valid semantic confirmation of missing required fact, unsupported claim, or language failure → fail; missing/invalid evidence or unresolved indeterminate → indeterminate; all hard criteria pass → pass. Readability and error types never affect status. The function accepts no Human Review argument.
- [ ] Run all domain tests and commit:

```powershell
python -m pytest tests/domain -q
git add src/eval_lab/domain/grader_contract.py src/eval_lab/domain/status.py tests/domain/test_grader_contract.py tests/domain/test_status.py
git commit -m "feat: add grader normalization and status aggregation"
```

**Completion standard:** Grader data has a strict blind-compatible shape and calculated_status is a pure Rule + Grader function.
## Task 5: Add deterministic generation and blind-Grader packets

**Files**

- Create src/eval_lab/domain/packets.py.
- Create src/eval_lab/application/packets.py.
- Create tests/domain/test_packets.py.
- Create tests/application/test_packets.py.
- Modify db/schema.sql and repository/application tests for packet version/hash fields.

**Interfaces**

```python
def render_generation_packet(case: Mapping[str, object], task_pack_contract: Mapping[str, object], prompt_version: Mapping[str, object]) -> dict[str, object]: ...
def render_blind_grader_packet(candidate_id: str, task_pack_contract: Mapping[str, object], source_material: str, source_facts: Sequence[Mapping[str, str]], required_fact_ids: Sequence[str], constraints: Mapping[str, object], raw_model_response: str, grader_prompt: str, rubric: str, error_taxonomy: str) -> dict[str, object]: ...
def render_blind_human_review_packet(candidate_id: str, source_material: str, task_instructions: str, constraints: Mapping[str, object], raw_model_response: str, human_review_rubric: str, decision_options: Sequence[str]) -> dict[str, object]: ...
def build_generation_packet(conn, run_id: int, test_case_id: int) -> dict[str, object]: ...
def build_blind_grader_packet(conn, model_output_id: int, grader_condition_id: int) -> dict[str, object]: ...
def build_blind_human_review_packet(conn, evaluation_result_id: int) -> dict[str, object]: ...
```

`render_generation_packet` must select only model-facing fields from its mappings: the Task Pack's natural-language task description/output contract, Case-visible instructions/constraints and source_material, and Prompt Version `prompt_text`. It must ignore internal annotations even when they are present in the input mappings.

All packet renderers return packet_version, text, payload, and content_hash. Use a fixed section order, UTF-8, normalized LF newlines, no trailing whitespace, and canonical JSON serialization with ensure_ascii=False, sort_keys=True, and stable separators. Hash the exact rendered text with SHA-256. For generation, `payload` and `text` are the model-facing allowlist only; for blind Human Review, the allowlisted payload/text is reviewer-facing while packet provenance remains application-only and is never shown before submission.

- [ ] Write Domain tests proving the same Case × Prompt Version produces byte-identical model-facing text/hash across repeated renders, changing the Prompt text changes the hash, and changing source material or visible Case instructions changes the hash.
- [ ] Add generation-packet leakage tests using a Case and Prompt Version populated with sentinel internal values. Assert that neither `text` nor model-facing `payload` contains source_facts/fact IDs, required_fact_ids, split, Case revision/hash, Prompt Version label, Prompt content hash, comparison_group_id, run/generator metadata, or any Rule/Grader/Human Review value. Assert that the actual `prompt_text` is present.
- [ ] Write blind-packet tests that assert the payload/text contains candidate_id, contract, source material, source facts, required facts, constraints, raw response, grader prompt, rubric, and error taxonomy.
- [ ] Add negative tests asserting the blind packet contains none of these keys or values: Prompt Version identity, v1/v2 label, Dev/Holdout split, generator product/model, run purpose, calculated_status, prior Grader result, Human Review, or experiment conclusion. Candidate ID must remain anonymous and must not encode version/split.
- [ ] Add blind Human Review packet tests proving the packet contains only anonymous candidate_id, source_material, Case-visible task instructions/constraints, the exact raw model response, fixed Human Review rubric, and decision options. Assert that Prompt Version, split, generator metadata, Grader result/reason/evidence, calculated_status, primary_error_type, previous Human Review, and analysis/conclusions are absent.
- [ ] Implement generation rendering as a copy-ready text packet with explicit labeled sections: fixed user task/output contract, Case-visible task instructions/constraints, source material, and the actual Prompt Version `prompt_text`. Read but ignore internal Case annotations and Prompt Version labels/hashes when selecting the model-facing allowlist. Do not call any model API.
- [ ] Implement blind rendering from an allowlist only. Do not pass a Run row or full database context into the renderer; the function signature makes forbidden metadata unavailable. Include grader asset snapshots and hashes, preserve the raw model response exactly, and omit their hidden experiment meaning.
- [ ] Implement `render_blind_human_review_packet` from a separate allowlist and fixed rubric/decision options. `build_blind_human_review_packet` may fetch database rows, but must pass only the allowlisted values into the Domain renderer; do not persist or display automatic results in the pre-submit packet.
- [ ] Keep any blind-review packet version/hash as application provenance only; do not show it, the evaluation-result identifier, or any other internal metadata in the reviewer-facing context.
- [ ] Persist generation_packet_version and generation_packet_hash on model_outputs when the output slot is created. Persist blind_packet_version and blind_packet_hash on grader_results when a packet is built/imported. Do not store mutable packet text as a second source of truth.
- [ ] Run:

```powershell
python -m pytest tests/domain/test_packets.py tests/application/test_packets.py -q
```

- [ ] Commit:

```powershell
git add src/eval_lab/domain/packets.py src/eval_lab/application/packets.py db/schema.sql src/eval_lab/repositories/sqlite.py tests/domain/test_packets.py tests/application/test_packets.py
git commit -m "feat: add canonical generation and blind packets"
```

**Completion standard:** Human copy/paste input is deterministic and hashable for generation, Grader, and pre-submit Human Review use, with automated metadata-leakage tests and no API call.



## Task 6: Add simple Repository CRUD and query functions

**Files**

- Modify src/eval_lab/repositories/sqlite.py.
- Create tests/repositories/test_crud.py.

**Interfaces**

```python
def insert_task_pack(conn, data: Mapping[str, object]) -> int: ...
def insert_test_case(conn, data: Mapping[str, object]) -> int: ...
def list_test_cases(conn, task_pack_id: int, split: str | None = None) -> list[sqlite3.Row]: ...
def insert_prompt_version(conn, data: Mapping[str, object]) -> int: ...
def freeze_prompt_version(conn, prompt_version_id: int, frozen_at: str) -> None: ...
def insert_evaluation_run(conn, data: Mapping[str, object]) -> int: ...
def get_evaluation_run(conn, run_id: int) -> sqlite3.Row: ...
def update_run_status(conn, run_id: int, status: str) -> None: ...
def insert_model_output_slot(conn, data: Mapping[str, object]) -> int: ...
def update_technical_retry(conn, model_output_id: int, reason: str) -> None: ...
def insert_rule_results(conn, model_output_id: int, results: Sequence[Mapping[str, object]]) -> None: ...
def insert_grader_condition(conn, data: Mapping[str, object]) -> int: ...
def insert_grader_result(conn, data: Mapping[str, object]) -> int: ...
def insert_grader_fact_results(conn, grader_result_id: int, results: Sequence[Mapping[str, object]]) -> None: ...
def insert_evaluation_result(conn, data: Mapping[str, object]) -> int: ...
def insert_human_review(conn, data: Mapping[str, object]) -> int: ...
def fetch_output_context(conn, model_output_id: int) -> dict[str, object]: ...
def fetch_raw_response(conn, model_output_id: int) -> str | None: ...
def fetch_retry_count(conn, model_output_id: int) -> int: ...
```

- [ ] Write tests for parent/child inserts, output context joins, duplicate output slot, duplicate Grader condition, duplicate evaluation result, and duplicate Human Review.
- [ ] Run before implementation:

```powershell
python -m pytest tests/repositories/test_crud.py -q
```

- [ ] Implement parameterized SQL functions with ? parameters. Serialize JSON with ensure_ascii=False and sort_keys=True. Do not create a Repository class or interface hierarchy.
- [ ] Require model-output inserts to persist the generation packet version/hash and Grader-result inserts to persist the blind packet version/hash; tests must fetch both hashes from stored rows and reject missing packet provenance.
- [ ] Add a rollback test proving a failed multi-row insert leaves earlier rows absent.
- [ ] Run and commit:

```powershell
python -m pytest tests/repositories -q
git add src/eval_lab/repositories/sqlite.py tests/repositories/test_crud.py
git commit -m "feat: add sqlite repositories"
```

**Completion standard:** All approved entities persist/retrieve through simple functions, with SQL enforcing relationships and uniqueness.

## Task 7: Implement Imports validation boundaries

**Files**

- Create src/eval_lab/imports/test_cases.py, model_outputs.py, grader_results.py, human_reviews.py.
- Create tests/imports/test_case_imports.py, test_model_output_imports.py, test_grader_imports.py, and test_review_imports.py.

**Interfaces**

```python
def parse_json_text(raw_text: str) -> object: ...
def parse_task_pack_payload(payload: Mapping[str, object]) -> ValidationResult: ...
def parse_test_case_payload(payload: Mapping[str, object]) -> ValidationResult: ...
def parse_model_output_payload(payload: Mapping[str, object]) -> ValidationResult: ...
def parse_grader_payload(payload: Mapping[str, object], required_fact_ids: Sequence[str]) -> ValidationResult: ...
def parse_human_review_payload(payload: Mapping[str, object]) -> ValidationResult: ...
```

ValidationResult is a TypedDict with ok: bool, value: dict or None, errors: list[str], and raw_text: str or None.

- [ ] Test malformed JSON, fences, missing fields, wrong types, invalid split/status, invalid raw output type, invalid Grader labels, forbidden blind metadata, and missing Human Review decision/reason. Invalid JSON must retain exact raw text.
- [ ] Run before implementation:

```powershell
python -m pytest tests/imports -q
```

- [ ] Implement strict parsing and basic validation. Imports may normalize object ordering for hashes but may not alter model response, remove fences, add defaults, coerce types, or repair syntax. Imports never call Repository functions.
- [ ] Run and commit:

```powershell
python -m pytest tests/imports -q
git add src/eval_lab/imports tests/imports
git commit -m "feat: add strict import validation"
```

**Completion standard:** Invalid external data is visible with explicit errors and cannot silently become evaluation evidence.

## Task 8: Build Application lifecycle, output capture, and Rules vertical slice

**Files**

- Create src/eval_lab/application/prompts.py, runs.py, outputs.py.
- Create tests/fixtures/demo_case.json.
- Create tests/application/test_prompt_lifecycle.py and test_output_workflow.py.

**Interfaces**

```python
def create_prompt_version(conn, prompt_text: str, version_label: str, change_reason: str) -> int: ...
def freeze_prompt_version(conn, prompt_version_id: int, frozen_at: str) -> None: ...
def create_evaluation_run(conn, prompt_version_id: int, comparison_group_id: str, split: str, metadata: Mapping[str, object]) -> int: ...
def assert_runs_comparable(run_a: Mapping[str, object], run_b: Mapping[str, object]) -> None: ...
def close_run(conn, run_id: int) -> None: ...
def record_model_output(conn, run_id: int, test_case_id: int, generation_packet_version: str, generation_packet_hash: str, raw_response: str | None, generated_at: str | None, technical_retry_reason: str | None = None) -> int: ...
def evaluate_output_rules(conn, model_output_id: int, contract: Mapping[str, object], forbidden_claims: Sequence[str]) -> list[dict[str, object]]: ...
class WorkflowError(ValueError): ...
```

- [ ] Test draft → frozen Prompt, Holdout creation blocked before v2 freeze, run metadata, comparable/incomparable groups, and closed-run write rejection.
- [ ] Test first actual response and technical retries:

```python
def test_quality_failure_is_not_retryable(conn, run_id, case_id):
    output_id = record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", "not json", "2026-08-13T09:00:00Z")
    with pytest.raises(WorkflowError):
        record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", '{"title":"retry"}', "2026-08-13T09:01:00Z")
    assert fetch_raw_response(conn, output_id) == "not json"

def test_technical_retry_is_recorded(conn, run_id, case_id):
    output_id = record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", None, None, "page load failure")
    record_model_output(conn, run_id, case_id, "packet-v1", "packet-hash", None, None, "network error")
    assert fetch_retry_count(conn, output_id) == 2
```

- [ ] Run before implementation:

```powershell
python -m pytest tests/application/test_prompt_lifecycle.py tests/application/test_output_workflow.py -q
```

- [ ] Implement exact raw capture, one output slot per Run/Case, required generation packet version/hash, retry metadata only for a null response plus technical reason, and rejection of a second real response. evaluate_output_rules calls Domain Rules and writes Rule rows in one transaction.
- [ ] Run, compile, and commit:

```powershell
python -m pytest tests/application/test_prompt_lifecycle.py tests/application/test_output_workflow.py -q
python -m compileall -q app.py src
git add src/eval_lab/application/prompts.py src/eval_lab/application/runs.py src/eval_lab/application/outputs.py tests/fixtures/demo_case.json tests/application/test_prompt_lifecycle.py tests/application/test_output_workflow.py
git commit -m "feat: capture evaluation runs and model outputs"
```

**Completion standard:** A demo Case attaches to a Run, first actual response is immutable evidence, technical retries are separate, Rules persist, and lifecycle gates prevent invalid operations.

## Task 9: Complete Grader, automatic status, and Human Review workflow

**Files**

- Create src/eval_lab/application/cases.py, grading.py, reviews.py.
- Create tests/fixtures/demo_grader_valid.json and demo_grader_indeterminate.json.
- Create tests/application/test_grading_workflow.py and test_review_workflow.py.

**Interfaces**

```python
def load_case(conn, case_id: int) -> dict[str, object]: ...
def build_blind_grader_packet_for_output(conn, model_output_id: int, grader_condition_id: int) -> dict[str, object]: ...
def build_blind_human_review_packet_for_result(conn, evaluation_result_id: int) -> dict[str, object]: ...
def import_grader_result(conn, model_output_id: int, grader_condition: Mapping[str, object], raw_payload: Mapping[str, object]) -> int: ...
def calculate_output_status(conn, model_output_id: int, grader_result_id: int | None, grader_condition_id: int, aggregation_rule_version: str = "1.0") -> int: ...
def select_predeclared_review_sample(conn, comparison_group_id: str, fraction: float = 0.20) -> list[int]: ...
def required_review_targets(conn, comparison_group_id: str) -> list[int]: ...
def record_human_review(conn, evaluation_result_id: int, review_scope: str, blind_review: bool, evidence: Mapping[str, object], reason: str, final_decision: str) -> int: ...
```

- [ ] Test actual Grader snapshots/hashes, valid payload persistence, one fact row per required fact, invalid payload rejection, duplicate output/condition rejection, and status calculation using Rule + Grader only.
- [ ] Test that the application builds the canonical blind packet from allowlisted context before import, shows its exact version/hash to the operator, persists that provenance, and never forwards forbidden run/version/split/analysis metadata.
- [ ] Test that paired v1/v2 runs use the same grader_condition_id for the primary comparison and that a changed condition is reported as a separate condition rather than merged.
- [ ] Test pointwise isolation by rendering each candidate in a fresh Grader context with an anonymous candidate_id; no packet builder or import path may read another candidate's response, Grader result, review, status, or experiment conclusion.
- [ ] Test blind Human Review context isolation: before submission, the Application packet contains only the allowlisted candidate/source/instructions/raw-response/rubric fields, and seeded Grader results, calculated status, previous reviews, split, generator metadata, and analysis conclusions are not present in packet text or payload.
- [ ] Build the blind packet through `application/packets.py` before import, show it for the external Grader run, then pass only the returned raw Grader JSON to Imports. Keep the blind packet version/hash and the original Grader asset snapshots in the stored Grader result; do not merge conditions or mutate the candidate's raw model output.
- [ ] Keep Human Review separate from Grader import and status aggregation. The pre-submit review service returns only the blind Human Review packet; after `record_human_review` succeeds, the UI may load and display calculated_status beside the saved final_decision.
- [ ] Test Human Review separation:

```python
def test_human_review_does_not_change_calculated_status(conn, evaluation_result_id):
    before = fetch_calculated_status(conn, evaluation_result_id)
    record_human_review(
        conn, evaluation_result_id, "indeterminate_queue", True,
        {"output_evidence": "..."}, "Manual evidence resolves ambiguity", "pass"
    )
    assert fetch_calculated_status(conn, evaluation_result_id) == before
    assert fetch_final_decision(conn, evaluation_result_id) == "pass"
```

- [ ] Test deterministic sampling. In each prompt-version/split stratum, rank candidate IDs by SHA-256 and select ceil(0.20 × count). Repeated calls are stable and independent of Grader outcomes. Do not add a sampling table.
- [ ] Define `required_review_targets` before result inspection as every calculated indeterminate result plus every detected unsupported-claim result, then add the predeclared approximately-20% SHA-256 sample from the remaining results with prompt-version/split balance. Human review never changes the calculated status.
- [ ] Run before implementation:

```powershell
python -m pytest tests/application/test_grading_workflow.py tests/application/test_review_workflow.py -q
```

- [ ] Implement Imports → Application association → Domain normalization → Repository persistence. calculate_output_status calls only aggregate_calculated_status and writes evaluation_results. record_human_review writes only human_reviews.
- [ ] Run non-UI tests and commit:

```powershell
python -m pytest tests/domain tests/repositories tests/imports tests/application -q
git add src/eval_lab/application/cases.py src/eval_lab/application/grading.py src/eval_lab/application/reviews.py tests/fixtures/demo_grader_valid.json tests/fixtures/demo_grader_indeterminate.json tests/application/test_grading_workflow.py tests/application/test_review_workflow.py
git commit -m "feat: add grading and human review workflow"
```

**Completion standard:** The demo workflow stores blinded Grader evidence, computes automatic status, selects the declared queue, and stores an independent final decision.

## Task 10: Add read-only SQL/Pandas Analysis

**Files**

- Create src/eval_lab/analysis/queries.sql and reports.py.
- Create tests/analysis/test_reports.py.

**Interfaces**

```python
def load_query(query_name: str) -> str: ...
def run_query(conn, query_name: str, params: Sequence[object] = ()) -> pandas.DataFrame: ...
def run_summary(conn, run_id: int) -> pandas.DataFrame: ...
def paired_comparison(conn, comparison_group_id: str) -> pandas.DataFrame: ...
def status_distribution(conn, run_id: int) -> pandas.DataFrame: ...
def failure_breakdown(conn, run_id: int) -> dict[str, pandas.DataFrame]: ...
def review_coverage(conn, comparison_group_id: str) -> pandas.DataFrame: ...
```

- [ ] Test total assigned, responses received, technical failure/not-evaluated, determinate, pass rate among determinate, indeterminate count/rate, calculated-status distribution, final-decision distribution, review coverage, Rule failures, required-fact failures, unsupported claims, and primary error types.
- [ ] Add named SQL sections: run_summary, status_distribution, paired_comparison, rule_failures, required_fact_failures, unsupported_claims, error_types, bad_cases, review_coverage. Paired query requires matching comparison group, split, Case set hash, contract hash, generator product/model, and protocol version; mismatch is incomparable.
- [ ] Implement read-only reports with Pandas formatting only. Never write or call Domain aggregation. Always show calculated status, final decision, and indeterminate rate separately.
- [ ] Run and prove no writes:

```powershell
python -m pytest tests/analysis/test_reports.py -q
```

Tests compare row counts and hashes before/after report calls.

- [ ] Commit:

```powershell
git add src/eval_lab/analysis tests/analysis/test_reports.py
git commit -m "feat: add descriptive analysis queries"
```

**Completion standard:** Demo data produces transparent, read-only reports with explicit denominators and separated outcomes.

## Task 11: Build minimal Streamlit shell and metadata pages

**Files**

- Modify app.py.
- Create src/eval_lab/ui/components.py.
- Create pages overview.py, task_pack.py, test_cases.py, prompt_versions.py.
- Create tests/ui/test_shell.py and test_metadata_pages.py.

**Interfaces**

- Each page exposes render(conn: sqlite3.Connection) -> None.
- components.py exposes small helpers such as show_validation_errors(errors) and status_badge(status).
- app.py creates one connection, initializes schema if needed, and routes to the seven approved pages with the official multipage mechanism.

- [ ] Write AppTest startup/navigation tests:

```python
from streamlit.testing.v1 import AppTest

def test_app_starts():
    at = AppTest.from_file("app.py").run()
    assert not at.exception
    assert "AI Output Eval Lab" in at.title[0].value
```

Also assert invalid form input is visible and not saved.
- [ ] Implement shell and helpers. Use one local DB path setting with a local default; initialize through Repository, never raw SQL in UI.
- [ ] Implement Overview counts, fixed Task Pack contract/QA display, Test Case split filters, and Prompt create/view/freeze with change reason. Frozen text is immutable.
- [ ] Run:

```powershell
python -m pytest tests/ui/test_shell.py tests/ui/test_metadata_pages.py -q
```

- [ ] Commit:

```powershell
git add app.py src/eval_lab/ui tests/ui/test_shell.py tests/ui/test_metadata_pages.py
git commit -m "feat: add metadata streamlit pages"
```

**Completion standard:** App starts and metadata pages work without evaluation logic inside UI modules.

## Task 12: Build evaluation, review, and analysis pages

**Files**

- Create pages model_outputs.py, evaluation.py, and analysis.py.
- Modify pages/overview.py.
- Create tests/ui/test_evaluation_pages.py.

**Interfaces**

- model_outputs.render(conn) collects Run/Case, calls the Application generation-packet service, displays the exact model-facing copy-ready packet text and shows packet provenance version/hash outside that copy block, then collects raw response, timestamp, and technical-retry reason without modifying raw text.
- evaluation.render(conn) calls the Application blind-packet service for Grader import and the blind Human Review packet service for review mode. In pre-submit blind review mode it displays only the allowlisted review packet and decision form; after submission it may display Rule/Grader evidence, calculated_status, and final_decision together.
- analysis.render(conn) calls only Analysis reports and labels calculated status, final decision, review coverage, determinate denominator, and indeterminate rate.

- [ ] Test invalid JSON is captured as-is with Rule failure and no quality-retry control.
- [ ] Test technical retry is separate.
- [ ] Test automatic indeterminate plus human pass displays both values without mutation.
- [ ] Test the copy-ready generation packet view shows only the model-facing rendered text in the copy block, shows provenance version/hash separately, and recording a response stores the displayed packet version/hash without changing the raw response.
- [ ] Test the copy-ready blind Grader packet view shows the exact rendered text and hash while excluding Prompt Version, split, generator metadata, calculated status, prior results, Human Review, and conclusions; no UI path calls an API.
- [ ] Add AppTest coverage for blind Human Review mode: before submitting, assert the UI shows candidate/source/instructions/raw response/rubric/options but not Grader result/reason/evidence, calculated_status, primary_error_type, Prompt Version, split, generator metadata, previous review, or conclusions; after submitting a decision, assert the automatic result and final_decision are both visible and unchanged.
- [ ] Implement the packet views with `st.code(packet["text"], language="text")` for model-facing and pre-submit blind-review content, separate labels for packet version/hash, and an explicit review-mode branch. Pass the displayed generation packet version/hash to output recording, build the blind Grader packet immediately before Grader import, and load automatic results only after Human Review submission.
- [ ] Implement readable tables, filters, status labels, and evidence expanders only; no visual system or complex frontend.
- [ ] Run and launch:

```powershell
python -m pytest tests/ui -q
python -m streamlit run app.py --server.headless true
```

Navigate all pages with demo data, then stop the process.
- [ ] Commit:

```powershell
git add src/eval_lab/ui/pages tests/ui/test_evaluation_pages.py
git commit -m "feat: add evaluation and analysis pages"
```

**Completion standard:** The complete non-formal demo workflow is usable through Streamlit.

## Task 13: Add seed/import structure and Dataset QA without claiming the formal dataset

**Files**

- Create db/seed_data/task_pack.json and test_cases.json.
- Modify imports/test_cases.py and application/cases.py.
- Create tests/application/test_dataset_qa.py.
- Create docs/methodology.md.

**Interfaces**

```python
def load_task_pack_seed(path: str | Path) -> ValidationResult: ...
def load_test_case_seed(path: str | Path) -> ValidationResult: ...
def qa_case_set(cases: Sequence[Mapping[str, object]], task_pack: Mapping[str, object]) -> dict[str, object]: ...
def compute_case_set_hash(cases: Sequence[Mapping[str, object]]) -> str: ...
```

- [ ] Put only the fixed contract in task_pack.json. Do not add per-Case length overrides or a DSL.
- [ ] Make test_cases.json empty or a clearly non-final demo collection. The loader accepts Case key/revision, split, source material, source facts, required IDs, explicit forbidden claims, notes, feasibility status, and hash.
- [ ] Test required subset, duplicate IDs, traceability metadata, exact 18/6 validation for a formal set, contract hash, and rejection of unreviewed/infeasible cases. Do not generate gold answers or pretend to solve semantic feasibility automatically.
- [ ] Implement qa_case_set. It returns counts, errors, case-set hash, and formal_ready only when every case has feasibility status pass, exact 18/6 split, valid annotations, and one shared contract hash. It does not write SQLite.
- [ ] Document source precedence, traceability, hard required facts, feasibility review, split discipline, hashes, and descriptive limits.
- [ ] Run and commit:

```powershell
python -m pytest tests/application/test_dataset_qa.py tests/imports/test_case_imports.py -q
git add db/seed_data src/eval_lab/imports/test_cases.py src/eval_lab/application/cases.py tests/application/test_dataset_qa.py docs/methodology.md
git commit -m "feat: add dataset seed and feasibility QA"
```

**Completion standard:** Seed/import structure and QA are truthful; an incomplete collection is not called the official dataset.

## Task 14: Author and approve the formal 24-case data after engineering works

**Files**

- Modify db/seed_data/test_cases.json.
- Modify docs/methodology.md only for the approved case-set record.
- Test tests/application/test_dataset_qa.py.

This is a content approval gate. Do not fabricate a benchmark or mark cases formal without owner review.

- [ ] Draft 24 fictional self-contained cases: 18 dev and 6 holdout, same task/contract, Simplified Chinese source, traceable facts, required subset, literal forbidden claims where needed, notes, and feasibility status.
- [ ] Run QA:

```powershell
python -c "from pathlib import Path; from eval_lab.imports.test_cases import load_task_pack_seed, load_test_case_seed; from eval_lab.application.cases import qa_case_set; p=load_task_pack_seed(Path('db/seed_data/task_pack.json')); c=load_test_case_seed(Path('db/seed_data/test_cases.json')); r=qa_case_set(c['value'], p['value']); print(r); raise SystemExit(0 if r['formal_ready'] else 1)"
```

Expected: total 24, dev 18, holdout 6, no annotation errors, all feasibility statuses pass, and a case-set hash.
- [ ] Manually verify every fact is source-supported, every required fact fits fixed lengths, no hard constraints conflict, and no Case needs a length exception. Record review date/hash after approval.
- [ ] Load only approved Cases into a fresh DB. Do not add model outputs, Grader results, or Human Reviews here.
- [ ] Run and commit after approval:

```powershell
python -m pytest tests/application/test_dataset_qa.py -q
git add db/seed_data/test_cases.json docs/methodology.md
git commit -m "data: add approved grounded brief cases"
```

**Completion standard:** Official seed has exactly 24 owner-reviewed feasibility-passing cases and a reproducible hash. Without approval, keep it non-final and report the data gate as pending.

## Task 15: Create and owner-approve formal Experiment Assets

**Files**

- Create db/seed_data/experiment_assets_v1.json.
- Create tests/application/test_experiment_asset_gate.py.
- Modify src/eval_lab/imports/test_cases.py and src/eval_lab/application/cases.py.
- Modify src/eval_lab/application/prompts.py and grading.py.
- Modify tests/application/test_prompt_lifecycle.py and test_grading_workflow.py.
- Modify docs/methodology.md.

**Interfaces**

```python
def load_experiment_assets(path: str | Path) -> ValidationResult: ...
def validate_experiment_assets(payload: Mapping[str, object]) -> list[str]: ...
def register_approved_experiment_assets(conn, payload: Mapping[str, object]) -> dict[str, int]: ...
def approve_prompt_version(conn, prompt_version_id: int, approved_at: str) -> None: ...
def approve_grader_condition(conn, grader_condition_id: int, approved_at: str) -> None: ...
def create_prompt_v2_after_dev(conn, dev_run_id: int, prompt_text: str, change_reason: str) -> int: ...
```

- [ ] Write asset-gate tests rejecting missing assets, missing version labels, hash mismatch, unapproved status, and a v2 asset appearing in the v1 approval manifest.
- [ ] Write tests that approved v1 assets register one frozen Prompt Version and one Grader Condition containing the actual Grader prompt, rubric, and error taxonomy snapshots plus content hashes. Test that registration cannot silently mark an unapproved asset as formal.
- [ ] Write lifecycle tests that create_prompt_v2_after_dev rejects a Dev run that is not closed, has no evaluation_results, or has an empty change_reason. It must create a draft v2 only after a completed Dev v1 result set exists.
- [ ] Define experiment_assets_v1.json as four distinct snapshots: prompt_v1, grader_prompt_v1, rubric_v1, and error_taxonomy_v1. Each entry contains asset_type, version_label, content, content_hash, draft/approved status, and owner_approved_at. Codex may draft content, but the file remains non-formal until the owner reviews it.
- [ ] Implement validation by recomputing each content hash from canonical content and requiring all four assets to be present, versioned v1, and owner-approved before registration. Register prompt_v1 through prompt_versions and the three Grader assets through grader_conditions; do not add a database table.
- [ ] Require approval before freezing Prompt v1 or Prompt v2 and before using a Grader Condition in the formal experiment. Keep the owner_approved_at columns specified in Task 2.
- [ ] Document the approval gate and the distinction between Codex-assisted drafting and owner-approved formal assets in docs/methodology.md.
- [ ] Run:

```powershell
python -m pytest tests/application/test_experiment_asset_gate.py tests/application/test_prompt_lifecycle.py tests/application/test_grading_workflow.py -q
```

- [ ] Commit:

```powershell
git add db/seed_data/experiment_assets_v1.json src/eval_lab/imports/test_cases.py src/eval_lab/application/cases.py src/eval_lab/application/prompts.py src/eval_lab/application/grading.py tests/application db/schema.sql docs/methodology.md
git commit -m "feat: gate formal experiment assets"
```

**Completion standard:** Prompt v1, Grader Prompt v1, Rubric v1, and Error Taxonomy v1 exist as reproducible snapshots with hashes and explicit owner approval; no Prompt v2 is created by this task.

## Task 16: Execute the owner-supervised formal experiment and write findings

**Files**

- Create docs/findings.md.
- Create db/seed_data/experiment_assets_final.json after Prompt v2 approval/freeze.
- Create tests/application/test_formal_experiment_gate.py.
- Modify src/eval_lab/application/runs.py, outputs.py, grading.py, and reviews.py only where formal lifecycle guards are missing.
- Modify src/eval_lab/analysis/queries.sql and reports.py for final paired report fields.
- Modify tests/analysis/test_reports.py and Application workflow tests.

**Interfaces**

```python
def assert_formal_run_ready(conn, run_id: int) -> None: ...
def assert_holdout_not_started_before_v2_freeze(conn, comparison_group_id: str) -> None: ...
def formal_run_summary(conn, comparison_group_id: str) -> dict[str, object]: ...
def write_findings_inputs(conn, comparison_group_id: str) -> dict[str, object]: ...
def write_final_experiment_asset_snapshot(conn, prompt_v1_id: int, prompt_v2_id: int, grader_condition_id: int, path: str | Path) -> None: ...
```

The formal execution is owner-supervised manual work. Application supplies canonical packets and records raw responses; it never calls a model or Grader API.

- [ ] Write gate tests requiring approved v1 assets, exactly 18 Dev cases for a Dev baseline, and matching generator/protocol/contract/Case-set hashes. Test that any Holdout run creation or result display before Prompt v2 is owner-approved and frozen is rejected.
- [ ] Write tests that every formal output has a generation packet version/hash, every imported Grader result has a blind packet version/hash and approved Grader condition, and technical failures remain outside quality denominators.
- [ ] Write snapshot tests requiring `experiment_assets_final.json` to contain Prompt v1, Prompt v2, Grader Prompt, Rubric, and Error Taxonomy entries with version labels, recomputable content hashes, owner approval timestamps, and Prompt freeze timestamps where applicable. Reject a final snapshot that is missing v2 approval/freeze or whose content hash does not match.
- [ ] Run gate tests before manual execution:

```powershell
python -m pytest tests/application/test_formal_experiment_gate.py tests/application/test_prompt_lifecycle.py tests/application/test_grading_workflow.py -q
```

- [ ] Execute phase A, Dev baseline, through the UI with approved assets: create a v1/dev run for all 18 Dev cases; render and copy one canonical generation packet per Case; collect the first actual response from the same generator condition; record technical retries only for technical failures; run Rule Checks; render one isolated blind Grader packet per candidate; import Grader results; calculate status; apply the declared Human Review queue; and run Dev SQL/Bad Case analysis.
- [ ] Record the Dev baseline run ID, comparison_group_id, generator product/model or not_visible, Grader condition ID, packet hashes, timestamps, response coverage, and any technical failures in docs/methodology.md. Do not hand-pick a better response.
- [ ] Execute phase B, Prompt iteration, only after Dev v1 results and Bad Cases are available: use Dev failure modes to draft Prompt v2; record a change_reason that names observed failure modes and evidence; if needed, run a Dev-only v2 paired comparison under the same Case/generator/Grader conditions while the version is still a draft; then obtain owner approval and freeze Prompt v2 with content hash and frozen_at. No v2 Holdout run or formal v2 use may occur before this point.
- [ ] Immediately after Prompt v2 approval/freeze, export `db/seed_data/experiment_assets_final.json` as a readable file-level snapshot. Include the actual Prompt v1/v2 text, Grader Prompt, Rubric, Error Taxonomy, version labels, content hashes, owner approval timestamps, and freeze timestamps; do not add a table or depend on a local SQLite database for public inspection.
- [ ] Execute phase C, Holdout, only after the v2 freeze: create separate v1/holdout and v2/holdout runs with one shared comparison_group_id, six cases each, matching generator and Grader conditions; first view/use Holdout packets and responses only after freeze; run Rules, blind Grader import, calculated status, declared Human Review, and paired descriptive analysis.
- [ ] Define paired categories by `test_case_id`: improved means v1 is `fail` and v2 is `pass`; regressed means v1 is `pass` and v2 is `fail`; unchanged means both determinate statuses are equal; indeterminate means either side is `indeterminate` or lacks a quality response because of a technical failure. Report technical failures separately and exclude them from quality pass-rate denominators; never convert them into a quality `fail`. Report raw counts and denominators for each category separately for Dev and Holdout.
- [ ] Execute phase D, Findings: create docs/findings.md with separate Dev and Holdout sections, raw counts, explicit denominators, response/technical-failure counts, determinate/pass-rate/indeterminate counts, improved/regressed/unchanged/indeterminate paired changes, major failure modes, required-fact failures, Rule failures, representative Bad Cases, Human Review coverage, and limitations. State that results are descriptive and personal; do not claim significance, benchmark validity, or general model capability.
- [ ] Run final report tests and inspect findings:

```powershell
python -m pytest tests/application/test_formal_experiment_gate.py tests/analysis/test_reports.py -q
python -c "from pathlib import Path; assert Path('docs/findings.md').exists(); print(Path('docs/findings.md').stat().st_size)"
```

- [ ] Commit owner-reviewed experiment evidence and findings:

```powershell
git add db/seed_data/experiment_assets_final.json docs/findings.md docs/methodology.md src/eval_lab/application src/eval_lab/analysis tests/application tests/analysis
git commit -m "docs: record formal evaluation findings"
```

**Completion standard:** The repository contains owner-supervised Dev baseline, Prompt v2 rationale/freeze, a readable final experiment-assets snapshot, post-freeze Holdout comparison, and findings with honest denominators and limitations. No API call or unsupported statistical claim is introduced.


## Task 17: Complete README, limitations, Bad Cases, and screenshots after findings

**Files**

- Create or modify README.md.
- Create docs/limitations.md.
- Modify docs/methodology.md.
- Create docs/screenshots/overview.png, evaluation.png, analysis.png, bad-case.png.

- [ ] Document install, DB initialization, Streamlit launch, page map, import path, architecture, and calculated-status versus final-decision distinction.
- [ ] Document closed-world rule, strict parsing, fixed lengths, 18/6 order, same generator condition, blind pointwise Grader, 20% sampling, descriptive analysis, technical retry rule, constructed-data boundary, no production traffic/API automation/benchmark/statistical validation, and honest Codex assistance.
- [ ] Link and describe `db/seed_data/experiment_assets_final.json` in README.md and docs/methodology.md so a public repository reader can inspect the owner-approved Prompt v1/v2 and Grader assets without opening SQLite. Do not substitute the draft `experiment_assets_v1.json` for the final snapshot.
- [ ] Build the Bad Case section from the owner-reviewed formal experiment findings, with at least one schema failure, required-fact failure, unsupported claim, and indeterminate case when present; include raw output, evidence, calculated status, and final decision where present. Never edit raw output or substitute demo fixtures for formal evidence.
- [ ] Run the app after docs/findings.md is complete and capture Overview, Evaluation, Analysis, and Bad Case screenshots with those exact filenames. The screenshots must show formal experiment findings, not only demo fixtures, and must exclude secrets/private account data.
- [ ] Run:

```powershell
rg -n "README|methodology|limitations|screenshots|calculated_status|final_decision|indeterminate" README.md docs
git diff --check
git add README.md docs
git commit -m "docs: explain eval methodology and limitations"
```

**Completion standard:** A new reader can run the app, understand protocol/limits, inspect Bad Cases, and see screenshots without mistaking the project for a production benchmark.

## Task 18: Final verification and MVP handoff

**Files**

- Modify only files revealed by verification failures; do not add product scope.
- Test all existing tests and the approved seed.

- [ ] Run all tests:

```powershell
python -m pytest -q
```

- [ ] Run compile/schema checks:

```powershell
python -m compileall -q app.py src
python -c "from pathlib import Path; from eval_lab.repositories.sqlite import connect, initialize_database, table_names; db=Path('tmp_verify.sqlite'); conn=connect(db); initialize_database(conn, Path('db/schema.sql')); print(sorted(table_names(conn))); assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1; conn.close(); db.unlink()"
git diff --check
```

Expected: compilation succeeds, eleven tables print, foreign_keys is 1, temp DB is removed, and no whitespace errors occur.
- [ ] Run Task 14 dataset QA, Task 15 asset-approval tests, and Task 16 formal-experiment/report/snapshot tests; record exact case-set and asset hashes/counts. Verify `db/seed_data/experiment_assets_final.json` exists and its hashes/timestamps validate. If owner approval or formal experiment evidence is absent, report the corresponding gate as pending.
- [ ] Execute a clean manual demo on a fresh DB: Prompt v1 Dev run → raw output → Rules → Grader → calculated status → Human Review → Prompt v2 freeze → Holdout run creation → Analysis. Do not view Holdout results before v2 freeze.
- [ ] Inspect:

```powershell
git status --short --branch
git log --oneline -5
```

The handoff lists tests, schema/foreign-key evidence, dataset hash/split counts, screenshots, limitations, and uncommitted files. Never claim benchmark, statistical validation, production traffic, API automation, or independent authorship of all code.
- [ ] Commit final verification fixes only:

```powershell
git add app.py pyproject.toml .gitignore src db tests README.md docs
git commit -m "chore: verify AI Output Eval Lab MVP"
```

**Completion standard:** Approved acceptance criteria are evidenced, final working tree is clean, and engineering readiness is separated from owner-reviewed experiment data.

## Plan self-review checklist

- [ ] Exactly eleven approved tables; no evaluation_run_prompts or grader_claim_results.
- [ ] Schema initialization uses an explicit rollback-safe statement loop, rejects broken schemas, and never leaves a half-initialized fresh database.
- [ ] Prompt Version is derived through model_outputs.run_id → evaluation_runs.prompt_version_id.
- [ ] calculated_status has no Human Review input or human-generated snapshot.
- [ ] final_decision is nullable until review and stored only in human_reviews.
- [ ] Strict parsing, field applicability, fixed lengths, closed-world evidence, language hard criterion, technical retries, and first-response behavior are tested.
- [ ] Dev/Holdout freeze order and comparison comparability are implemented without blind-test/significance claims.
- [ ] Grader snapshots, hashes, labels, product/model condition, candidate blindness, and independent contexts are represented.
- [ ] Canonical generation text is restricted to the model-facing allowlist and excludes internal facts/IDs, split, labels, hashes, run metadata, and evaluation annotations; provenance remains outside copied text.
- [ ] Canonical blind Grader and blind Human Review packets are deterministic, isolated, allowlisted, hashable where applicable, and covered by negative leakage tests; Human Review hides automatic results until submission.
- [ ] 20% sample is deterministic, stratified, and independent of observed outcomes.
- [ ] Analysis is read-only, descriptive, denominator-explicit, and separates automatic versus human outcomes.
- [ ] Formal 24-case content is a later owner-review gate, not an invented fixture silently treated as complete.
- [ ] Formal Experiment Assets approval precedes formal runs; Prompt v2 is created only from Dev v1 evidence, records change_reason, and is frozen with content hash/frozen_at before Holdout.
- [ ] Final experiment assets are exported after Prompt v2 approval/freeze to `db/seed_data/experiment_assets_final.json`, with readable content, labels, hashes, approval/freeze timestamps, and README/methodology references.
- [ ] Formal experiment execution has separate Dev baseline, Prompt iteration, post-freeze Holdout, and findings tasks; docs/screenshots consume formal findings rather than demo-only fixtures.
- [ ] No task introduces API, ORM, RAG, Agent, DSL, plugin, complex frontend, or unnecessary abstraction.
