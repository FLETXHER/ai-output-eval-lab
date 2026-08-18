# AI Output Eval Lab

AI Output Eval Lab is a small, local, auditable Prompt-evaluation workbench
for **Grounded Structured Brief Generation**. It demonstrates a complete loop:
fixed Cases → Prompt v1 → Dev failure analysis → evidence-driven Prompt v2 →
frozen Holdout comparison → deterministic checks and blind Grader → Human
Review provenance → paired analysis.

This is a personal evaluation project, not a production A/B test, industry
benchmark, statistical validation, or automated model-API platform.

## Why this project

A single output that “feels better” is not enough to justify a Prompt change.
The project keeps the task contract, Case Set, Prompt snapshots, evaluation
layers, run metadata, and correction trail explicit so that a change can be
explained and audited.

## What it evaluates

The fixed Task Pack asks a model to generate a Simplified-Chinese structured
brief from closed-world source material. The output must be one strict JSON
object containing exactly:

```json
{
  "title": "string",
  "summary": "string",
  "key_points": ["string", "string", "string"]
}
```

The formal contract uses `len(text.strip())`:

- `title`: 4–20 characters;
- `summary`: 60–120 characters;
- exactly three `key_points`, each 6–40 characters;
- natural-language values are primarily Simplified Chinese;
- factual claims must be directly supported by `source_material`.

## Evaluation workflow

```text
Formal Case Set (24: 18 Dev / 6 Holdout)
              ↓
         Prompt v1
              ↓
         Dev baseline
              ↓
       Failure analysis
              ↓
 Evidence-driven Prompt v2
              ↓
     Frozen Holdout v1/v2 pair
              ↓
 Deterministic Rules + blind Grader
              ↓
 Human Review / correction provenance
              ↓
      Automatic paired analysis
              ↓
       Owner recommendation
```

The primary result layer is persisted `calculated_status`. Human Review and
its effective decision are reported separately and never overwrite automatic
results.

## Key result

| Stage | Result |
| --- | --- |
| Dev v1 | 12 pass / 6 fail; all 6 failures were `summary_length` |
| Formal Holdout v1 | 5/6 pass |
| Formal Holdout v2 | 6/6 pass |
| Paired comparison | 1 improved / 5 unchanged / 0 regressed / 0 indeterminate |

The only improved Holdout Case was `brief-holdout-03`, where
`summary_length` changed from fail to pass. Prompt v2 is the recommended
version for this task setup with **Moderate** confidence.

The Formal Holdout contains only six Cases. This result is descriptive and is
not a statistical benchmark or a claim that v2 is universally better.

## What changed in Prompt v2

Prompt v2 was a minimal revision based only on the Dev failure evidence. It
kept the hard summary range at 60–120 characters, added an approximate 70–100
character generation target, and added a source-grounded silent length check.
The target is not a new pass/fail rule: only 2/6 v2 summaries landed in that
target, while all 6/6 satisfied the formal 60–120 range.

## Evaluation layers

1. **Deterministic Rules** check JSON parsing, schema, field counts, lengths,
   and other hard conditions.
2. **Blind AI Grader** performs pointwise semantic checks for required facts,
   closed-world groundedness, language, readability, and diagnostics.
3. **Human Review** is a separate, anonymous decision layer.
4. `calculated_status` is computed only from Rules and Grader results;
   `effective_final_decision` is reported independently when a valid Human
   Review correction exists.

## Auditability and provenance

- Prompt v1 hash: `07aa48853dbe0ed54ff88a2476ce6ec9be2cac4d2680dc2b41d0fc36c392ae4f`
- Prompt v2 hash: `46198292143fa675fc9ad2cb0e724b6811aa3f2455b05f19a75f12e04aeaae74`
- Full Formal Case Set hash:
  `c2555bafffd6d8ac0730a438fe0963530676d63beb7cea7b13a3116ae59f6bb5`
- Dev-only run hash:
  `a23f8d88ad1e35443d3b31bfcd0c60274b204cdbd0738d4ab21eefd24db3cb1c`
- Holdout-only run hash:
  `b22b44b58162a69e74de8af7ab93f9f8507caf3f665f70a68ad630ead004bd6f`
- Task Pack contract hash:
  `ae273822b78d16cba4df5d784d611313f788353229d1b95166047cc1254a2c59`
- Formal Holdout comparison group: `HOLDOUT-COMP-02`
- Formal Grader: Condition 2, DeepSeek Web, visible model `not_visible`
- SQLite foreign-key checks passed; formal DB is local and ignored by Git.

The approved v1 asset snapshots are preserved in
[`db/seed_data/experiment_assets_v1.json`](db/seed_data/experiment_assets_v1.json).
The final Prompt v2 hash, approval state, and experiment evidence are recorded
in [`docs/methodology.md`](docs/methodology.md) and
[`docs/final_report.md`](docs/final_report.md).

## Human Review correction incident

Four sampled Holdout reviews were classified as procedure-invalid after a
renderer display encoding was mistaken for the stored JSON root type. The
original reviews remain unchanged. An append-only corrective re-review records
four authorized corrections, all effective decisions `pass`. This correction
layer does not modify automatic evaluation evidence.

## Repository structure

```text
app.py                    Streamlit entry point
pages/                    Streamlit views
src/eval_lab/domain/      Pure evaluation rules and contracts
src/eval_lab/application/ Workflow orchestration
src/eval_lab/repositories/ SQLite persistence
src/eval_lab/imports/     External JSON/input validation
db/schema.sql             SQLite schema
db/seed_data/             Reproducible Task Pack, Cases, and approved v1 assets
docs/methodology.md       Method and provenance boundary
docs/final_report.md      Final experiment evidence report
docs/run_sheets/          Historical execution records
tests/                    Unit, integration, workflow, and UI tests
```

## Run locally

Requirements are declared in `pyproject.toml`: Python 3.11 or newer,
Streamlit, Pandas, and Pytest for development.

```powershell
python -m pip install -e ".[dev]"
streamlit run app.py
```

The app uses `db/eval_lab.sqlite3` by default. Set `EVAL_LAB_DB_PATH` to use a
different local database when experimenting; do not commit SQLite files.

## Testing

```powershell
python -m pytest -q
python -m compileall -q src pages tests
```

## Documentation

- [Methodology and data boundary](docs/methodology.md)
- [Final experiment report](docs/final_report.md)
- [Design specification](docs/superpowers/specs/2026-08-13-ai-output-eval-lab-design.md)
- [Implementation plan](docs/superpowers/plans/2026-08-13-ai-output-eval-lab-implementation-plan.md)

## Limitations

- The Formal Holdout has six fictional Cases.
- There is no production traffic, live A/B test, statistical significance
  claim, or industry benchmark.
- One Grader Condition and one manual generator environment were used.
- Two Grader diagnostic records are marked possible overreach.
- The 70–100 generation target was hit by only 2/6 v2 summaries.
- Human Review correction provenance is disclosed separately from automatic
  results.

## Status

**Formal experiment complete**
**Recommended version: Prompt v2**
**Confidence: Moderate**
