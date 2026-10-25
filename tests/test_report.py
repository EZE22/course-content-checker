from content_checker.loader import SourceFile
from content_checker.report import format_report
from content_checker.rules import Finding

EM_DASH = "\u2014"


def readable(path, kind="article"):
    return SourceFile(path, kind, "text", "")


def rejected(path, reason):
    return SourceFile(path, "unreadable", "", reason)


def finding(line, rule="em_dash", message="Em dash found."):
    return Finding(line, rule, "error", message)


def test_finding_line_has_exactly_the_planned_format():
    report = format_report(
        [readable("a.md")], [("a.md", finding(7, "table_pipe", "Table row is too wide."))]
    )

    assert report.splitlines()[0] == "a.md:7 table_pipe error Table row is too wide."


def test_findings_are_sorted_by_path_then_line_then_rule_regardless_of_input_order():
    findings = [
        ("b.md", finding(1, "em_dash")),
        ("a.md", finding(10, "em_dash")),
        ("a.md", finding(2, "table_pipe")),
        ("a.md", finding(2, "em_dash")),
    ]

    report = format_report([readable("a.md"), readable("b.md")], findings)

    lines = report.splitlines()
    assert [line.split(" ")[0] for line in lines[:4]] == ["a.md:2", "a.md:2", "a.md:10", "b.md:1"]
    assert [line.split(" ")[1] for line in lines[:2]] == ["em_dash", "table_pipe"]


def test_rejected_file_is_listed_after_findings_and_before_the_summary():
    files = [readable("a.md"), rejected("z.md", "Not valid UTF-8: bad"), rejected("b.md", "Denied")]

    report = format_report(files, [("a.md", finding(3))])

    assert report.splitlines() == [
        "a.md:3 em_dash error Em dash found.",
        "Rejected files:",
        "b.md: Denied",
        "z.md: Not valid UTF-8: bad",
        "Checked 3 files, 1 findings, 2 rejected.",
    ]


def test_rejected_block_with_no_findings_still_precedes_the_summary():
    report = format_report([rejected("b.md", "Denied")], [])

    assert report.splitlines() == [
        "Rejected files:",
        "b.md: Denied",
        "Checked 1 files, 0 findings, 1 rejected.",
    ]


def test_no_rejected_files_means_no_rejected_block():
    report = format_report([readable("a.md")], [("a.md", finding(1))])

    assert "Rejected files:" not in report


def test_summary_is_last_line_on_a_clean_run():
    report = format_report([readable("a.md"), readable("lab-1.md", "lab")], [])

    assert report.splitlines() == ["Checked 2 files, 0 findings, 0 rejected."]


def test_summary_counts_include_rejected_files_and_stay_plural():
    files = [readable("a.md"), readable("b.md"), rejected("c.md", "Denied")]
    findings = [("a.md", finding(1)), ("b.md", finding(2))]

    report = format_report(files, findings)

    assert report.splitlines()[-1] == "Checked 3 files, 2 findings, 1 rejected."


def test_summary_keeps_plural_words_for_one_of_everything():
    report = format_report([rejected("c.md", "Denied")], [])

    assert report.splitlines()[-1] == "Checked 1 files, 0 findings, 1 rejected."


def test_report_ends_with_one_newline():
    report = format_report([readable("a.md")], [("a.md", finding(1))])

    assert report.endswith("\n")
    assert not report.endswith("\n\n")


def test_report_contains_no_em_dash():
    files = [readable("a.md"), rejected("b.md", "Not valid UTF-8: bad")]

    report = format_report(files, [("a.md", finding(1))])

    assert EM_DASH not in report
