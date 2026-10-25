"""Rules that check course content text and return findings."""

import re
from dataclasses import dataclass

EM_DASH = "\u2014"

HEADING = re.compile(r"^#{1,6}\s+(.*)$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
SEPARATOR = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$")
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


@dataclass(frozen=True)
class Finding:
    """One problem found in a text. The runner adds the file path."""

    line: int
    rule: str
    severity: str
    message: str


class Rule:
    """Base class for rules. Subclasses set name and implement check."""

    name = ""

    def check(self, text, file_kind):
        """Return a list of findings for the text."""
        raise NotImplementedError


def _fenced_lines(lines):
    """Return the 1-based numbers of lines inside or on a fenced code block."""
    fenced = set()
    inside = False
    for number, line in enumerate(lines, start=1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced.add(number)
            inside = not inside
        elif inside:
            fenced.add(number)
    return fenced


def _cell_count(row):
    """Count the cells in a table row, ignoring the outer pipes."""
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    return len(UNESCAPED_PIPE.split(row))


def _find_tables(lines):
    """Return tables outside code fences as (start, header, body) tuples.

    start is the 1-based line of the header row, header is its text, and
    body is a list of (line number, text) for each body row.
    """
    fenced = _fenced_lines(lines)
    tables = []
    index = 0
    while index < len(lines) - 1:
        header = lines[index]
        separator = lines[index + 1]
        is_table = (
            index + 1 not in fenced
            and index + 2 not in fenced
            and "|" in header
            and "|" in separator
            and SEPARATOR.match(separator)
        )
        if not is_table:
            index += 1
            continue
        body = []
        row = index + 2
        while row < len(lines) and lines[row].strip() and "|" in lines[row]:
            if row + 1 in fenced:
                break
            body.append((row + 1, lines[row]))
            row += 1
        tables.append((index + 1, header, body))
        index = row
    return tables


class EmDashRule(Rule):
    """Flags every em dash character, including inside code blocks."""

    name = "em_dash"

    def check(self, text, file_kind):
        """Return one finding per em dash, on the line where it appears."""
        findings = []
        for number, line in enumerate(text.splitlines(), start=1):
            for _ in range(line.count(EM_DASH)):
                findings.append(
                    Finding(number, self.name, "error", "Em dash found. Use a comma or a period.")
                )
        return findings


class TablePipeRule(Rule):
    """Flags table rows with more cells than the header or an escaped pipe."""

    name = "table_pipe"

    def check(self, text, file_kind):
        """Return one finding per offending table body row."""
        findings = []
        for _, header, body in _find_tables(text.splitlines()):
            expected = _cell_count(header)
            for number, row in body:
                if "\\|" in row:
                    message = "Table row has an escaped pipe in a cell."
                elif _cell_count(row) > expected:
                    message = (
                        f"Table row has {_cell_count(row)} cells but the header has {expected}."
                    )
                else:
                    continue
                findings.append(Finding(number, self.name, "error", message))
        return findings


class MissingSectionRule(Rule):
    """Flags required headings that are absent from the text."""

    name = "missing_section"

    def __init__(self, required_sections):
        """Take a dict with the keys article and lab, each a list of names."""
        self.required_sections = required_sections

    def check(self, text, file_kind):
        """Return one finding on line 1 for each missing required section."""
        present = set()
        for line in text.splitlines():
            match = HEADING.match(line)
            if match:
                present.add(match.group(1).strip().lower())
        findings = []
        for section in self.required_sections.get(file_kind, []):
            if section.strip().lower() not in present:
                findings.append(
                    Finding(1, self.name, "error", f"Missing required section: {section}")
                )
        return findings


class TableLeadInRule(Rule):
    """Flags tables that do not follow a lead-in sentence."""

    name = "table_lead_in"

    def check(self, text, file_kind):
        """Return one finding on the first line of each table without a lead-in."""
        lines = text.splitlines()
        tables = _find_tables(lines)
        table_lines = set()
        for start, _, body in tables:
            table_lines.update(range(start, start + 2))
            table_lines.update(number for number, _ in body)
        findings = []
        for start, _, _ in tables:
            previous = start - 1
            while previous >= 1 and not lines[previous - 1].strip():
                previous -= 1
            if previous < 1:
                reason = "the start of the file"
            elif previous in table_lines:
                reason = "another table"
            elif HEADING.match(lines[previous - 1]):
                reason = "a heading"
            elif LIST_ITEM.match(lines[previous - 1]):
                reason = "a list item"
            else:
                continue
            message = f"Table follows {reason}. Add a lead-in sentence."
            findings.append(Finding(start, self.name, "error", message))
        return findings


RULE_REGISTRY = {
    EmDashRule.name: EmDashRule,
    TablePipeRule.name: TablePipeRule,
    MissingSectionRule.name: MissingSectionRule,
    TableLeadInRule.name: TableLeadInRule,
}
