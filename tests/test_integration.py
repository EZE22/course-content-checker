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


def test_end_to_end_over_the_fixtures_folder(tmp_path):
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

    def run_checker(run_env):
        return subprocess.run(
            [str(script), "check", str(settings)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=elsewhere,
            env=run_env,
        )

    def query(sql):
        with closing(sqlite3.connect(db_path)) as conn:
            return conn.execute(sql).fetchall()

    def count(table):
        return query(f"SELECT COUNT(*) FROM {table}")[0][0]

    # Phase 1, violating run.
    result = run_checker(env)
    assert result.returncode == 1
    assert result.stderr == ""
    lines = result.stdout.splitlines()
    assert lines[0].startswith("article-missing-section.md:1 missing_section error")
    assert lines[1].startswith("article-no-lead-in.md:5 table_lead_in error")
    assert lines[2].startswith("article-table-pipe.md:9 table_pipe error")
    assert lines[-1] == "Checked 5 files, 3 findings, 0 rejected."
    assert "Rejected files:" not in result.stdout

    assert count("runs") == 1
    assert count("files") == 5
    assert count("findings") == 3
    assert query("PRAGMA user_version")[0][0] == 1
    saved = {path.name: path.read_bytes() for path in content.iterdir()}
    assert len(saved) == 5

    # Phase 2, history accumulates.
    result = run_checker(env)
    assert result.returncode == 1
    assert count("runs") == 2
    assert count("findings") == 6
    assert {path.name: path.read_bytes() for path in content.iterdir()} == saved

    # Phase 3, clean run.
    for name in ("article-missing-section.md", "article-no-lead-in.md", "article-table-pipe.md"):
        (content / name).unlink()
    result = run_checker(env)
    assert result.returncode == 0
    assert result.stdout == "Checked 2 files, 0 findings, 0 rejected.\n"
    assert count("runs") == 3
    assert query("SELECT finding_count FROM runs ORDER BY id DESC LIMIT 1")[0][0] == 0

    # Phase 4, missing database path.
    env.pop("CHECKER_DB")
    result = run_checker(env)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "CHECKER_DB" in result.stderr
    assert count("runs") == 3
