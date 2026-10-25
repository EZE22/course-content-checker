"""Walk the content folder, read Markdown files, and decide article or lab."""

import re
from dataclasses import dataclass
from pathlib import Path

HEADING_PATTERN = re.compile(r"^#+ ")
LAB_HEADING_PATTERN = re.compile(r"lab[ :0-9]", re.IGNORECASE)
FENCE_MARKERS = ("```", "~~~")


@dataclass(frozen=True)
class SourceFile:
    """One file from the content folder.

    path is relative to the content folder with forward slashes. kind is article,
    lab, or unreadable. reason is empty unless the file was unreadable.
    """

    path: str
    kind: str
    text: str
    reason: str


def _first_heading(text):
    """Return the first heading line outside fenced code blocks, or None."""
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(FENCE_MARKERS):
            in_fence = not in_fence
        elif not in_fence and HEADING_PATTERN.match(line):
            return line
    return None


def detect_kind(file_name, text):
    """Return "lab" if the file name or first heading says so, otherwise "article"."""
    name = file_name.lower()
    if name.startswith("lab") or "lab-" in name or "lab_" in name:
        return "lab"

    heading = _first_heading(text)
    if heading is not None:
        title = heading.lstrip("#")[1:]
        if LAB_HEADING_PATTERN.match(title):
            return "lab"
    return "article"


def collect_files(content_folder):
    """Return a SourceFile for every .md file under content_folder, sorted by path.

    Other file types are skipped. A file that cannot be read is kept with kind
    unreadable, empty text, and a reason naming the cause. This function only reads.
    """
    root = Path(content_folder)
    files = []
    for file_path in root.rglob("*"):
        if file_path.suffix != ".md" or not file_path.is_file():
            continue
        relative = file_path.relative_to(root).as_posix()
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            files.append(SourceFile(relative, "unreadable", "", f"Not valid UTF-8: {error}"))
        except OSError as error:
            files.append(SourceFile(relative, "unreadable", "", f"Cannot read file: {error}"))
        else:
            files.append(SourceFile(relative, detect_kind(file_path.name, text), text, ""))
    return sorted(files, key=lambda source: source.path)
