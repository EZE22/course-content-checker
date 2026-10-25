import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from content_checker.loader import SourceFile
from content_checker.rules import Finding
from content_checker.storage import connect, save_run

EXPECTED_COLUMNS = {
    "runs": [
        "id",
        "started_at",
        "content_folder",
        "checker_version",
        "files_checked",
        "finding_count",
    ],
    "files": ["id", "run_id", "path", "kind", "reason"],
    "findings": ["id", "run_id", "file_id", "line", "rule", "severity", "message"],
}


def make_files():
    return [
        SourceFile("a.md", "article", "text a", ""),
        SourceFile("labs/lab-1.md", "lab", "text b", ""),
    ]


def make_findings():
    return [
        ("a.md", Finding(3, "em_dash", "error", "Em dash found.")),
        ("labs/lab-1.md", Finding(1, "missing_section", "error", "Missing Grading Rubric.")),
    ]


def count(db_path, table):
    with closing(sqlite3.connect(db_path)) as other:
        return other.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def table_names(connection):
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows}


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "data" / "history.db"


# 1. connect creates the folder, the file, the tables, and user_version


def test_connect_creates_parent_folder_and_database_file(db_path):
    assert not db_path.parent.exists()
    with closing(connect(db_path)):
        pass
    assert db_path.parent.is_dir()
    assert db_path.is_file()


def test_connect_creates_the_three_tables_with_exact_columns(db_path):
    with closing(connect(db_path)) as connection:
        for table, columns in EXPECTED_COLUMNS.items():
            info = connection.execute(f"PRAGMA table_info({table})").fetchall()
            assert [row[1] for row in info] == columns
        names = table_names(connection)
    assert {"runs", "files", "findings"} <= names


def test_connect_sets_user_version_to_1(db_path):
    with closing(connect(db_path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


# 2. Foreign keys are on for every connection


def test_connect_switches_foreign_keys_on(db_path):
    with closing(connect(db_path)) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_connect_switches_foreign_keys_on_for_a_second_connection(db_path):
    with closing(connect(db_path)):
        pass
    with closing(connect(db_path)) as second:
        assert second.execute("PRAGMA foreign_keys").fetchone()[0] == 1


# 3. An existing database is left alone


def test_connect_on_existing_database_keeps_rows(db_path):
    with closing(connect(db_path)) as connection:
        connection.execute(
            "INSERT INTO runs (started_at, content_folder, checker_version, "
            "files_checked, finding_count) VALUES (?, ?, ?, ?, ?)",
            ("2026-01-01T00:00:00+00:00", "content", "1.0.0", 5, 2),
        )
        connection.commit()
    with closing(connect(db_path)) as connection:
        rows = connection.execute(
            "SELECT started_at, content_folder, checker_version, files_checked, "
            "finding_count FROM runs"
        ).fetchall()
        assert rows == [("2026-01-01T00:00:00+00:00", "content", "1.0.0", 5, 2)]
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


# 4. save_run writes one run, its files, and its findings


def test_save_run_writes_run_files_and_findings(db_path):
    with closing(connect(db_path)) as connection:
        run_id = save_run(connection, "content", "1.0.0", make_files(), make_findings())
    assert count(db_path, "runs") == 1
    assert count(db_path, "files") == 2
    assert count(db_path, "findings") == 2
    with closing(sqlite3.connect(db_path)) as other:
        run = other.execute(
            "SELECT id, files_checked, finding_count FROM runs"
        ).fetchone()
        assert run == (run_id, 2, 2)
        file_run_ids = {r[0] for r in other.execute("SELECT run_id FROM files")}
        assert file_run_ids == {run_id}
        finding_run_ids = {r[0] for r in other.execute("SELECT run_id FROM findings")}
        assert finding_run_ids == {run_id}


def test_save_run_links_each_finding_to_the_file_with_the_same_path(db_path):
    with closing(connect(db_path)) as connection:
        save_run(connection, "content", "1.0.0", make_files(), make_findings())
    with closing(sqlite3.connect(db_path)) as other:
        rows = other.execute(
            "SELECT files.path, findings.rule FROM findings "
            "JOIN files ON files.id = findings.file_id ORDER BY files.path"
        ).fetchall()
    assert rows == [("a.md", "em_dash"), ("labs/lab-1.md", "missing_section")]


def test_save_run_returns_the_new_run_id(db_path):
    with closing(connect(db_path)) as connection:
        first = save_run(connection, "content", "1.0.0", make_files(), make_findings())
        second = save_run(connection, "content", "1.0.0", make_files(), [])
    assert isinstance(first, int)
    assert second != first
    with closing(sqlite3.connect(db_path)) as other:
        ids = [row[0] for row in other.execute("SELECT id FROM runs ORDER BY id")]
    assert ids == [first, second]


# 5. Unreadable files


def test_save_run_stores_unreadable_file_with_reason(db_path):
    files = [
        SourceFile("good.md", "article", "text", ""),
        SourceFile("bad.md", "unreadable", "", "Not valid UTF-8: bad byte"),
    ]
    with closing(connect(db_path)) as connection:
        save_run(connection, "content", "1.0.0", files, [])
    with closing(sqlite3.connect(db_path)) as other:
        rows = other.execute("SELECT path, kind, reason FROM files ORDER BY path").fetchall()
    assert rows == [
        ("bad.md", "unreadable", "Not valid UTF-8: bad byte"),
        ("good.md", "article", ""),
    ]


# 6. Clean runs and empty runs


def test_clean_run_is_saved_with_zero_findings(db_path):
    with closing(connect(db_path)) as connection:
        save_run(connection, "content", "1.0.0", make_files(), [])
    with closing(sqlite3.connect(db_path)) as other:
        row = other.execute("SELECT files_checked, finding_count FROM runs").fetchone()
    assert row == (2, 0)
    assert count(db_path, "files") == 2
    assert count(db_path, "findings") == 0


def test_run_with_no_files_is_saved(db_path):
    with closing(connect(db_path)) as connection:
        save_run(connection, "content", "1.0.0", [], [])
    with closing(sqlite3.connect(db_path)) as other:
        row = other.execute("SELECT files_checked, finding_count FROM runs").fetchone()
    assert row == (0, 0)
    assert count(db_path, "files") == 0
    assert count(db_path, "findings") == 0


# 7. Values read back correctly


def test_saved_values_read_back_correctly(db_path):
    with closing(connect(db_path)) as connection:
        save_run(connection, "/some/content", "1.2.3", make_files(), make_findings())
    with closing(sqlite3.connect(db_path)) as other:
        run = other.execute("SELECT content_folder, checker_version FROM runs").fetchone()
        files = other.execute("SELECT path, kind, reason FROM files ORDER BY path").fetchall()
        findings = other.execute(
            "SELECT files.path, findings.line, findings.rule, findings.severity, "
            "findings.message FROM findings JOIN files ON files.id = findings.file_id "
            "ORDER BY files.path"
        ).fetchall()
    assert run == ("/some/content", "1.2.3")
    assert files == [("a.md", "article", ""), ("labs/lab-1.md", "lab", "")]
    assert findings == [
        ("a.md", 3, "em_dash", "error", "Em dash found."),
        ("labs/lab-1.md", 1, "missing_section", "error", "Missing Grading Rubric."),
    ]


def test_started_at_parses_as_a_utc_timestamp(db_path):
    before = datetime.now(timezone.utc) - timedelta(minutes=1)
    with closing(connect(db_path)) as connection:
        save_run(connection, "content", "1.0.0", [], [])
    after = datetime.now(timezone.utc) + timedelta(minutes=1)
    with closing(sqlite3.connect(db_path)) as other:
        started_at = other.execute("SELECT started_at FROM runs").fetchone()[0]
    assert isinstance(started_at, str)
    parsed = datetime.fromisoformat(started_at)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    assert parsed.utcoffset() == timedelta(0)
    assert before <= parsed <= after


# 8. Rollback


def test_failed_save_leaves_no_trace(db_path):
    bad_findings = make_findings() + [
        ("missing.md", Finding(1, "em_dash", "error", "No such file in the run."))
    ]
    with closing(connect(db_path)) as connection:
        with pytest.raises(ValueError, match="missing.md"):
            save_run(connection, "content", "1.0.0", make_files(), bad_findings)
    assert count(db_path, "runs") == 0
    assert count(db_path, "files") == 0
    assert count(db_path, "findings") == 0


def test_failed_save_leaves_no_trace_on_the_same_connection(db_path):
    bad_findings = [("missing.md", Finding(1, "em_dash", "error", "No such file."))]
    with closing(connect(db_path)) as connection:
        with pytest.raises(ValueError, match="missing.md"):
            save_run(connection, "content", "1.0.0", make_files(), bad_findings)
        for table in ("runs", "files", "findings"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


# 9. Rollback keeps earlier data


def test_failed_second_save_keeps_first_run_complete(db_path):
    with closing(connect(db_path)) as connection:
        first_id = save_run(connection, "content", "1.0.0", make_files(), make_findings())
        bad_findings = [("missing.md", Finding(1, "em_dash", "error", "No such file."))]
        with pytest.raises(ValueError, match="missing.md"):
            save_run(connection, "content", "1.0.1", make_files(), bad_findings)
    assert count(db_path, "runs") == 1
    assert count(db_path, "files") == 2
    assert count(db_path, "findings") == 2
    with closing(sqlite3.connect(db_path)) as other:
        assert other.execute("SELECT id, checker_version FROM runs").fetchall() == [
            (first_id, "1.0.0")
        ]
        assert {r[0] for r in other.execute("SELECT run_id FROM files")} == {first_id}
        assert {r[0] for r in other.execute("SELECT run_id FROM findings")} == {first_id}


# 10. Foreign key enforced


def test_finding_with_unknown_run_id_raises_integrity_error(db_path):
    with closing(connect(db_path)) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO findings (run_id, file_id, line, rule, severity, message) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (999, 999, 1, "em_dash", "error", "orphan"),
            )


# 11. Values are passed as parameters


def test_hostile_message_is_stored_exactly_and_tables_survive(db_path):
    message = "It's a trap '); DROP TABLE runs; --"
    findings = [("a.md", Finding(2, "em_dash", "error", message))]
    with closing(connect(db_path)) as connection:
        save_run(connection, "content", "1.0.0", make_files(), findings)
        assert {"runs", "files", "findings"} <= table_names(connection)
    with closing(sqlite3.connect(db_path)) as other:
        stored = other.execute("SELECT message FROM findings").fetchone()[0]
    assert stored == message
    assert count(db_path, "runs") == 1


# 12. The connection is closed by contextlib.closing


def test_connection_is_closed_after_the_with_block(db_path):
    with closing(connect(db_path)) as connection:
        connection.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
