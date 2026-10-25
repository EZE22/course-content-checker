# Changelog

All notable changes to the Course Content Checker are recorded in this file, in the Keep a Changelog style.

## [1.0.0] - 2026-10-25

### Added

- The check command, which exits 0 when the content is clean, 1 when findings are reported, and 2 on an error.
- Four rules: em dash, pipe in a table cell, missing section, and table without lead-in.
- Article and lab detection, so each file is checked against the rules that apply to its kind.
- A settings file with clear error messages for a missing file, bad JSON, or invalid values.
- Run history saved to SQLite in one transaction, with the database path taken from CHECKER_DB.
- A report format that lists the findings for each file and summarizes the run.
- The backup and restore commands for the history database, and the --version flag.
- A Docker image with a read-only content mount and a named volume for history.
- A CI workflow with ruff, pytest, and docker-build jobs.
