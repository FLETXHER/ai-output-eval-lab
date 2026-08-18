from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import ContextManager


class SchemaInitializationError(RuntimeError):
    """Raised when schema initialization cannot complete atomically."""


class SchemaMigrationError(RuntimeError):
    """Raised when a schema migration cannot complete atomically."""


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _complete_statements(schema_sql: str) -> Iterator[str]:
    statement = ""
    for line in schema_sql.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            complete_statement = statement.strip()
            if complete_statement:
                yield complete_statement
            statement = ""

    if statement.strip():
        raise ValueError("schema contains an incomplete SQL statement")


def initialize_database(conn: sqlite3.Connection, schema_path: str | Path) -> None:
    try:
        schema_sql = Path(schema_path).read_text(encoding="utf-8")
        conn.execute("BEGIN")
        for statement in _complete_statements(schema_sql):
            conn.execute(statement)
        conn.execute("COMMIT")
    except (OSError, sqlite3.Error, ValueError) as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise SchemaInitializationError("database schema initialization failed") from exc


def apply_migration(conn: sqlite3.Connection, migration_path: str | Path) -> None:
    """Apply one SQL migration as one transaction, or leave no partial changes."""
    try:
        migration_sql = Path(migration_path).read_text(encoding="utf-8")
        with transaction(conn):
            for statement in _complete_statements(migration_sql):
                conn.execute(statement)
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise SchemaMigrationError("database schema migration failed") from exc


@contextmanager
def transaction(conn: sqlite3.Connection) -> ContextManager[sqlite3.Connection]:
    if conn.in_transaction:
        conn.execute("SAVEPOINT eval_lab_nested_transaction")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK TO SAVEPOINT eval_lab_nested_transaction")
            conn.execute("RELEASE SAVEPOINT eval_lab_nested_transaction")
            raise
        else:
            conn.execute("RELEASE SAVEPOINT eval_lab_nested_transaction")
        return
    conn.execute("BEGIN")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )
    return {row[0] for row in rows}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_value(value: str, field_name: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"stored {field_name} is not valid JSON") from exc


def _insert(
    conn: sqlite3.Connection, sql: str, values: Sequence[object]
) -> int:
    with transaction(conn):
        cursor = conn.execute(sql, values)
    return int(cursor.lastrowid)


def insert_task_pack(conn: sqlite3.Connection, data: Mapping[str, object]) -> int:
    return _insert(
        conn,
        """
        INSERT INTO task_packs (
            pack_key, contract_version, contract_hash, language,
            title_min_chars, title_max_chars, summary_min_chars, summary_max_chars,
            key_points_count, key_point_min_chars, key_point_max_chars, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tuple(data[key] for key in (
            "pack_key", "contract_version", "contract_hash", "language", "title_min_chars",
            "title_max_chars", "summary_min_chars", "summary_max_chars", "key_points_count",
            "key_point_min_chars", "key_point_max_chars", "created_at", "updated_at",
        )),
    )


def insert_test_case(conn: sqlite3.Connection, data: Mapping[str, object]) -> int:
    return _insert(
        conn,
        """
        INSERT INTO test_cases (
            task_pack_id, case_key, revision, split, source_material, source_facts_json,
            required_fact_ids_json, explicit_forbidden_claims_json, task_notes,
            feasibility_qa_status, content_hash, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["task_pack_id"], data["case_key"], data["revision"], data["split"],
            data["source_material"], _json(data["source_facts"]),
            _json(data["required_fact_ids"]), _json(data["explicit_forbidden_claims"]),
            data["task_notes"], data["feasibility_qa_status"], data["content_hash"],
            data["created_at"], data["updated_at"],
        ),
    )


def list_test_cases(
    conn: sqlite3.Connection, task_pack_id: int, split: str | None = None
) -> list[sqlite3.Row]:
    if split is None:
        return list(conn.execute(
            "SELECT * FROM test_cases WHERE task_pack_id = ? ORDER BY case_key, revision",
            (task_pack_id,),
        ))
    return list(conn.execute(
        """SELECT * FROM test_cases
        WHERE task_pack_id = ? AND split = ? ORDER BY case_key, revision""",
        (task_pack_id, split),
    ))


def list_task_packs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return the fixed Task Pack records for metadata display."""
    return list(conn.execute("SELECT * FROM task_packs ORDER BY pack_key"))


def list_prompt_versions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return Prompt provenance records without exposing an edit path."""
    return list(
        conn.execute(
            "SELECT * FROM prompt_versions ORDER BY created_at, id"
        )
    )


def metadata_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return read-only Overview counts through the persistence boundary."""
    return {
        "task_packs": int(conn.execute("SELECT COUNT(*) FROM task_packs").fetchone()[0]),
        "test_cases": int(conn.execute("SELECT COUNT(*) FROM test_cases").fetchone()[0]),
        "prompt_versions": int(
            conn.execute("SELECT COUNT(*) FROM prompt_versions").fetchone()[0]
        ),
    }


def insert_prompt_version(conn: sqlite3.Connection, data: Mapping[str, object]) -> int:
    return _insert(
        conn,
        """
        INSERT INTO prompt_versions (
            version_label, prompt_text, change_reason, content_hash, status,
            owner_approved_at, frozen_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tuple(data[key] for key in (
            "version_label", "prompt_text", "change_reason", "content_hash", "status",
            "owner_approved_at", "frozen_at", "created_at", "updated_at",
        )),
    )


def freeze_prompt_version(
    conn: sqlite3.Connection, prompt_version_id: int, frozen_at: str
) -> None:
    with transaction(conn):
        conn.execute(
            "UPDATE prompt_versions SET status = 'frozen', frozen_at = ? WHERE id = ?",
            (frozen_at, prompt_version_id),
        )


def insert_evaluation_run(conn: sqlite3.Connection, data: Mapping[str, object]) -> int:
    return _insert(
        conn,
        """
        INSERT INTO evaluation_runs (
            comparison_group_id, prompt_version_id, split, case_set_hash, contract_hash,
            generator_product, generator_visible_model, environment_notes, protocol_version,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tuple(data[key] for key in (
            "comparison_group_id", "prompt_version_id", "split", "case_set_hash", "contract_hash",
            "generator_product", "generator_visible_model", "environment_notes", "protocol_version",
            "status", "created_at", "updated_at",
        )),
    )


def get_evaluation_run(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM evaluation_runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise LookupError(f"evaluation run {run_id} was not found")
    return row


def update_run_status(conn: sqlite3.Connection, run_id: int, status: str) -> None:
    with transaction(conn):
        conn.execute("UPDATE evaluation_runs SET status = ? WHERE id = ?", (status, run_id))


def update_generator_visible_model(
    conn: sqlite3.Connection, run_id: int, visible_model: str, updated_at: str
) -> None:
    """Persist the one authorized generator provenance field update."""
    with transaction(conn):
        conn.execute(
            """UPDATE evaluation_runs
            SET generator_visible_model = ?, updated_at = ?
            WHERE id = ?""",
            (visible_model, updated_at, run_id),
        )


def insert_model_output_slot(conn: sqlite3.Connection, data: Mapping[str, object]) -> int:
    return _insert(
        conn,
        """
        INSERT INTO model_outputs (
            evaluation_run_id, test_case_id, candidate_id, generation_packet_version,
            generation_packet_hash, raw_response, output_hash, generated_at,
            technical_retry_count, technical_retry_reasons_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["evaluation_run_id"], data["test_case_id"], data["candidate_id"],
            data["generation_packet_version"], data["generation_packet_hash"],
            data.get("raw_response"), data.get("output_hash"), data.get("generated_at"),
            data.get("technical_retry_count", 0), _json(data.get("technical_retry_reasons", [])),
            data["created_at"], data["updated_at"],
        ),
    )


def update_technical_retry(
    conn: sqlite3.Connection, model_output_id: int, reason: str
) -> None:
    row = conn.execute(
        "SELECT technical_retry_reasons_json FROM model_outputs WHERE id = ?", (model_output_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"model output {model_output_id} was not found")
    reasons = _json_value(row["technical_retry_reasons_json"], "technical_retry_reasons_json")
    if not isinstance(reasons, list):
        raise ValueError("stored technical_retry_reasons_json must be a JSON array")
    reasons.append(reason)
    with transaction(conn):
        conn.execute(
            """UPDATE model_outputs
            SET technical_retry_count = technical_retry_count + 1,
                technical_retry_reasons_json = ?
            WHERE id = ?""",
            (_json(reasons), model_output_id),
        )


def insert_rule_results(
    conn: sqlite3.Connection,
    model_output_id: int,
    results: Sequence[Mapping[str, object]],
) -> None:
    with transaction(conn):
        for result in results:
            conn.execute(
                """
                INSERT INTO rule_results (
                    model_output_id, rule_key, rule_version, status, actual_json,
                    expected_json, reason, calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_output_id, result["rule_key"], result["rule_version"], result["status"],
                    _json(result["actual"]), _json(result["expected"]), result["reason"],
                    result["calculated_at"],
                ),
            )


def _grader_condition_exists(conn: sqlite3.Connection, data: Mapping[str, object]) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM grader_conditions
        WHERE grader_product = ? AND grader_visible_model = ?
          AND grader_prompt = ? AND grader_prompt_hash = ? AND grader_prompt_version_label = ?
          AND rubric = ? AND rubric_hash = ? AND rubric_version_label = ?
          AND error_taxonomy = ? AND error_taxonomy_hash = ? AND error_taxonomy_version_label = ?
        """,
        tuple(data[key] for key in (
            "grader_product", "grader_visible_model", "grader_prompt", "grader_prompt_hash",
            "grader_prompt_version_label", "rubric", "rubric_hash", "rubric_version_label",
            "error_taxonomy", "error_taxonomy_hash", "error_taxonomy_version_label",
        )),
    ).fetchone()
    return row is not None


def insert_grader_condition(conn: sqlite3.Connection, data: Mapping[str, object]) -> int:
    if _grader_condition_exists(conn, data):
        raise sqlite3.IntegrityError("duplicate grader condition")
    return _insert(
        conn,
        """
        INSERT INTO grader_conditions (
            grader_product, grader_visible_model, grader_prompt, grader_prompt_hash,
            grader_prompt_version_label, rubric, rubric_hash, rubric_version_label,
            error_taxonomy, error_taxonomy_hash, error_taxonomy_version_label,
            owner_approved_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tuple(data[key] for key in (
            "grader_product", "grader_visible_model", "grader_prompt", "grader_prompt_hash",
            "grader_prompt_version_label", "rubric", "rubric_hash", "rubric_version_label",
            "error_taxonomy", "error_taxonomy_hash", "error_taxonomy_version_label",
            "owner_approved_at", "created_at",
        )),
    )


def insert_grader_result(conn: sqlite3.Connection, data: Mapping[str, object]) -> int:
    return _insert(
        conn,
        """
        INSERT INTO grader_results (
            model_output_id, grader_condition_id, blind_packet_version, blind_packet_hash,
            raw_payload_json, import_status, normalized_semantic_json, language_compliance,
            readability, primary_error_type, secondary_error_types_json,
            unsupported_claims_json, reason_json, evidence_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["model_output_id"], data["grader_condition_id"], data["blind_packet_version"],
            data["blind_packet_hash"], _json(data["raw_payload"]), data["import_status"],
            _json(data["normalized_semantic"]) if data.get("normalized_semantic") is not None else None,
            data.get("language_compliance"), data.get("readability"), data.get("primary_error_type"),
            _json(data["secondary_error_types"]) if data.get("secondary_error_types") is not None else None,
            _json(data["unsupported_claims"]) if data.get("unsupported_claims") is not None else None,
            _json(data["reason"]) if data.get("reason") is not None else None,
            _json(data["evidence"]) if data.get("evidence") is not None else None,
            data["created_at"],
        ),
    )


def insert_grader_fact_results(
    conn: sqlite3.Connection,
    grader_result_id: int,
    results: Sequence[Mapping[str, object]],
) -> None:
    with transaction(conn):
        for result in results:
            conn.execute(
                """
                INSERT INTO grader_fact_results (
                    grader_result_id, fact_id, status, output_evidence, reason
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    grader_result_id, result["fact_id"], result["status"],
                    result["output_evidence"], result["reason"],
                ),
            )


def insert_evaluation_result(conn: sqlite3.Connection, data: Mapping[str, object]) -> int:
    return _insert(
        conn,
        """
        INSERT INTO evaluation_results (
            model_output_id, grader_result_id, grader_condition_id, aggregation_rule_version,
            calculated_status, blocking_reasons_json, calculated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["model_output_id"], data.get("grader_result_id"), data["grader_condition_id"],
            data["aggregation_rule_version"], data["calculated_status"],
            _json(data["blocking_reasons"]), data["calculated_at"],
        ),
    )


def insert_human_review(conn: sqlite3.Connection, data: Mapping[str, object]) -> int:
    return _insert(
        conn,
        """
        INSERT INTO human_reviews (
            evaluation_result_id, review_scope, blind_review, evidence_json, reason,
            final_decision, reviewed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["evaluation_result_id"], data["review_scope"], int(bool(data["blind_review"])),
            _json(data["evidence"]), data["reason"], data.get("final_decision"),
            data["reviewed_at"],
        ),
    )


def insert_human_review_correction(
    conn: sqlite3.Connection, data: Mapping[str, object]
) -> int:
    return _insert(
        conn,
        """
        INSERT INTO human_review_corrections (
            original_human_review_id, evaluation_result_id, review_mode,
            correction_reason, reviewer_evidence_json, reviewer_reason,
            corrected_final_decision, corrected_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["original_human_review_id"], data["evaluation_result_id"],
            data["review_mode"], data["correction_reason"],
            _json(data["reviewer_evidence"]), data["reviewer_reason"],
            data["corrected_final_decision"], data["corrected_at"],
        ),
    )


def insert_human_review_correction_target(
    conn: sqlite3.Connection, data: Mapping[str, object]
) -> int:
    return _insert(
        conn,
        """
        INSERT INTO human_review_correction_targets (
            original_human_review_id, evaluation_result_id,
            authorization_reason, authorized_at
        ) VALUES (?, ?, ?, ?)
        """,
        (
            data["original_human_review_id"], data["evaluation_result_id"],
            data["authorization_reason"], data["authorized_at"],
        ),
    )


def get_human_review_correction_target_for_review(
    conn: sqlite3.Connection, original_human_review_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM human_review_correction_targets
        WHERE original_human_review_id = ?
        """,
        (original_human_review_id,),
    ).fetchone()


def get_human_review_correction_for_review(
    conn: sqlite3.Connection, original_human_review_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM human_review_corrections
        WHERE original_human_review_id = ?
        """,
        (original_human_review_id,),
    ).fetchone()


def list_human_review_corrections(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT * FROM human_review_corrections
            ORDER BY id
            """
        )
    )


def fetch_output_context(conn: sqlite3.Connection, model_output_id: int) -> dict[str, object]:
    row = conn.execute(
        """
        SELECT
            mo.id AS model_output_id, mo.evaluation_run_id, mo.test_case_id, mo.candidate_id,
            mo.generation_packet_version, mo.generation_packet_hash, mo.raw_response,
            mo.output_hash, mo.generated_at, mo.technical_retry_count,
            mo.technical_retry_reasons_json, mo.created_at AS model_output_created_at,
            mo.updated_at AS model_output_updated_at,
            tc.id AS case_id, tc.case_key, tc.revision AS case_revision, tc.split AS case_split,
            tc.source_material, tc.source_facts_json, tc.required_fact_ids_json,
            tc.explicit_forbidden_claims_json, tc.task_notes, tc.feasibility_qa_status,
            tc.content_hash AS case_content_hash, tc.created_at AS case_created_at,
            tc.updated_at AS case_updated_at,
            tp.id AS task_pack_id, tp.pack_key, tp.contract_version, tp.contract_hash,
            tp.language, tp.title_min_chars, tp.title_max_chars, tp.summary_min_chars,
            tp.summary_max_chars, tp.key_points_count, tp.key_point_min_chars,
            tp.key_point_max_chars, tp.created_at AS task_pack_created_at,
            tp.updated_at AS task_pack_updated_at,
            er.id AS run_id, er.comparison_group_id, er.prompt_version_id,
            er.split AS run_split, er.case_set_hash, er.contract_hash AS run_contract_hash,
            er.generator_product, er.generator_visible_model, er.environment_notes,
            er.protocol_version, er.status AS run_status, er.created_at AS run_created_at,
            er.updated_at AS run_updated_at,
            pv.id AS prompt_id, pv.version_label, pv.prompt_text, pv.change_reason,
            pv.content_hash AS prompt_content_hash, pv.status AS prompt_status,
            pv.owner_approved_at, pv.frozen_at, pv.created_at AS prompt_created_at,
            pv.updated_at AS prompt_updated_at
        FROM model_outputs AS mo
        JOIN test_cases AS tc ON tc.id = mo.test_case_id
        JOIN task_packs AS tp ON tp.id = tc.task_pack_id
        JOIN evaluation_runs AS er ON er.id = mo.evaluation_run_id
        JOIN prompt_versions AS pv ON pv.id = er.prompt_version_id
        WHERE mo.id = ?
        """,
        (model_output_id,),
    ).fetchone()
    if row is None:
        raise LookupError(f"model output {model_output_id} was not found")
    return {
        "model_output": {
            "id": row["model_output_id"], "evaluation_run_id": row["evaluation_run_id"],
            "test_case_id": row["test_case_id"], "candidate_id": row["candidate_id"],
            "generation_packet_version": row["generation_packet_version"],
            "generation_packet_hash": row["generation_packet_hash"],
            "raw_response": row["raw_response"], "output_hash": row["output_hash"],
            "generated_at": row["generated_at"], "technical_retry_count": row["technical_retry_count"],
            "technical_retry_reasons": _json_value(row["technical_retry_reasons_json"], "technical_retry_reasons_json"),
            "created_at": row["model_output_created_at"], "updated_at": row["model_output_updated_at"],
        },
        "test_case": {
            "id": row["case_id"], "case_key": row["case_key"], "revision": row["case_revision"],
            "split": row["case_split"], "source_material": row["source_material"],
            "source_facts": _json_value(row["source_facts_json"], "source_facts_json"),
            "required_fact_ids": _json_value(row["required_fact_ids_json"], "required_fact_ids_json"),
            "explicit_forbidden_claims": _json_value(row["explicit_forbidden_claims_json"], "explicit_forbidden_claims_json"),
            "task_notes": row["task_notes"], "feasibility_qa_status": row["feasibility_qa_status"],
            "content_hash": row["case_content_hash"], "created_at": row["case_created_at"],
            "updated_at": row["case_updated_at"],
        },
        "task_pack": {
            "id": row["task_pack_id"], "pack_key": row["pack_key"],
            "contract_version": row["contract_version"], "contract_hash": row["contract_hash"],
            "language": row["language"], "title_min_chars": row["title_min_chars"],
            "title_max_chars": row["title_max_chars"], "summary_min_chars": row["summary_min_chars"],
            "summary_max_chars": row["summary_max_chars"], "key_points_count": row["key_points_count"],
            "key_point_min_chars": row["key_point_min_chars"], "key_point_max_chars": row["key_point_max_chars"],
            "created_at": row["task_pack_created_at"], "updated_at": row["task_pack_updated_at"],
        },
        "evaluation_run": {
            "id": row["run_id"], "comparison_group_id": row["comparison_group_id"],
            "prompt_version_id": row["prompt_version_id"], "split": row["run_split"],
            "case_set_hash": row["case_set_hash"], "contract_hash": row["run_contract_hash"],
            "generator_product": row["generator_product"],
            "generator_visible_model": row["generator_visible_model"],
            "environment_notes": row["environment_notes"], "protocol_version": row["protocol_version"],
            "status": row["run_status"], "created_at": row["run_created_at"],
            "updated_at": row["run_updated_at"],
        },
        "prompt_version": {
            "id": row["prompt_id"], "version_label": row["version_label"],
            "prompt_text": row["prompt_text"], "change_reason": row["change_reason"],
            "content_hash": row["prompt_content_hash"], "status": row["prompt_status"],
            "owner_approved_at": row["owner_approved_at"], "frozen_at": row["frozen_at"],
            "created_at": row["prompt_created_at"], "updated_at": row["prompt_updated_at"],
        },
    }


def fetch_raw_response(conn: sqlite3.Connection, model_output_id: int) -> str | None:
    row = conn.execute(
        "SELECT raw_response FROM model_outputs WHERE id = ?", (model_output_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"model output {model_output_id} was not found")
    return row["raw_response"]


def fetch_retry_count(conn: sqlite3.Connection, model_output_id: int) -> int:
    row = conn.execute(
        "SELECT technical_retry_count FROM model_outputs WHERE id = ?", (model_output_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"model output {model_output_id} was not found")
    return int(row["technical_retry_count"])
