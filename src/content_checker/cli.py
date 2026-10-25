"""Command line entry point for the content checker."""

import argparse
import importlib.metadata
import os
import sqlite3
import sys
from contextlib import closing

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
    """A usage problem found by argparse. Carries the message to print."""


class _Parser(argparse.ArgumentParser):
    """An argument parser that raises instead of printing usage and exiting."""

    def error(self, message):
        """Raise a _UsageError with the message."""
        raise _UsageError(message)


def _build_parser():
    parser = _Parser(prog="content-checker")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    check = subparsers.add_parser("check", help="check the content folder")
    check.add_argument("settings_path", nargs="?", default=DEFAULT_SETTINGS)
    return parser


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

    db_path = os.environ.get(DB_ENV_VAR)
    if not db_path:
        return _fail(f"The environment variable {DB_ENV_VAR} is not set")

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


def main(argv=None):
    """Run the command line and return the exit code. Never raises SystemExit."""
    try:
        args = _build_parser().parse_args(argv)
    except _UsageError as error:
        return _fail(error)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 0

    return _check(args.settings_path)
