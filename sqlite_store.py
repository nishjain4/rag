"""Load an uploaded CSV/Excel file into SQLite and run read-only queries against it."""

import os
import re
import sqlite3
from typing import Any

import pandas as pd

from config import MAX_QUERY_ROWS, SAMPLE_VALUES_PER_COLUMN, SQLITE_DB_PATH

_IDENTIFIER_PATTERN = re.compile(r"\W+")
_READ_ONLY_PREFIXES = ("select", "with")
_FORBIDDEN_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex)\b",
    re.IGNORECASE,
)


def _sanitize(name: str, fallback: str) -> str:
    cleaned = _IDENTIFIER_PATTERN.sub("_", str(name).strip()).strip("_")
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"{fallback}_{cleaned}" if cleaned else fallback
    return cleaned


def _unique(name: str, taken: set[str]) -> str:
    candidate = name
    suffix = 2
    while candidate.lower() in taken:
        candidate = f"{name}_{suffix}"
        suffix += 1
    taken.add(candidate.lower())
    return candidate


def _read_frames(file_path: str) -> dict[str, pd.DataFrame]:
    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".csv":
        base = os.path.splitext(os.path.basename(file_path))[0]
        return {base: pd.read_csv(file_path)}
    if extension in {".xlsx", ".xls"}:
        return pd.read_excel(file_path, sheet_name=None)

    raise ValueError(f"Unsupported file type: {extension}")


def _clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.dropna(axis=1, how="all").dropna(axis=0, how="all")
    return frame.loc[:, [column for column in frame.columns if "Unnamed" not in str(column)]]


def _samples(frame: pd.DataFrame, column: str) -> list[str]:
    values = frame[column].dropna().astype(str).str.strip()
    values = values[values != ""].unique()[:SAMPLE_VALUES_PER_COLUMN]
    return [str(value) for value in values]


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(SQLITE_DB_PATH)
    connection.isolation_level = None  # VACUUM cannot run inside a transaction
    return connection


def _drop_all_tables(connection: sqlite3.Connection) -> None:
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') "
        "AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for (name,) in tables:
        connection.execute(f'DROP TABLE IF EXISTS "{name}"')


def reset_database() -> None:
    """Drop every table so no trace of the previous upload is left behind."""
    if not os.path.exists(SQLITE_DB_PATH):
        return
    connection = _connect()
    try:
        _drop_all_tables(connection)
        connection.execute("VACUUM")
    finally:
        connection.close()


def build_database(file_path: str) -> list[dict]:
    """Replace the database contents with the uploaded file and return the resulting schema."""
    frames = _read_frames(file_path)

    connection = _connect()
    try:
        _drop_all_tables(connection)

        schema: list[dict] = []
        taken_tables: set[str] = set()

        for sheet_name, frame in frames.items():
            frame = _clean_frame(frame)
            if frame.empty or not len(frame.columns):
                continue

            taken_columns: set[str] = set()
            renamed = {}
            for index, column in enumerate(frame.columns):
                sanitized = _unique(_sanitize(column, f"column_{index + 1}"), taken_columns)
                renamed[column] = sanitized

            frame = frame.rename(columns=renamed)
            table_name = _unique(_sanitize(sheet_name, "table"), taken_tables)
            frame.to_sql(table_name, connection, if_exists="replace", index=False)

            types = {
                row[1]: row[2]
                for row in connection.execute(f'PRAGMA table_info("{table_name}")')
            }
            schema.append({
                "table": table_name,
                "row_count": len(frame),
                "columns": [
                    {
                        "name": renamed[original],
                        "original_name": str(original),
                        "data_type": types.get(renamed[original], "TEXT"),
                        "samples": _samples(frame, renamed[original]),
                    }
                    for original in renamed
                ],
            })
    finally:
        connection.close()

    if not schema:
        raise ValueError("No readable table could be built from the uploaded file")

    return schema


def is_read_only(sql: str) -> bool:
    statement = sql.strip().rstrip(";").strip()
    if not statement.lower().startswith(_READ_ONLY_PREFIXES):
        return False
    if ";" in statement:
        return False
    return not _FORBIDDEN_PATTERN.search(statement)


def run_query(sql: str) -> dict[str, Any]:
    """Execute a single read-only statement and return its columns and rows."""
    statement = sql.strip().rstrip(";").strip()
    if not is_read_only(statement):
        raise ValueError("Only a single read-only SELECT statement can be executed")
    if not os.path.exists(SQLITE_DB_PATH):
        raise ValueError("No document uploaded. Please upload a document first.")

    connection = sqlite3.connect(f"file:{SQLITE_DB_PATH}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        cursor = connection.execute(statement)
        rows = cursor.fetchmany(MAX_QUERY_ROWS)
        columns = [description[0] for description in cursor.description or []]
    finally:
        connection.close()

    return {
        "columns": columns,
        "rows": [list(row) for row in rows],
        "truncated": len(rows) == MAX_QUERY_ROWS,
    }


def format_rows(result: dict[str, Any], max_rows: int = 30) -> str:
    """Render a query result as a compact text table for the answering model."""
    columns = result.get("columns", [])
    rows = result.get("rows", [])
    if not columns:
        return "(no columns)"
    if not rows:
        return "(no rows returned)"

    lines = [" | ".join(str(column) for column in columns)]
    for row in rows[:max_rows]:
        lines.append(" | ".join("" if value is None else str(value) for value in row))
    if len(rows) > max_rows:
        lines.append(f"... {len(rows) - max_rows} more rows")
    return "\n".join(lines)
