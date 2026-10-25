from pathlib import Path

from content_checker.loader import SourceFile
from content_checker.rules import (
    EmDashRule,
    Finding,
    MissingSectionRule,
    Rule,
    TableLeadInRule,
    TablePipeRule,
)
from content_checker.runner import build_rules, run_rules
from content_checker.settings import Settings

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

ALL_RULE_NAMES = ["em_dash", "table_pipe", "missing_section", "table_lead_in"]

LAB_WITHOUT_RUBRIC = "# Lab 1\n\n## Problem Statement\n\n## Requirements\n"


class RecordingRule(Rule):
    """A rule that records every call and returns no findings."""

    name = "recording"

    def __init__(self):
        self.calls = []

    def check(self, text, file_kind):
        self.calls.append((text, file_kind))
        return []


class FixedRule(Rule):
    """A rule that returns one finding for each line number it was given."""

    def __init__(self, name, lines):
        self.name = name
        self.lines = lines

    def check(self, text, file_kind):
        return [Finding(line, self.name, "error", "message") for line in self.lines]


def make_settings(rules):
    return Settings(
        content_folder=Path("."),
        rules=rules,
        required_sections=REQUIRED_SECTIONS,
    )


def read_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def source(path, kind, text="", reason=""):
    return SourceFile(path, kind, text, reason)


def summary(pairs):
    return [(path, finding.line, finding.rule) for path, finding in pairs]


def test_build_rules_follows_settings_order():
    names = ["table_lead_in", "em_dash", "missing_section", "table_pipe"]

    rules = build_rules(make_settings(names))

    assert [type(rule) for rule in rules] == [
        TableLeadInRule,
        EmDashRule,
        MissingSectionRule,
        TablePipeRule,
    ]


def test_build_rules_gives_missing_section_rule_the_required_sections():
    rules = build_rules(make_settings(ALL_RULE_NAMES))

    missing_section = next(rule for rule in rules if isinstance(rule, MissingSectionRule))
    assert missing_section.required_sections == REQUIRED_SECTIONS


def test_build_rules_returns_only_the_listed_rules():
    rules = build_rules(make_settings(["em_dash"]))

    assert [type(rule) for rule in rules] == [EmDashRule]


def test_run_rules_passes_text_and_kind_for_article_and_lab():
    recorder = RecordingRule()
    files = [
        source("article.md", "article", "article text"),
        source("lab-1.md", "lab", "lab text"),
    ]

    run_rules(files, [recorder])

    assert recorder.calls == [("article text", "article"), ("lab text", "lab")]


def test_run_rules_flags_a_lab_missing_grading_rubric_using_the_lab_list():
    settings = make_settings(ALL_RULE_NAMES)
    files = [
        source("article-clean.md", "article", read_fixture("article-clean.md")),
        source("lab-1.md", "lab", LAB_WITHOUT_RUBRIC),
    ]

    results = run_rules(files, build_rules(settings))

    assert len(results) == 1
    path, finding = results[0]
    assert path == "lab-1.md"
    assert finding.rule == "missing_section"
    assert "Grading Rubric" in finding.message


def test_run_rules_ignores_unreadable_files_completely():
    recorder = RecordingRule()
    files = [
        source("broken.md", "unreadable", "", "Not valid UTF-8: bad byte"),
        source("article.md", "article", "text"),
    ]

    results = run_rules(files, [recorder, FixedRule("fixed", [1])])

    assert recorder.calls == [("text", "article")]
    assert [path for path, _ in results] == ["article.md"]


def test_run_rules_with_only_unreadable_files_returns_empty_list():
    recorder = RecordingRule()

    results = run_rules([source("broken.md", "unreadable", "", "reason")], [recorder])

    assert results == []
    assert recorder.calls == []


def test_run_rules_sorts_by_path_then_line_then_rule():
    files = [source("b.md", "article"), source("a.md", "article")]
    rules = [FixedRule("zeta", [10, 2]), FixedRule("alpha", [2])]

    results = run_rules(files, rules)

    assert summary(results) == [
        ("a.md", 2, "alpha"),
        ("a.md", 2, "zeta"),
        ("a.md", 10, "zeta"),
        ("b.md", 2, "alpha"),
        ("b.md", 2, "zeta"),
        ("b.md", 10, "zeta"),
    ]


def test_run_rules_returns_path_and_finding_pairs():
    results = run_rules([source("a.md", "article")], [FixedRule("alpha", [3])])

    assert results == [("a.md", Finding(3, "alpha", "error", "message"))]


def test_run_rules_on_clean_files_returns_empty_list():
    files = [
        source("article-clean.md", "article", read_fixture("article-clean.md")),
        source("lab-clean.md", "lab", read_fixture("lab-clean.md")),
    ]

    assert run_rules(files, build_rules(make_settings(ALL_RULE_NAMES))) == []
