import sqlite3
from contextlib import closing

import pytest

from content_checker.backup import BackupError, backup_database, restore_database
from content_checker.loader import SourceFile
from content_checker.rules import Finding
from content_checker.storage import connect, save_run

TABLES = ("runs", "files", "findings")


def make_history(path, runs=2):
    """Build a populated history database, each run with two files and two findings."""
    for number in range(runs):
        source_files = [
            SourceFile(path="a.md", kind="article", text="text", reason=""),
            SourceFile(path="lab-b.md", kind="lab", text="text", reason=""),
        ]
        findings = [
            ("a.md", Finding(line=1, rule="missing_section", severity="error", message="one")),
            ("lab-b.md", Finding(line=3, rule="table_pipe", severity="error", message="two")),
        ]
        with closing(connect(path)) as connection:
            save_run(connection, "/content", f"1.0.{number}", source_files, findings)
    return path


def all_rows(path):
    with closing(sqlite3.connect(path)) as connection:
        return {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            for table in TABLES
        }


def count_runs(path):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]


def pragma(path, name):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(f"PRAGMA {name}").fetchone()[0]


def listing(folder):
    return sorted(item.name for item in folder.iterdir())


def zero_page(path, page_number=2):
    page_size = pragma(path, "page_size")
    data = bytearray(path.read_bytes())
    start = page_size * (page_number - 1)
    data[start : start + page_size] = bytes(page_size)
    path.write_bytes(bytes(data))


def before_restore(db_path):
    return db_path.with_name(db_path.name + ".before-restore")


# backup_database


def test_backup_copies_every_row_and_passes_integrity_check(tmp_path):
    source = make_history(tmp_path / "history.db", runs=2)
    destination = tmp_path / "copy.bak"

    assert backup_database(source, destination) is None

    assert all_rows(destination) == all_rows(source)
    assert len(all_rows(destination)["runs"]) == 2
    assert len(all_rows(destination)["files"]) == 4
    assert len(all_rows(destination)["findings"]) == 4
    assert pragma(destination, "user_version") == 1
    assert pragma(destination, "integrity_check") == "ok"


def test_backup_creates_missing_parent_folder(tmp_path):
    source = make_history(tmp_path / "history.db")
    destination = tmp_path / "deep" / "er" / "copy.bak"

    backup_database(str(source), str(destination))

    assert destination.is_file()


def test_backup_refuses_an_existing_destination(tmp_path):
    source = make_history(tmp_path / "history.db")
    destination = tmp_path / "copy.bak"
    destination.write_bytes(b"do not touch")

    with pytest.raises(BackupError) as error:
        backup_database(source, destination)

    assert str(destination) in str(error.value)
    assert destination.read_bytes() == b"do not touch"


def test_backup_of_a_missing_source_creates_nothing(tmp_path):
    source = tmp_path / "missing" / "history.db"
    out = tmp_path / "out"
    out.mkdir()
    destination = out / "copy.bak"

    with pytest.raises(BackupError) as error:
        backup_database(source, destination)

    assert str(source) in str(error.value)
    assert not source.exists()
    assert not source.parent.exists()
    assert not destination.exists()
    assert listing(out) == []


def test_backup_leaves_the_source_byte_for_byte_identical(tmp_path):
    source = make_history(tmp_path / "history.db")
    before = source.read_bytes()
    folder_before = listing(tmp_path)

    backup_database(source, tmp_path / "backups" / "copy.bak")

    assert source.read_bytes() == before
    assert listing(tmp_path) == sorted([*folder_before, "backups"])


def test_backup_of_a_file_that_is_not_a_database(tmp_path):
    source = tmp_path / "history.db"
    source.write_bytes(b"this is not a database, just text " * 200)
    before = source.read_bytes()
    out = tmp_path / "out"
    out.mkdir()
    destination = out / "copy.bak"

    with pytest.raises(BackupError) as error:
        backup_database(source, destination)

    assert str(source) in str(error.value)
    assert not destination.exists()
    assert listing(out) == []
    assert source.read_bytes() == before


def test_backup_of_a_database_with_a_zeroed_page(tmp_path):
    source = make_history(tmp_path / "history.db", runs=3)
    zero_page(source, page_number=2)
    before = source.read_bytes()
    out = tmp_path / "out"
    out.mkdir()
    folder_before = listing(tmp_path)
    destination = out / "copy.bak"

    with pytest.raises(BackupError) as error:
        backup_database(source, destination)

    message = str(error.value)
    assert str(source) in message
    assert "malformed" in message.lower()
    assert not destination.exists()
    assert listing(out) == []
    assert source.read_bytes() == before
    assert listing(tmp_path) == folder_before


# restore_database


def test_restore_replaces_the_history_with_the_backup(tmp_path):
    backup = make_history(tmp_path / "backups" / "history.bak", runs=3)
    db_path = make_history(tmp_path / "data" / "history.db", runs=1)
    assert count_runs(db_path) == 1

    assert restore_database(backup, db_path) is None

    assert count_runs(db_path) == 3
    assert all_rows(db_path) == all_rows(backup)


def test_restore_creates_the_history_and_its_parent_when_missing(tmp_path):
    backup = make_history(tmp_path / "history.bak", runs=2)
    db_path = tmp_path / "new" / "data" / "history.db"

    restore_database(str(backup), str(db_path))

    assert db_path.is_file()
    assert all_rows(db_path) == all_rows(backup)
    assert not before_restore(db_path).exists()
    assert listing(db_path.parent) == ["history.db"]


def test_restore_copies_an_existing_history_aside(tmp_path):
    backup = make_history(tmp_path / "history.bak", runs=3)
    db_path = make_history(tmp_path / "data" / "history.db", runs=1)
    old_bytes = db_path.read_bytes()

    restore_database(backup, db_path)

    assert before_restore(db_path).read_bytes() == old_bytes


def test_restore_refuses_when_a_before_restore_file_exists(tmp_path):
    backup = make_history(tmp_path / "history.bak", runs=3)
    db_path = make_history(tmp_path / "data" / "history.db", runs=1)
    safety = before_restore(db_path)
    safety.write_bytes(b"earlier safety copy")
    history_before = db_path.read_bytes()
    folder_before = listing(db_path.parent)

    with pytest.raises(BackupError) as error:
        restore_database(backup, db_path)

    assert str(safety) in str(error.value)
    assert db_path.read_bytes() == history_before
    assert safety.read_bytes() == b"earlier safety copy"
    assert listing(db_path.parent) == folder_before


def bad_missing_file(tmp_path):
    return tmp_path / "bad" / "missing.bak"


def bad_not_a_database(tmp_path):
    path = tmp_path / "bad" / "garbage.bak"
    path.parent.mkdir()
    path.write_bytes(b"this is not a database, just text " * 200)
    return path


def bad_user_version_2(tmp_path):
    path = make_history(tmp_path / "bad" / "version2.bak")
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA user_version = 2")
    return path


def bad_missing_findings_table(tmp_path):
    path = make_history(tmp_path / "bad" / "nofindings.bak")
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("DROP TABLE findings")
    return path


def bad_zeroed_page(tmp_path):
    path = make_history(tmp_path / "bad" / "zeroed.bak", runs=3)
    zero_page(path, page_number=2)
    return path


@pytest.mark.parametrize(
    "make_bad",
    [
        bad_missing_file,
        bad_not_a_database,
        bad_user_version_2,
        bad_missing_findings_table,
        bad_zeroed_page,
    ],
)
def test_restore_rejects_an_invalid_backup_and_changes_nothing(tmp_path, make_bad):
    bad = make_bad(tmp_path)
    db_path = make_history(tmp_path / "data" / "history.db", runs=1)
    history_before = db_path.read_bytes()
    folder_before = listing(db_path.parent)

    with pytest.raises(BackupError) as error:
        restore_database(bad, db_path)

    message = str(error.value)
    assert str(bad) in message
    if make_bad is bad_zeroed_page:
        assert "malformed" in message.lower()
    assert db_path.read_bytes() == history_before
    assert listing(db_path.parent) == folder_before


def test_restore_leaves_the_backup_byte_for_byte_identical(tmp_path):
    backup = make_history(tmp_path / "history.bak", runs=3)
    db_path = make_history(tmp_path / "data" / "history.db", runs=1)
    backup_bytes = backup.read_bytes()

    restore_database(backup, db_path)

    assert backup.read_bytes() == backup_bytes


def test_restore_leaves_only_the_database_and_the_safety_copy(tmp_path):
    backup = make_history(tmp_path / "history.bak", runs=3)
    db_path = make_history(tmp_path / "data" / "history.db", runs=1)

    restore_database(backup, db_path)

    assert listing(db_path.parent) == ["history.db", "history.db.before-restore"]


def test_restored_database_accepts_a_new_run(tmp_path):
    backup = make_history(tmp_path / "history.bak", runs=3)
    db_path = tmp_path / "data" / "history.db"
    restore_database(backup, db_path)
    source_files = [SourceFile(path="c.md", kind="article", text="text", reason="")]

    with closing(connect(db_path)) as connection:
        save_run(connection, "/content", "1.0.0", source_files, [])

    assert count_runs(db_path) == 4
    assert pragma(db_path, "integrity_check") == "ok"


def test_backup_then_restore_gives_identical_rows(tmp_path):
    source = make_history(tmp_path / "source" / "history.db", runs=3)
    backup = tmp_path / "backups" / "history.bak"
    restored = tmp_path / "restored" / "history.db"

    backup_database(source, backup)
    restore_database(backup, restored)

    assert all_rows(restored) == all_rows(source)
    assert pragma(restored, "user_version") == 1
    assert pragma(restored, "integrity_check") == "ok"
