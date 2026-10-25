import importlib.metadata
import sqlite3
from contextlib import closing

import pytest

from content_checker.cli import main
from content_checker.loader import SourceFile
from content_checker.rules import Finding
from content_checker.storage import connect, save_run


def make_history(path, runs=2):
    """Build a populated history database, each run with two files and two findings."""
    for number in range(runs):
        source_files = [
            SourceFile(path="a.md", kind="article", text="text", reason=""),
            SourceFile(path="lab-b.md", kind="lab", text="text", reason=""),
        ]
        findings = [
            ("a.md", Finding(line=1, rule="missing_section", severity="error", message="one")),
            ("lab-b.md", Finding(line=3, rule="table_pipe", severity="error", message="two")),
        ]
        with closing(connect(path)) as connection:
            save_run(connection, "/content", f"1.0.{number}", source_files, findings)
    return path


def count_runs(path):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]


def tree(folder):
    return sorted(str(item.relative_to(folder)) for item in folder.rglob("*"))


def assert_one_error_line(captured, *needles):
    assert captured.out == ""
    assert captured.err.endswith("\n")
    lines = captured.err.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("Error:")
    for needle in needles:
        assert needle in lines[0]


def test_version_flag(capsys):
    assert main(["--version"]) == 0

    captured = capsys.readouterr()
    version = importlib.metadata.version("course-content-checker")
    assert captured.out == f"content-checker {version}\n"
    assert captured.err == ""


def test_backup_success(tmp_path, monkeypatch, capsys):
    db_path = make_history(tmp_path / "data" / "history.db")
    monkeypatch.setenv("CHECKER_DB", str(db_path))
    destination = str(tmp_path / "backups" / "history.bak")

    assert main(["backup", destination]) == 0

    captured = capsys.readouterr()
    assert captured.out == f"Backup saved: {destination}\nIntegrity check: ok\n"
    assert captured.err == ""
    assert (tmp_path / "backups" / "history.bak").is_file()


def test_restore_success(tmp_path, monkeypatch, capsys):
    backup = make_history(tmp_path / "backups" / "history.bak", runs=3)
    db_path = tmp_path / "data" / "history.db"
    monkeypatch.setenv("CHECKER_DB", str(db_path))

    assert main(["restore", str(backup)]) == 0

    captured = capsys.readouterr()
    assert captured.out == f"Restored: {db_path}\nIntegrity check: ok\n"
    assert captured.err == ""
    assert count_runs(db_path) == 3


@pytest.mark.parametrize("command", ["backup", "restore"])
@pytest.mark.parametrize("env_state", ["unset", "empty"])
def test_missing_checker_db_is_a_usage_error(tmp_path, monkeypatch, capsys, command, env_state):
    if env_state == "unset":
        monkeypatch.delenv("CHECKER_DB", raising=False)
    else:
        monkeypatch.setenv("CHECKER_DB", "")
    backup = make_history(tmp_path / "src" / "history.bak")
    argument = str(backup) if command == "restore" else str(tmp_path / "out" / "copy.bak")
    before = tree(tmp_path)
    backup_bytes = backup.read_bytes()

    assert main([command, argument]) == 2

    assert_one_error_line(capsys.readouterr(), "CHECKER_DB")
    assert tree(tmp_path) == before
    assert backup.read_bytes() == backup_bytes


def test_backup_to_an_existing_destination_fails(tmp_path, monkeypatch, capsys):
    db_path = make_history(tmp_path / "data" / "history.db")
    monkeypatch.setenv("CHECKER_DB", str(db_path))
    destination = tmp_path / "copy.bak"
    destination.write_bytes(b"do not touch")
    history_before = db_path.read_bytes()

    assert main(["backup", str(destination)]) == 2

    assert_one_error_line(capsys.readouterr(), str(destination))
    assert destination.read_bytes() == b"do not touch"
    assert db_path.read_bytes() == history_before


def test_backup_of_a_missing_history_fails(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "data" / "history.db"
    monkeypatch.setenv("CHECKER_DB", str(db_path))
    destination = tmp_path / "out" / "copy.bak"

    assert main(["backup", str(destination)]) == 2

    assert_one_error_line(capsys.readouterr(), str(db_path))
    assert not db_path.exists()
    assert not destination.exists()


def test_restore_of_a_missing_backup_fails(tmp_path, monkeypatch, capsys):
    db_path = make_history(tmp_path / "data" / "history.db")
    monkeypatch.setenv("CHECKER_DB", str(db_path))
    missing = tmp_path / "nope.bak"
    history_before = db_path.read_bytes()
    before = tree(tmp_path)

    assert main(["restore", str(missing)]) == 2

    assert_one_error_line(capsys.readouterr(), str(missing))
    assert db_path.read_bytes() == history_before
    assert tree(tmp_path) == before


def test_restore_of_a_garbage_backup_fails(tmp_path, monkeypatch, capsys):
    db_path = make_history(tmp_path / "data" / "history.db")
    monkeypatch.setenv("CHECKER_DB", str(db_path))
    garbage = tmp_path / "garbage.bak"
    garbage.write_bytes(b"this is not a database, just text " * 200)
    history_before = db_path.read_bytes()
    before = tree(tmp_path)

    assert main(["restore", str(garbage)]) == 2

    assert_one_error_line(capsys.readouterr(), str(garbage))
    assert db_path.read_bytes() == history_before
    assert tree(tmp_path) == before


@pytest.mark.parametrize("command", ["backup", "restore"])
def test_missing_argument_is_a_usage_error(tmp_path, monkeypatch, capsys, command):
    db_path = make_history(tmp_path / "data" / "history.db")
    monkeypatch.setenv("CHECKER_DB", str(db_path))
    history_before = db_path.read_bytes()
    before = tree(tmp_path)

    assert main([command]) == 2

    assert_one_error_line(capsys.readouterr())
    assert db_path.read_bytes() == history_before
    assert tree(tmp_path) == before
