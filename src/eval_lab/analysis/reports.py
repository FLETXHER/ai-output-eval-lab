from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import re
import sqlite3

import pandas as pd


_QUERY_MARKER = re.compile(r"^-- name: ([a-z_]+)\s*$", re.MULTILINE)
_READ_ONLY_TOKENS = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|REPLACE|VACUUM|ATTACH|DETACH|PRAGMA|BEGIN|COMMIT|ROLLBACK)\b",
    re.IGNORECASE,
)
_PAIR_CONDITION_KEYS = (
    "split",
    "case_set_hash",
    "contract_hash",
    "generator_product",
    "generator_visible_model",
    "environment_notes",
    "protocol_version",
)
_RUN_SCOPED_QUERY_NAMES = frozenset({
    "run_summary",
    "status_distribution",
    "rule_failures",
    "required_fact_failures",
    "unsupported_claims",
    "error_types",
    "bad_cases",
})


def _queries() -> dict[str, str]:
    source = Path(__file__).with_name("queries.sql").read_text(encoding="utf-8")
    matches = list(_QUERY_MARKER.finditer(source))
    return {
        match.group(1): source[match.end(): matches[index + 1].start() if index + 1 < len(matches) else None].strip()
        for index, match in enumerate(matches)
    }


def load_query(query_name: str) -> str:
    """Return one named, package-owned read-only SQL query."""
    try:
        return _queries()[query_name]
    except KeyError as exc:
        raise KeyError(f"unknown analysis query: {query_name}") from exc


def run_query(
    conn: sqlite3.Connection, query_name: str, params: Sequence[object] = ()
) -> pd.DataFrame:
    """Execute one fixed read-only query and return its rows as a DataFrame."""
    query = load_query(query_name)
    if _READ_ONLY_TOKENS.search(query):
        raise ValueError(f"analysis query {query_name!r} is not read-only")
    _guard_query_grader_conditions(conn, query_name, params)
    cursor = conn.execute(query, tuple(params))
    columns = [column[0] for column in cursor.description]
    return pd.DataFrame.from_records([tuple(row) for row in cursor.fetchall()], columns=columns)


def _grader_condition_ids_for_runs(
    conn: sqlite3.Connection, run_ids: Sequence[object]
) -> set[int]:
    unique_run_ids = tuple(dict.fromkeys(run_ids))
    if not unique_run_ids:
        return set()
    placeholders = ", ".join("?" for _ in unique_run_ids)
    rows = conn.execute(
        f"""
        SELECT DISTINCT grader_condition_id
        FROM grader_results AS gr
        JOIN model_outputs AS mo ON mo.id = gr.model_output_id
        WHERE mo.evaluation_run_id IN ({placeholders})
        UNION
        SELECT DISTINCT grader_condition_id
        FROM evaluation_results AS ev
        JOIN model_outputs AS mo ON mo.id = ev.model_output_id
        WHERE mo.evaluation_run_id IN ({placeholders})
        """,
        unique_run_ids * 2,
    )
    return {int(row[0]) for row in rows}


def _assert_single_grader_condition_for_runs(
    conn: sqlite3.Connection, run_ids: Sequence[object]
) -> set[int]:
    condition_ids = _grader_condition_ids_for_runs(conn, run_ids)
    if len(condition_ids) > 1:
        raise ValueError("analysis cannot merge multiple grader conditions")
    return condition_ids


def _run_ids_for_comparison_group(
    conn: sqlite3.Connection, comparison_group_id: object
) -> tuple[int, ...]:
    rows = conn.execute(
        "SELECT id FROM evaluation_runs WHERE comparison_group_id = ? ORDER BY id",
        (comparison_group_id,),
    )
    return tuple(int(row[0]) for row in rows)


def _guard_query_grader_conditions(
    conn: sqlite3.Connection, query_name: str, params: Sequence[object]
) -> None:
    if query_name in _RUN_SCOPED_QUERY_NAMES:
        if not params:
            raise ValueError(f"analysis query {query_name!r} requires a run id")
        _assert_single_grader_condition_for_runs(conn, (params[0],))
    elif query_name == "paired_comparison":
        if len(params) < 2:
            raise ValueError("paired_comparison requires two run ids")
        _assert_single_grader_condition_for_runs(conn, (params[0], params[1]))
    elif query_name == "review_coverage":
        if not params:
            raise ValueError("review_coverage requires a comparison group id")
        _assert_single_grader_condition_for_runs(
            conn, _run_ids_for_comparison_group(conn, params[0])
        )


def run_summary(conn: sqlite3.Connection, run_id: int) -> pd.DataFrame:
    return run_query(conn, "run_summary", (run_id,))


def status_distribution(conn: sqlite3.Connection, run_id: int) -> pd.DataFrame:
    return run_query(conn, "status_distribution", (run_id, run_id))


def _comparable_runs(conn: sqlite3.Connection, comparison_group_id: str) -> list[sqlite3.Row]:
    rows = list(conn.execute(
        """
        SELECT er.*, pv.version_label
        FROM evaluation_runs AS er
        JOIN prompt_versions AS pv ON pv.id = er.prompt_version_id
        WHERE er.comparison_group_id = ?
        ORDER BY pv.version_label, er.id
        """,
        (comparison_group_id,),
    ))
    if len(rows) != 2:
        raise ValueError("paired comparison requires exactly two runs in the comparison group")
    first, second = rows
    if first["prompt_version_id"] == second["prompt_version_id"]:
        raise ValueError("paired comparison requires two distinct prompt versions")
    for key in _PAIR_CONDITION_KEYS:
        if first[key] != second[key]:
            raise ValueError(f"paired comparison runs are not comparable: {key} differs")
    return rows


def _comparison_label(left: object, right: object) -> str:
    if left is None or right is None or "indeterminate" in {left, right}:
        return "indeterminate"
    if left == right:
        return "unchanged"
    if left == "fail" and right == "pass":
        return "improved"
    if left == "pass" and right == "fail":
        return "regressed"
    return "indeterminate"


def paired_comparison(conn: sqlite3.Connection, comparison_group_id: str) -> pd.DataFrame:
    """Compare the two fully matched runs without collapsing decision layers."""
    left, right = _comparable_runs(conn, comparison_group_id)
    left_conditions = _grader_condition_ids_for_runs(conn, (left["id"],))
    right_conditions = _grader_condition_ids_for_runs(conn, (right["id"],))
    if len(left_conditions) != 1 or len(right_conditions) != 1 or left_conditions != right_conditions:
        raise ValueError("paired comparison requires one shared grader condition")
    table = run_query(conn, "paired_comparison", (left["id"], right["id"], left["id"], right["id"]))
    table.insert(1, "left_prompt_version", left["version_label"])
    table.insert(2, "right_prompt_version", right["version_label"])
    table["comparison"] = [
        _comparison_label(row.left_calculated_status, row.right_calculated_status)
        for row in table.itertuples(index=False)
    ]
    return table


def failure_breakdown(conn: sqlite3.Connection, run_id: int) -> dict[str, pd.DataFrame]:
    return {
        name: run_query(conn, name, (run_id,))
        for name in (
            "rule_failures",
            "required_fact_failures",
            "unsupported_claims",
            "error_types",
            "bad_cases",
        )
    }


def review_coverage(conn: sqlite3.Connection, comparison_group_id: str) -> pd.DataFrame:
    return run_query(conn, "review_coverage", (comparison_group_id,))
