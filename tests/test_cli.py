import importlib.metadata
import json
import re
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from content_checker.cli import main

FIXTURES = Path(__file__).parent / "fixtures"

SETTINGS = {
    "content_folder": "content",
    "rules": ["em_dash", "table_pipe", "missing_section", "table_lead_in"],
    "required_sections": {
        "article": [
            "Common Mistakes",
            "Try It Yourself",
            "Why This Matters for an FDE",
            "Comprehension Check",
        ],
        "lab": ["Problem Statement", "Requirements", "Grading Rubric"],
    },
}

CLEAN_FILES = ["article-clean.md", "lab-clean.md"]


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "data" / "checker.db"
    monkeypatch.setenv("CHECKER_DB", str(path))
    return path


def write_settings(tmp_path, data=None):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(SETTINGS if data is None else data), encoding="utf-8")
    return path


def make_content(tmp_path, fixture_names=(), extra_text=None, extra_bytes=None):
    """Build tmp_path/content from fixtures plus files written at run time."""
    folder = tmp_path / "content"
    folder.mkdir(exist_ok=True)
    for name in fixture_names:
        shutil.copy(FIXTURES / name, folder / name)
    for name, text in (extra_text or {}).items():
        (folder / name).write_text(text, encoding="utf-8")
    for name, data in (extra_bytes or {}).items():
        (folder / name).write_bytes(data)
    return folder


def em_dash_article():
    clean = (FIXTURES / "article-clean.md").read_text(encoding="utf-8")
    return clean + "\nThis line has a dash \u2014 in it.\n"


def violating_content(tmp_path):
    """Three files: a missing section, an em dash, and a clean lab. Two findings."""
    return make_content(
        tmp_path,
        ["article-missing-section.md", "lab-clean.md"],
        extra_text={"article-em-dash.md": em_dash_article()},
    )


def run_check(tmp_path, capsys):
    code = main(["check", str(write_settings(tmp_path))])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def read_rows(db_path, sql):
    with closing(sqlite3.connect(db_path)) as connection:
        return connection.execute(sql).fetchall()


def snapshot(folder):
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in folder.rglob("*")
        if path.is_file()
    }


def test_clean_folder_exits_0_and_saves_a_run(tmp_path, db_path, capsys):
    make_content(tmp_path, CLEAN_FILES)

    code, out, err = run_check(tmp_path, capsys)

    assert code == 0
    assert out.splitlines()[-1] == "Checked 2 files, 0 findings, 0 rejected."
    assert err == ""
    assert read_rows(db_path, "SELECT COUNT(*) FROM runs") == [(1,)]


def test_violating_fixture_exits_1_and_lists_the_finding(tmp_path, db_path, capsys):
    make_content(tmp_path, ["article-clean.md", "article-table-pipe.md"])

    code, out, err = run_check(tmp_path, capsys)

    assert code == 1
    assert re.search(r"^article-table-pipe\.md:9 table_pipe error .+$", out, re.MULTILINE)
    assert out.splitlines()[-1] == "Checked 2 files, 1 findings, 0 rejected."
    assert err == ""


def test_invalid_utf8_file_is_rejected_and_other_files_are_still_checked(
    tmp_path, db_path, capsys
):
    make_content(
        tmp_path,
        ["article-clean.md", "article-missing-section.md"],
        extra_bytes={"broken.md": b"\xff\xfe not utf-8 \xff"},
    )

    code, out, err = run_check(tmp_path, capsys)

    lines = out.splitlines()
    assert code == 1
    assert "Rejected files:" in lines
    reason_line = next(line for line in lines if line.startswith("broken.md: "))
    assert "UTF-8" in reason_line
    missing_prefix = "article-missing-section.md:1 missing_section error"
    assert any(line.startswith(missing_prefix) for line in lines)
    assert lines[-1] == "Checked 3 files, 1 findings, 1 rejected."
    assert err == ""


def test_missing_settings_file_exits_2_and_creates_no_database(tmp_path, db_path, capsys):
    code = main(["check", str(tmp_path / "missing.json")])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("Error:")
    assert not db_path.exists()


def test_invalid_json_exits_2_and_creates_no_database(tmp_path, db_path, capsys):
    bad = tmp_path / "settings.json"
    bad.write_text("{ not json", encoding="utf-8")

    code = main(["check", str(bad)])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("Error:")
    assert not db_path.exists()


def test_unset_checker_db_exits_2_naming_it_and_creates_no_database(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("CHECKER_DB", raising=False)
    make_content(tmp_path, CLEAN_FILES)
    write_settings(tmp_path)
    before = {path for path in tmp_path.rglob("*")}

    code = main(["check", str(tmp_path / "settings.json")])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("Error:")
    assert "CHECKER_DB" in captured.err
    assert {path for path in tmp_path.rglob("*")} == before


def test_empty_checker_db_exits_2_naming_it_and_creates_no_database(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("CHECKER_DB", "")
    make_content(tmp_path, CLEAN_FILES)
    write_settings(tmp_path)
    before = {path for path in tmp_path.rglob("*")}

    code = main(["check", str(tmp_path / "settings.json")])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("Error:")
    assert "CHECKER_DB" in captured.err
    assert {path for path in tmp_path.rglob("*")} == before


def test_settings_message_wins_when_settings_and_checker_db_are_both_wrong(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("CHECKER_DB", raising=False)

    code = main(["check", str(tmp_path / "missing-settings.json")])

    captured = capsys.readouterr()
    assert code == 2
    assert "missing-settings.json" in captured.err
    assert "CHECKER_DB" not in captured.err


def test_settings_path_is_optional(tmp_path, db_path, monkeypatch, capsys):
    make_content(tmp_path, CLEAN_FILES)
    write_settings(tmp_path)
    monkeypatch.chdir(tmp_path)

    code = main(["check"])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.splitlines()[-1] == "Checked 2 files, 0 findings, 0 rejected."


def test_violating_run_is_saved_with_files_findings_and_version(tmp_path, db_path, capsys):
    violating_content(tmp_path)

    code, _, _ = run_check(tmp_path, capsys)

    assert code == 1
    assert read_rows(db_path, "SELECT COUNT(*) FROM runs") == [(1,)]
    assert read_rows(db_path, "SELECT COUNT(*) FROM files") == [(3,)]
    assert read_rows(db_path, "SELECT COUNT(*) FROM findings") == [(2,)]
    assert read_rows(db_path, "SELECT checker_version FROM runs") == [
        (importlib.metadata.version("course-content-checker"),)
    ]


def test_unusable_database_path_exits_2_but_still_prints_the_report(
    tmp_path, monkeypatch, capsys
):
    blocker = tmp_path / "blocker"
    blocker.write_text("a regular file, not a folder", encoding="utf-8")
    monkeypatch.setenv("CHECKER_DB", str(blocker / "checker.db"))
    violating_content(tmp_path)

    code, out, err = run_check(tmp_path, capsys)

    assert code == 2
    assert err.startswith("Error:")
    assert out.splitlines()[-1] == "Checked 3 files, 2 findings, 0 rejected."
    assert "em_dash error" in out


@pytest.mark.parametrize(
    "argv",
    [[], ["bogus"], ["--bogus"], ["check", "--bogus"]],
    ids=["missing-subcommand", "unknown-subcommand", "unknown-option", "unknown-check-option"],
)
def test_usage_errors_exit_2_with_one_error_line_on_stderr(argv, tmp_path, db_path, capsys):
    code = main(argv)

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert len(captured.err.strip().splitlines()) == 1


def test_content_folder_is_never_changed(tmp_path, db_path, capsys):
    folder = violating_content(tmp_path)
    make_content(
        tmp_path,
        extra_text={"notes.txt": "not markdown"},
        extra_bytes={"broken.md": b"\xff\xfe"},
    )
    before = snapshot(folder)

    run_check(tmp_path, capsys)

    assert snapshot(folder) == before
