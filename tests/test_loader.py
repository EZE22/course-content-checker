import os
import stat

import pytest
from content_checker.loader import SourceFile, collect_files, detect_kind

# Case 1: the name test.


@pytest.mark.parametrize(
    "file_name",
    ["lab-03-inventory.md", "lab01.md", "intro-lab-2.md", "intro_lab_2.md", "LAB-1.md"],
)
def test_lab_names_are_labs(file_name):
    assert detect_kind(file_name, "# Plain heading\n") == "lab"


def test_name_with_lab_inside_a_word_is_an_article():
    assert detect_kind("elaborate-intro.md", "# Welcome\n") == "article"


# Case 2: the heading test.


@pytest.mark.parametrize("heading", ["# Lab 3: Inventory", "# Lab: Inventory", "# lab 3", "# Lab3"])
def test_lab_headings_make_a_lab(heading):
    assert detect_kind("notes.md", f"{heading}\n\nBody text.\n") == "lab"


def test_heading_with_lab_inside_a_longer_word_is_an_article():
    assert detect_kind("notes.md", "# Labrador facts\n") == "article"


# Case 3: only the first heading counts.


def test_later_lab_heading_does_not_make_a_lab():
    text = "# Intro\n\nSome text.\n\n## Lab 2\n\nMore text.\n"
    assert detect_kind("notes.md", text) == "article"


# Case 4: fenced code blocks are ignored.


def test_lab_heading_inside_a_fenced_block_is_ignored():
    text = "Some text.\n\n```\n# Lab 1\n```\n\nMore text.\n"
    assert detect_kind("notes.md", text) == "article"


# Case 5: the name test wins.


def test_name_match_wins_over_an_article_heading():
    assert detect_kind("lab-03-inventory.md", "# Inventory overview\n") == "lab"


# Case 6: nested folders, forward slash paths, sorted.


def test_collect_files_returns_nested_md_files_sorted(tmp_path):
    (tmp_path / "b" / "deep").mkdir(parents=True)
    (tmp_path / "a").mkdir()
    (tmp_path / "b" / "deep" / "z.md").write_text("# Z\n", encoding="utf-8")
    (tmp_path / "b" / "m.md").write_text("# M\n", encoding="utf-8")
    (tmp_path / "a" / "x.md").write_text("# X\n", encoding="utf-8")
    (tmp_path / "top.md").write_text("# Top\n", encoding="utf-8")

    files = collect_files(tmp_path)

    assert [f.path for f in files] == ["a/x.md", "b/deep/z.md", "b/m.md", "top.md"]


# Case 7: other file types are skipped with no entry.


def test_collect_files_skips_non_md_files(tmp_path):
    (tmp_path / "notes.txt").write_text("text", encoding="utf-8")
    (tmp_path / "data.json").write_text("{}", encoding="utf-8")
    (tmp_path / "README").write_text("readme", encoding="utf-8")
    (tmp_path / "keep.md").write_text("# Keep\n", encoding="utf-8")

    files = collect_files(tmp_path)

    assert [f.path for f in files] == ["keep.md"]


# Case 8: an empty folder.


def test_collect_files_on_an_empty_folder_returns_an_empty_list(tmp_path):
    assert collect_files(tmp_path) == []


# Case 9: invalid UTF-8.


def test_invalid_utf8_file_is_unreadable_and_others_still_load(tmp_path):
    (tmp_path / "bad.md").write_bytes(b"# Bad\n\xff\xfe\x80 broken\n")
    (tmp_path / "good.md").write_text("# Good\n", encoding="utf-8")

    files = collect_files(tmp_path)

    assert [f.path for f in files] == ["bad.md", "good.md"]
    bad, good = files
    assert bad.kind == "unreadable"
    assert bad.text == ""
    assert "utf-8" in bad.reason.lower()
    assert good.kind == "article"
    assert good.text == "# Good\n"
    assert good.reason == ""


# Case 10: no read permission.


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read files with mode 0o000")
def test_file_without_read_permission_is_unreadable(tmp_path):
    locked = tmp_path / "locked.md"
    locked.write_text("# Locked\n", encoding="utf-8")
    (tmp_path / "open.md").write_text("# Open\n", encoding="utf-8")
    locked.chmod(0o000)
    try:
        files = collect_files(tmp_path)
    finally:
        locked.chmod(stat.S_IRUSR | stat.S_IWUSR)

    assert [f.path for f in files] == ["locked.md", "open.md"]
    locked_file, open_file = files
    assert locked_file.kind == "unreadable"
    assert locked_file.text == ""
    assert "permission" in locked_file.reason.lower()
    assert open_file.kind == "article"


# Case 11: readable files carry their text and kind.


def test_readable_files_carry_text_and_kind(tmp_path):
    lab_text = "# Lab 1: Setup\n\nDo the steps.\n"
    article_text = "# Overview\n\nSome words.\n"
    (tmp_path / "setup.md").write_text(lab_text, encoding="utf-8")
    (tmp_path / "guide.md").write_text(article_text, encoding="utf-8")

    files = collect_files(tmp_path)

    assert files == [
        SourceFile(path="guide.md", kind="article", text=article_text, reason=""),
        SourceFile(path="setup.md", kind="lab", text=lab_text, reason=""),
    ]
    assert files[0].kind == detect_kind("guide.md", article_text)
    assert files[1].kind == detect_kind("setup.md", lab_text)
