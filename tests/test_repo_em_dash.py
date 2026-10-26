import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIPPED_FOLDERS = {".git", ".venv", ".pytest_cache", ".ruff_cache", "__pycache__"}
EM_DASH_BYTES = "\u2014".encode("utf-8")


def test_no_file_in_the_repository_contains_an_em_dash():
    offenders = []
    scanned = 0
    for folder, subfolders, names in os.walk(ROOT):
        subfolders[:] = [
            name
            for name in subfolders
            if name not in SKIPPED_FOLDERS and not name.endswith(".egg-info")
        ]
        for name in names:
            path = Path(folder) / name
            scanned += 1
            if EM_DASH_BYTES in path.read_bytes():
                offenders.append(str(path.relative_to(ROOT)))
    assert scanned >= 10, f"Only scanned {scanned} files"
    assert not offenders, "Em dash found in: " + ", ".join(sorted(offenders))
