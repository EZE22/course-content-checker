import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from content_checker.cli import main
from content_checker.rules import RULE_REGISTRY, Finding, HeadingSkipRule

TESTS = Path(__file__).parent
FIXTURES = TESTS / "fixtures"
SKIP_FIXTURES = TESTS / "fixtures_heading_skip"
SKIP_FIXTURE = "article-heading-skip.md"

FOUR_RULES = ["em_dash", "table_pipe", "missing_section", "table_lead_in"]
FIVE_RULES = [*FOUR_RULES, "heading_skip"]

REQUIRED_SECTIONS = {
    "article": [
        "Common Mistakes",
        "Try It Yourself",
        "Why This Matters for an FDE",
        "Comprehension Check",
    ],
    "lab": ["Problem Statement", "Requirements", "Grading Rubric"],
}


def check(text, file_kind="article"):
    return HeadingSkipRule().check(text, file_kind)


def lines_of(findings):
    return [finding.line for finding in findings]


def skipped_heading_line():
    lines = (SKIP_FIXTURES / SKIP_FIXTURE).read_text(encoding="utf-8").splitlines()
    return lines.index("#### Skipped Heading") + 1


# 1. Clean fixtures


@pytest.mark.parametrize(
    ("name", "kind"), [("article-clean.md", "article"), ("lab-clean.md", "lab")]
)
def test_clean_fixtures_give_no_findings(name, kind):
    text = (FIXTURES / name).read_text(encoding="utf-8")
    assert check(text, kind) == []


# 2. New fixture


def test_new_fixture_gives_exactly_one_finding_on_the_skipped_heading():
    text = (SKIP_FIXTURES / SKIP_FIXTURE).read_text(encoding="utf-8")
    findings = check(text)
    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, Finding)
    assert finding.rule == "heading_skip"
    assert finding.severity == "error"
    assert finding.line == skipped_heading_line()
    assert "2" in finding.message
    assert "4" in finding.message


# 3. Basic skips


def test_h2_then_h4_is_flagged_on_the_h4_line():
    findings = check("## A\n\n#### B\n")
    assert lines_of(findings) == [3]
    assert findings[0].rule == "heading_skip"
    assert findings[0].severity == "error"


def test_h1_then_h3_is_flagged():
    assert lines_of(check("# A\n\n### B\n")) == [3]


def test_h1_then_h2_is_not_flagged():
    assert check("# A\n\n## B\n") == []


# 4. Going back up


def test_going_back_up_is_fine():
    assert check("### A\n\n# B\n") == []


# 5. First heading


def test_first_heading_is_never_flagged():
    assert check("### Title\n") == []


def test_first_heading_deep_then_skip_flags_only_the_second():
    assert lines_of(check("### A\n\n##### B\n")) == [3]


# 6. Compared with the heading directly before, even a flagged one


def test_flagged_heading_is_the_baseline_for_the_next():
    assert lines_of(check("# A\n#### B\n##### C\n")) == [2]


# 7. Several skips


def test_several_skips_give_one_finding_each_in_line_order():
    text = "# A\n### B\n\ntext\n\n## C\n#### D\n\n# E\n###### F\n"
    assert lines_of(check(text)) == [2, 7, 10]


# 8. Fenced code blocks


def test_backtick_fence_lines_are_not_headings():
    text = "## A\n\n```\n#### not a heading\n```\n\n### B\n"
    assert check(text) == []


def test_tilde_fence_lines_are_not_headings():
    text = "## A\n\n~~~\n#### not a heading\n~~~\n\n### B\n"
    assert check(text) == []


# 9. No space after the #


def test_hashtag_without_space_is_not_a_heading():
    assert check("## A\n\n#hashtag\n\n### B\n") == []
    assert check("# A\n\n####hashtag\n") == []


# 10. File kind makes no difference


def test_same_findings_for_article_and_lab():
    text = "# A\n### B\n## C\n#### D\n"
    assert check(text, "article") == check(text, "lab")
    assert lines_of(check(text, "lab")) == [2, 4]


# 11. Never raises


@pytest.mark.parametrize(
    "text", ["", "\n\n\n", "   \n\t\n", "just words\nmore words\n"]
)
def test_never_raises_and_returns_empty_list(text):
    assert check(text) == []


# 12. Registry


def test_registry_maps_heading_skip_to_the_class():
    assert RULE_REGISTRY["heading_skip"] is HeadingSkipRule
    assert HeadingSkipRule.name == "heading_skip"
    assert HeadingSkipRule().name == "heading_skip"


# 13 and 14. CLI


def write_settings(tmp_path, rules):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "content_folder": "content",
                "rules": rules,
                "required_sections": REQUIRED_SECTIONS,
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def content(tmp_path):
    folder = tmp_path / "content"
    folder.mkdir()
    shutil.copy(SKIP_FIXTURES / SKIP_FIXTURE, folder / SKIP_FIXTURE)
    shutil.copy(FIXTURES / "article-clean.md", folder / "article-clean.md")
    return folder


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "data" / "checker.db"
    monkeypatch.setenv("CHECKER_DB", str(path))
    return path


def test_cli_with_five_rules_reports_the_skip(
    tmp_path, content, db_path, capsys
):
    settings = write_settings(tmp_path, FIVE_RULES)
    assert main(["check", str(settings)]) == 1
    lines = capsys.readouterr().out.splitlines()
    prefix = f"{SKIP_FIXTURE}:{skipped_heading_line()} heading_skip error"
    assert any(line.startswith(prefix) for line in lines)
    assert lines[-1] == "Checked 2 files, 1 findings, 0 rejected."


def test_cli_with_four_rules_behaves_as_in_1_0_0(
    tmp_path, content, db_path, capsys
):
    settings = write_settings(tmp_path, FOUR_RULES)
    assert main(["check", str(settings)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == "Checked 2 files, 0 findings, 0 rejected."
    assert not any("heading_skip" in line for line in lines)


def test_cli_five_rule_run_saves_one_heading_skip_row(
    tmp_path, content, db_path, capsys
):
    settings = write_settings(tmp_path, FIVE_RULES)
    assert main(["check", str(settings)]) == 1
    capsys.readouterr()
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute("SELECT rule, line FROM findings").fetchall()
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert rows == [("heading_skip", skipped_heading_line())]
    assert version == 1
