import json
import os
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

REQUIRED_SECTIONS = {
    "article": [
        "Common Mistakes",
        "Try It Yourself",
        "Why This Matters for an FDE",
        "Comprehension Check",
    ],
    "lab": ["Problem Statement", "Requirements", "Grading Rubric"],
}


def test_backup_and_restore_through_the_real_command(tmp_path):
    script = Path(sys.executable).parent / "content-checker"
    if not script.exists():
        pytest.fail(f"console script not found at {script}, install with pip install -e '.[dev]'")

    content = tmp_path / "content"
    content.mkdir()
    for fixture in FIXTURES.glob("*.md"):
        shutil.copy(fixture, content / fixture.name)
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "content_folder": "content",
                "rules": ["em_dash", "table_pipe", "missing_section", "table_lead_in"],
                "required_sections": REQUIRED_SECTIONS,
            }
        ),
        encoding="utf-8",
    )

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    db_path = tmp_path / "data" / "history.db"
    env = dict(os.environ)
    env["CHECKER_DB"] = str(db_path)

    def run_checker(*args):
        return subprocess.run(
            [str(script), *args],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=elsewhere,
            env=env,
        )

    def query(sql):
        with closing(sqlite3.connect(db_path)) as conn:
            return conn.execute(sql).fetchall()

    def count(table):
        return query(f"SELECT COUNT(*) FROM {table}")[0][0]

    for _ in range(3):
        assert run_checker("check", str(settings)).returncode == 1
    assert count("runs") == 3

    backup = tmp_path / "backups" / "history.bak"
    result = run_checker("backup", str(backup))
    assert result.returncode == 0
    assert result.stdout == f"Backup saved: {backup}\nIntegrity check: ok\n"
    assert result.stderr == ""

    db_path.unlink()
    assert not db_path.exists()

    result = run_checker("restore", str(backup))
    assert result.returncode == 0
    assert result.stdout == f"Restored: {db_path}\nIntegrity check: ok\n"
    assert result.stderr == ""

    assert db_path.exists()
    assert count("runs") == 3
    assert count("files") == 15
    assert count("findings") == 9
    assert query("PRAGMA integrity_check") == [("ok",)]

    assert run_checker("check", str(settings)).returncode == 1
    assert count("runs") == 4

    result = run_checker("--version")
    assert result.returncode == 0
    assert result.stdout.startswith("content-checker ")
