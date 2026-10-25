"""SQLite storage for runs, files, and findings."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

CREATE_RUNS = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    content_folder TEXT NOT NULL,
    checker_version TEXT NOT NULL,
    files_checked INTEGER NOT NULL,
    finding_count INTEGER NOT NULL
)
"""

CREATE_FILES = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs (id),
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    reason TEXT NOT NULL
)
"""

CREATE_FINDINGS = """
CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs (id),
    file_id INTEGER NOT NULL REFERENCES files (id),
    line INTEGER NOT NULL,
    rule TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL
)
"""


def connect(db_path):
    """Open the database, creating the folder and tables, and return the connection.

    Foreign keys are switched on right after opening. The caller closes the
    connection with contextlib.closing.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        _create_schema(connection)
    except BaseException:
        connection.close()
        raise
    return connection


def _create_schema(connection):
    """Create the tables if missing and mark a new database with user_version 1."""
    is_new = connection.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0] == 0
    connection.execute(CREATE_RUNS)
    connection.execute(CREATE_FILES)
    connection.execute(CREATE_FINDINGS)
    if is_new:
        connection.execute("PRAGMA user_version = 1")


def save_run(connection, content_folder, checker_version, source_files, findings):
    """Save one run, its files, and its findings in one transaction.

    findings is a list of (path, Finding) pairs. Returns the new run id. This is
    the only function that commits. Any error rolls everything back and is re-raised.
    """
    try:
        run_id = _insert_run(connection, content_folder, checker_version, source_files, findings)
        file_ids = _insert_files(connection, run_id, source_files)
        _insert_findings(connection, run_id, file_ids, findings)
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return run_id


def _insert_run(connection, content_folder, checker_version, source_files, findings):
    """Insert the run row and return its id. Does not commit."""
    started_at = datetime.now(timezone.utc).isoformat()
    cursor = connection.execute(
        "INSERT INTO runs (started_at, content_folder, checker_version, "
        "files_checked, finding_count) VALUES (?, ?, ?, ?, ?)",
        (started_at, str(content_folder), checker_version, len(source_files), len(findings)),
    )
    return cursor.lastrowid


def _insert_files(connection, run_id, source_files):
    """Insert a row for every source file and return a dict of path to file id."""
    file_ids = {}
    for source in source_files:
        cursor = connection.execute(
            "INSERT INTO files (run_id, path, kind, reason) VALUES (?, ?, ?, ?)",
            (run_id, source.path, source.kind, source.reason),
        )
        file_ids[source.path] = cursor.lastrowid
    return file_ids


def _insert_findings(connection, run_id, file_ids, findings):
    """Insert a row for every finding, looking up its file id as it goes."""
    for path, finding in findings:
        if path not in file_ids:
            raise ValueError(f"Finding path matches no source file: {path}")
        connection.execute(
            "INSERT INTO findings (run_id, file_id, line, rule, severity, message) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, file_ids[path], finding.line, finding.rule, finding.severity, finding.message),
        )
