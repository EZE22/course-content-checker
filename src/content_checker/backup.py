"""Backup and restore of the history database."""

import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

EXPECTED_USER_VERSION = 1
REQUIRED_TABLES = ("runs", "files", "findings")
BEFORE_RESTORE_SUFFIX = ".before-restore"


class BackupError(Exception):
    """A backup or restore failed. The message names the problem and the path."""


def _open_read_only(path):
    """Open a database read-only through a URI and switch foreign keys on."""
    uri = Path(path).absolute().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _make_temp_file(folder):
    """Create an empty temporary file in the folder and return its path."""
    handle, name = tempfile.mkstemp(dir=folder, prefix=".content-checker-", suffix=".tmp")
    os.close(handle)
    return name


def _copy_with_backup_api(source_path, target_path):
    """Copy a database into target_path with Connection.backup, source opened read-only."""
    with closing(_open_read_only(source_path)) as source:
        with closing(sqlite3.connect(target_path)) as target:
            target.execute("PRAGMA foreign_keys = ON")
            source.backup(target)


def _verify(path, label, full):
    """Check a database file. With full, also check user_version and the tables.

    The label is the path as the caller passed it, used in error messages.
    """
    with closing(_open_read_only(path)) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchall()
        if result != [("ok",)]:
            raise BackupError(f"Integrity check failed for {label}: {result!r}")
        if not full:
            return
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version != EXPECTED_USER_VERSION:
            raise BackupError(
                f"Unsupported database version in {label}: user_version is {version}, "
                f"expected {EXPECTED_USER_VERSION}"
            )
        names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        missing = [table for table in REQUIRED_TABLES if table not in names]
        if missing:
            raise BackupError(f"Missing tables in {label}: {', '.join(missing)}")


def _remove(path):
    """Remove a file, ignoring one that is already gone."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def backup_database(db_path, destination):
    """Copy the history database to destination and verify the copy.

    Raises BackupError if the source is not a file, the destination exists, or
    the copy fails verification. Nothing is created in those cases.
    """
    source = Path(db_path)
    target = Path(destination)
    if not source.is_file():
        raise BackupError(f"Cannot back up {db_path}: the history database does not exist")
    if target.exists():
        raise BackupError(f"Cannot back up to {destination}: the destination already exists")

    temp_name = None
    try:
        try:
            with closing(_open_read_only(db_path)) as source_connection:
                target.parent.mkdir(parents=True, exist_ok=True)
                temp_name = _make_temp_file(target.parent)
                with closing(sqlite3.connect(temp_name)) as temp_connection:
                    temp_connection.execute("PRAGMA foreign_keys = ON")
                    source_connection.backup(temp_connection)
            _verify(temp_name, destination, full=False)
            if target.exists():
                raise BackupError(
                    f"Cannot back up to {destination}: the destination already exists"
                )
            os.replace(temp_name, target)
        finally:
            if temp_name is not None:
                _remove(temp_name)
    except (sqlite3.Error, OSError) as error:
        raise BackupError(f"Could not back up {db_path} to {destination}: {error}") from error


def restore_database(backup_path, db_path):
    """Replace the history database with a verified backup.

    An existing history is first copied aside with the suffix .before-restore.
    Raises BackupError on any failure, leaving the history as it was.
    """
    backup = Path(backup_path)
    history = Path(db_path)
    aside = history.with_name(history.name + BEFORE_RESTORE_SUFFIX)

    temp_name = None
    aside_made = False
    replaced = False
    try:
        try:
            if not backup.is_file():
                raise BackupError(f"Cannot restore {backup_path}: the backup file does not exist")
            _verify(backup_path, backup_path, full=True)
            if aside.exists():
                raise BackupError(
                    f"Cannot restore {backup_path}: {aside} already exists, "
                    "move it away first"
                )
            history.parent.mkdir(parents=True, exist_ok=True)
            temp_name = _make_temp_file(history.parent)
            _copy_with_backup_api(backup_path, temp_name)
            _verify(temp_name, backup_path, full=True)
            if history.exists():
                aside_made = True
                shutil.copyfile(history, aside)
            os.replace(temp_name, history)
            replaced = True
        finally:
            if temp_name is not None:
                _remove(temp_name)
            if aside_made and not replaced:
                _remove(aside)
    except (sqlite3.Error, OSError) as error:
        raise BackupError(f"Could not restore {backup_path} to {db_path}: {error}") from error
