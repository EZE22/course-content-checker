"""Format the report printed by the check command."""

from content_checker.runner import UNREADABLE


def format_report(source_files, findings):
    """Return the report as one string ending in a newline.

    Findings are sorted by path, then line, then rule. Rejected files follow under
    "Rejected files:" when there are any. The summary line is always last.
    """
    lines = []
    ordered = sorted(findings, key=lambda pair: (pair[0], pair[1].line, pair[1].rule))
    for path, finding in ordered:
        lines.append(f"{path}:{finding.line} {finding.rule} {finding.severity} {finding.message}")

    rejected = sorted(
        (source for source in source_files if source.kind == UNREADABLE),
        key=lambda source: source.path,
    )
    if rejected:
        lines.append("Rejected files:")
        lines.extend(f"{source.path}: {source.reason}" for source in rejected)

    lines.append(
        f"Checked {len(source_files)} files, {len(ordered)} findings, {len(rejected)} rejected."
    )
    return "\n".join(lines) + "\n"
