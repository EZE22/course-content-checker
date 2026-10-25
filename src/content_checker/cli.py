"""Command line entry point for the content checker."""

import argparse
import importlib.metadata
import os
import sqlite3
import sys
from contextlib import closing

from content_checker.backup import BackupError, backup_database, restore_database
from content_checker.loader import collect_files
from content_checker.report import format_report
from content_checker.rules import RULE_REGISTRY
from content_checker.runner import build_rules, run_rules
from content_checker.settings import SettingsError, load_settings
from content_checker.storage import connect, save_run

DEFAULT_SETTINGS = "settings.json"
DB_ENV_VAR = "CHECKER_DB"
PACKAGE_NAME = "course-content-checker"


class _UsageError(Exception):
    """A usage or environment problem. Carries the message to print."""


class _Parser(argparse.ArgumentParser):
    """An argument parser that raises instead of printing usage and exiting."""

    def error(self, message):
        """Raise a _UsageError with the message."""
        raise _UsageError(message)


def _build_parser():
    parser = _Parser(prog="content-checker")
    parser.add_argument(
        "--version",
        action="version",
        version=f"content-checker {importlib.metadata.version(PACKAGE_NAME)}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    check = subparsers.add_parser("check", help="check the content folder")
    check.add_argument("settings_path", nargs="?", default=DEFAULT_SETTINGS)
    backup = subparsers.add_parser("backup", help="copy the history database to a new file")
    backup.add_argument("destination")
    restore = subparsers.add_parser("restore", help="replace the history database from a backup")
    restore.add_argument("backup_file")
    return parser


def _require_db_path():
    """Return the history database path from CHECKER_DB, or raise if unset or empty."""
    db_path = os.environ.get(DB_ENV_VAR)
    if not db_path:
        raise _UsageError(f"The environment variable {DB_ENV_VAR} is not set")
    return db_path


def _fail(message):
    """Print one Error line to stderr and return exit code 2."""
    print(f"Error: {message}", file=sys.stderr)
    return 2


def _check(settings_path):
    """Run the check command and return its exit code."""
    try:
        settings = load_settings(settings_path, set(RULE_REGISTRY))
    except SettingsError as error:
        return _fail(error)

    try:
        db_path = _require_db_path()
    except _UsageError as error:
        return _fail(error)

    source_files = collect_files(settings.content_folder)
    findings = run_rules(source_files, build_rules(settings))

    save_error = None
    try:
        version = importlib.metadata.version(PACKAGE_NAME)
        with closing(connect(db_path)) as connection:
            save_run(connection, settings.content_folder, version, source_files, findings)
    except (OSError, sqlite3.Error) as error:
        save_error = error

    print(format_report(source_files, findings), end="")

    if save_error is not None:
        return _fail(f"Could not save the run: {save_error}")
    if findings or any(source.kind == "unreadable" for source in source_files):
        return 1
    return 0


def _backup(destination):
    """Run the backup command and return its exit code."""
    try:
        db_path = _require_db_path()
        backup_database(db_path, destination)
    except (_UsageError, BackupError) as error:
        return _fail(error)
    print(f"Backup saved: {destination}")
    print("Integrity check: ok")
    return 0


def _restore(backup_file):
    """Run the restore command and return its exit code."""
    try:
        db_path = _require_db_path()
        restore_database(backup_file, db_path)
    except (_UsageError, BackupError) as error:
        return _fail(error)
    print(f"Restored: {db_path}")
    print("Integrity check: ok")
    return 0


def main(argv=None):
    """Run the command line and return the exit code. Never raises SystemExit."""
    try:
        args = _build_parser().parse_args(argv)
    except _UsageError as error:
        return _fail(error)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 0

    if args.command == "backup":
        return _backup(args.destination)
    if args.command == "restore":
        return _restore(args.backup_file)
    return _check(args.settings_path)
