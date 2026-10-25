import dataclasses
from pathlib import Path

import pytest
from content_checker.rules import (
    RULE_REGISTRY,
    EmDashRule,
    Finding,
    MissingSectionRule,
    Rule,
    TableLeadInRule,
    TablePipeRule,
)

FIXTURES = Path(__file__).parent / "fixtures"
EM_DASH = "\u2014"

REQUIRED_SECTIONS = {
    "article": [
        "Common Mistakes",
        "Try It Yourself",
        "Why This Matters for an FDE",
        "Comprehension Check",
    ],
    "lab": ["Problem Statement", "Requirements", "Grading Rubric"],
}

LAB_TEXT = (
    "# Lab 1\n\n## Problem Statement\n\n## Requirements\n\n## Grading Rubric\n"
)


def read_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def all_rules():
    return [
        EmDashRule(),
        TablePipeRule(),
        MissingSectionRule(REQUIRED_SECTIONS),
        TableLeadInRule(),
    ]


def rule_ids(rules):
    return [rule.name for rule in rules]


def assert_error_findings(findings, rule_name):
    for finding in findings:
        assert isinstance(finding, Finding)
        assert finding.rule == rule_name
        assert finding.severity == "error"
        assert isinstance(finding.message, str)
        assert finding.message.strip()


# 1. Clean files


@pytest.mark.parametrize("rule", all_rules(), ids=rule_ids(all_rules()))
def test_rule_is_silent_on_clean_article(rule):
    assert rule.check(read_fixture("article-clean.md"), "article") == []


@pytest.mark.parametrize(
    "rule",
    [EmDashRule(), TablePipeRule(), TableLeadInRule()],
    ids=["em_dash", "table_pipe", "table_lead_in"],
)
def test_rule_is_silent_on_clean_lab(rule):
    assert rule.check(read_fixture("lab-clean.md"), "lab") == []


def test_missing_section_is_silent_on_clean_lab():
    rule = MissingSectionRule(REQUIRED_SECTIONS)
    assert rule.check(read_fixture("lab-clean.md"), "lab") == []


# Finding shape


def test_finding_has_four_fields_and_no_file():
    finding = Finding(line=3, rule="em_dash", severity="error", message="m")
    names = [field.name for field in dataclasses.fields(Finding)]
    assert names == ["line", "rule", "severity", "message"]
    assert finding.line == 3
    assert not hasattr(finding, "file")


def test_finding_is_frozen():
    finding = Finding(line=3, rule="em_dash", severity="error", message="m")
    with pytest.raises(dataclasses.FrozenInstanceError):
        finding.line = 4


# 2. EmDashRule


def test_em_dash_one_finding_on_its_line():
    text = f"line one\nline two\nbad {EM_DASH} here\nline four\n"
    findings = EmDashRule().check(text, "article")
    assert len(findings) == 1
    assert findings[0].line == 3
    assert_error_findings(findings, "em_dash")


def test_em_dash_two_on_one_line_gives_two_findings():
    text = f"one\ntwo\na {EM_DASH} b {EM_DASH} c\n"
    findings = EmDashRule().check(text, "article")
    assert len(findings) == 2
    assert [f.line for f in findings] == [3, 3]
    assert_error_findings(findings, "em_dash")


def test_em_dash_inside_fenced_code_block_is_found():
    text = f"intro\n\n```\ncode {EM_DASH} here\n```\n"
    findings = EmDashRule().check(text, "article")
    assert len(findings) == 1
    assert findings[0].line == 4


def test_em_dash_ignores_en_dash_and_hyphen():
    text = "a - b\nc – d\n"
    assert EmDashRule().check(text, "article") == []


# 3. TablePipeRule


def test_table_pipe_fixture_gives_one_finding_on_offending_row():
    findings = TablePipeRule().check(read_fixture("article-table-pipe.md"), "article")
    assert len(findings) == 1
    assert findings[0].line == 9
    assert_error_findings(findings, "table_pipe")


def test_table_pipe_escaped_pipe_is_flagged():
    text = "Lead-in sentence.\n\n| A | B |\n| --- | --- |\n| x \\| y | z |\n"
    findings = TablePipeRule().check(text, "article")
    assert len(findings) == 1
    assert findings[0].line == 5
    assert_error_findings(findings, "table_pipe")


def test_table_pipe_one_finding_per_offending_row():
    text = (
        "Lead-in sentence.\n\n"
        "| A | B |\n| --- | --- |\n"
        "| 1 | 2 | 3 |\n"
        "| 4 | 5 |\n"
        "| 6 | 7 | 8 |\n"
    )
    findings = TablePipeRule().check(text, "article")
    assert [f.line for f in findings] == [5, 7]


def test_table_pipe_in_fenced_code_block_is_ignored():
    text = (
        "Lead-in sentence.\n\n"
        "```\n"
        "| A | B |\n| --- | --- |\n"
        "| 1 | 2 | 3 |\n"
        "```\n"
    )
    assert TablePipeRule().check(text, "article") == []


# 4. MissingSectionRule


def test_missing_section_fixture_names_comprehension_check():
    rule = MissingSectionRule(REQUIRED_SECTIONS)
    findings = rule.check(read_fixture("article-missing-section.md"), "article")
    assert len(findings) == 1
    assert findings[0].line == 1
    assert "Comprehension Check" in findings[0].message
    assert_error_findings(findings, "missing_section")


def test_missing_section_lab_uses_lab_list():
    text = "# Lab 1\n\n## Problem Statement\n\n## Requirements\n"
    rule = MissingSectionRule(REQUIRED_SECTIONS)
    findings = rule.check(text, "lab")
    assert len(findings) == 1
    assert findings[0].line == 1
    assert "Grading Rubric" in findings[0].message
    assert_error_findings(findings, "missing_section")


def test_missing_section_article_list_not_used_for_lab():
    rule = MissingSectionRule(REQUIRED_SECTIONS)
    assert rule.check(LAB_TEXT, "lab") == []
    findings = rule.check(LAB_TEXT, "article")
    assert len(findings) == 4


def test_missing_section_one_finding_per_missing_section():
    rule = MissingSectionRule(REQUIRED_SECTIONS)
    findings = rule.check("# Title\n", "lab")
    assert len(findings) == 3
    assert all(f.line == 1 for f in findings)
    messages = " ".join(f.message for f in findings)
    for name in REQUIRED_SECTIONS["lab"]:
        assert name in messages


def test_missing_section_ignores_case_and_surrounding_spaces():
    text = "#   problem statement   \n\n## REQUIREMENTS\n\n### Grading rubric  \n"
    rule = MissingSectionRule(REQUIRED_SECTIONS)
    assert rule.check(text, "lab") == []


def test_missing_section_bold_text_is_not_a_heading():
    text = "# Lab 1\n\n## Problem Statement\n\n## Requirements\n\n**Grading Rubric**\n"
    rule = MissingSectionRule(REQUIRED_SECTIONS)
    findings = rule.check(text, "lab")
    assert len(findings) == 1
    assert "Grading Rubric" in findings[0].message


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
def test_missing_section_heading_at_any_level_counts(level):
    marks = "#" * level
    text = f"{marks} Problem Statement\n\n{marks} Requirements\n\n{marks} Grading Rubric\n"
    rule = MissingSectionRule(REQUIRED_SECTIONS)
    assert rule.check(text, "lab") == []


# 5. TableLeadInRule


def test_lead_in_fixture_gives_one_finding_on_table_first_line():
    findings = TableLeadInRule().check(read_fixture("article-no-lead-in.md"), "article")
    assert len(findings) == 1
    assert findings[0].line == 5
    assert_error_findings(findings, "table_lead_in")


def test_lead_in_table_after_list_item_is_flagged():
    text = "- item one\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n"
    findings = TableLeadInRule().check(text, "article")
    assert len(findings) == 1
    assert findings[0].line == 3


def test_lead_in_table_after_another_table_is_flagged():
    text = (
        "Lead-in sentence.\n\n"
        "| A | B |\n| --- | --- |\n| 1 | 2 |\n\n"
        "| C | D |\n| --- | --- |\n| 3 | 4 |\n"
    )
    findings = TableLeadInRule().check(text, "article")
    assert len(findings) == 1
    assert findings[0].line == 7


def test_lead_in_table_at_start_of_file_is_flagged():
    text = "| A | B |\n| --- | --- |\n| 1 | 2 |\n"
    findings = TableLeadInRule().check(text, "article")
    assert len(findings) == 1
    assert findings[0].line == 1


def test_lead_in_table_after_sentence_is_not_flagged():
    text = "Here is the data.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n"
    assert TableLeadInRule().check(text, "article") == []


def test_lead_in_table_inside_fenced_code_block_is_ignored():
    text = "## Heading\n\n```\n| A | B |\n| --- | --- |\n| 1 | 2 |\n```\n"
    assert TableLeadInRule().check(text, "article") == []


# 6. Odd input


@pytest.mark.parametrize("rule", all_rules(), ids=rule_ids(all_rules()))
@pytest.mark.parametrize("kind", ["article", "lab"])
@pytest.mark.parametrize(
    "text",
    ["", "\n", "\n\n\n", "   \n \n", "\t\n"],
    ids=["empty", "newline", "blank-lines", "spaces", "tab"],
)
def test_rule_never_raises_on_blank_input(rule, kind, text):
    findings = rule.check(text, kind)
    assert isinstance(findings, list)


@pytest.mark.parametrize(
    "rule",
    [EmDashRule(), TablePipeRule(), TableLeadInRule()],
    ids=["em_dash", "table_pipe", "table_lead_in"],
)
@pytest.mark.parametrize("kind", ["article", "lab"])
def test_rules_return_empty_list_for_empty_string(rule, kind):
    assert rule.check("", kind) == []


@pytest.mark.parametrize(
    "rule",
    [EmDashRule(), TablePipeRule(), TableLeadInRule()],
    ids=["em_dash", "table_pipe", "table_lead_in"],
)
def test_rules_return_empty_list_for_text_with_no_tables(rule):
    text = "# Title\n\nJust a paragraph.\n\n- a list item\n"
    assert rule.check(text, "article") == []


@pytest.mark.parametrize("kind", ["article", "lab"])
def test_missing_section_on_empty_string_flags_every_section(kind):
    rule = MissingSectionRule(REQUIRED_SECTIONS)
    findings = rule.check("", kind)
    assert len(findings) == len(REQUIRED_SECTIONS[kind])
    assert all(f.line == 1 for f in findings)


def test_missing_section_with_no_required_sections_returns_empty_list():
    rule = MissingSectionRule({"article": [], "lab": []})
    assert rule.check("", "article") == []
    assert rule.check("", "lab") == []


@pytest.mark.parametrize("rule", all_rules(), ids=rule_ids(all_rules()))
def test_rule_never_raises_on_lone_table_pieces(rule):
    for text in ["|", "| a |", "| --- |", "```", "```\n", "#", "# ", "-", "- "]:
        assert isinstance(rule.check(text, "article"), list)


# 7. Base class and registry


def test_base_rule_check_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        Rule().check("text", "article")


def test_registry_has_exactly_the_four_rules():
    assert RULE_REGISTRY == {
        "em_dash": EmDashRule,
        "table_pipe": TablePipeRule,
        "missing_section": MissingSectionRule,
        "table_lead_in": TableLeadInRule,
    }


def test_every_registry_class_name_matches_its_key():
    for key, cls in RULE_REGISTRY.items():
        assert cls.name == key
        assert issubclass(cls, Rule)
