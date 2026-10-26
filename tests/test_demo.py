import re
from pathlib import Path

from content_checker.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"
SETTINGS = EXAMPLES / "settings.json"

FINDING_LINE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+) (?P<rule>\w+) (?P<severity>\w+) (?P<message>.*)$"
)

EXPECTED = {
    ("article-03-functions.md", "missing_section"),
    ("article-04-files.md", "table_lead_in"),
    ("article-05-errors.md", "table_pipe"),
    ("article-06-modules.md", "heading_skip"),
    ("article-07-testing.md", "missing_section"),
    ("article-07-testing.md", "table_lead_in"),
    ("lab-02-inventory.md", "missing_section"),
}


def run_demo(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CHECKER_DB", str(tmp_path / "demo.db"))
    code = main(["check", str(SETTINGS)])
    captured = capsys.readouterr()
    return code, captured


def finding_matches(stdout):
    lines = stdout.strip().splitlines()[:-1]
    return [FINDING_LINE.match(line) for line in lines if line.strip()]


def test_demo_gives_the_planted_findings(tmp_path, monkeypatch, capsys):
    code, captured = run_demo(tmp_path, monkeypatch, capsys)

    assert code == 1
    assert captured.err == ""
    assert captured.out.strip().splitlines()[-1] == "Checked 9 files, 7 findings, 0 rejected."

    matches = finding_matches(captured.out)
    assert all(matches)
    pairs = {(m["path"], m["rule"]) for m in matches}
    assert pairs == EXPECTED
    assert len(matches) == 7

    for match in matches:
        assert not match["path"].startswith(("article-01-", "article-02-", "lab-01-"))

    comprehension = [
        m
        for m in matches
        if m["path"] == "article-03-functions.md" and m["rule"] == "missing_section"
    ]
    assert len(comprehension) == 1
    assert "Comprehension Check" in comprehension[0]["message"]


def test_no_example_file_contains_an_em_dash():
    files = [path for path in EXAMPLES.rglob("*") if path.is_file()]
    assert files
    for path in files:
        assert "\u2014" not in path.read_text(encoding="utf-8"), path
