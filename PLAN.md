# Course Content Checker Plan

This file records the decisions made before any code was written. Every prompt to Claude Code points back here. If a decision needs to change, update this file first, then change the code.

## Decisions

### Finding shape

A finding has five fields: file, line, rule, severity, message.

1. Line numbers are 1-based integers.
2. A finding about the whole file, such as a missing section, reports line 1.
3. Severity is always "error" in 1.0.0. The field exists so a later release can add "warning" without changing the shape.
4. Any finding makes the exit code 1.

### Settings file

The settings file is JSON with three keys: content_folder (a path string), rules (a list of rule names), and required_sections (an object with the keys article and lab, each a list of heading names).

1. Rule names in 1.0.0 are em_dash, table_pipe, missing_section, and table_lead_in.
2. content_folder resolves relative to the settings file, not the current directory.
3. The settings path is a command line argument, with settings.json in the current directory as the default.
4. These problems exit with code 2 and a message naming the key involved: file missing, invalid JSON, a missing key, a wrong value type, an unknown rule name, or a content folder that does not exist.
5. The loader receives the known rule names as an argument, so it does not import the rules module. The command line passes the registry names in.

### File kind

A file is a lab if either test matches. Otherwise it is an article.

1. Name test: the lowercased file name starts with "lab" or contains "lab-" or "lab_".
2. Heading test: the first heading starts with "Lab" followed by a space, a colon, or a digit, ignoring case.
3. The first heading is the first line that starts with one or more # characters and a space, ignoring fenced code blocks.
4. Only .md files are read. Other files are skipped without a finding.
5. A file that cannot be read is kept with kind unreadable and a reason that names the cause, such as UTF-8 for undecodable bytes or the operating system message for permission errors.

### Database

The database has three tables: runs, files, and findings.

1. runs: id, started_at (UTC, ISO 8601 text), content_folder, checker_version, files_checked, finding_count.
2. files: id, run_id (foreign key), path (relative to the content folder), kind (article, lab, or unreadable), reason (empty unless the file was rejected). Every file the walker sees gets a row.
3. findings: id, run_id (foreign key), file_id (foreign key), line, rule, severity, message.
4. The rule column has no CHECK constraint, so a new rule needs no schema change.
5. PRAGMA user_version is set to 1 when the database is created.
6. Foreign keys are switched on right after every connection opens, before any transaction starts.
7. Connections are closed with contextlib.closing.

### Transactions

A run, its files, and its findings are saved in one transaction, or not at all.

1. All reading and rule checking finishes in memory before the database is opened.
2. One save function owns the transaction and commits once at the end. Helper functions never commit.
3. Any error rolls back everything, leaving no trace of the run in any table.
4. A run is saved even when it is clean or every file was rejected. A run is not saved when settings are invalid.

### Exit codes and database path

1. Exit code 0 means every readable file is clean. Exit code 1 means at least one finding or at least one rejected file. Exit code 2 means a settings or usage error.
2. The database path comes from the environment variable CHECKER_DB.
3. If CHECKER_DB is not set, the checker stops with exit code 2 and a clear message. There is no default location.
4. The parent folder of the database is created if it does not exist.
5. Settings and environment problems are checked before any file is read.

### Rule design

1. A base class Rule has a class attribute name and a method check(self, text, file_kind) that returns a list of findings. The base method raises NotImplementedError.
2. Rules receive text, not paths. The runner fills in the file path.
3. Required section names come from the settings file and are passed to the missing section rule when it is created.
4. A registry maps rule names to classes. The settings loader checks names against it.
5. Rules never raise on odd input. An empty file or a file with no tables returns an empty list.
6. The table rules skip fenced code blocks. The em dash rule scans the whole file.

### Violation definitions

1. Em dash: the character U+2014 anywhere in the file, including code blocks and tables. One finding per occurrence, on the line where it appears.
2. Pipe in a table cell: a table is a header row, a separator row, and body rows. A row is flagged when it has more cells than the header row. An escaped pipe is also flagged. One finding per offending row.
3. Missing section: no heading at any level whose text equals a required section name for that file kind, ignoring case and surrounding spaces. One finding per missing section, on line 1. Bold text does not count as a heading.
4. Table without lead-in: a table whose closest preceding non-blank line is a heading, another table, a list item, or the start of the file.

### Command line

1. Subcommands are check, backup, and restore. Only check is built in Phase 2.
2. The entry point is a console script named content-checker.
3. Usage is content-checker check [settings_path]. A top level --version flag is added in Phase 4.
4. The report has one line per finding in the form path:line rule severity message, sorted by path and then line.
5. Rejected files are listed in their own block after the findings, each with its reason.
6. A summary line is always printed last, with files checked, findings, and rejected files.
7. The report goes to stdout. Settings and usage errors go to stderr.

### Release 1.1.0 rule

The fifth rule is heading_skip. It flags a heading that jumps more than one level deeper than the heading before it. The first heading is never flagged, going back up is fine, and fenced code blocks are skipped. It applies to articles and labs. It needs no schema change.

A 1.0.0 image given a settings file that lists heading_skip exits with code 2 and an unknown rule error. That is correct and goes in the rollback steps.

## Branches

Each branch gets its own pull request, a green CI run, and a Linear issue moved to Done on merge. Tests are written first, then the code.

1. feature/settings-and-loader (FDE-2): JSON settings with clear errors, the folder walker, file reading, article or lab detection, and rejection of unreadable files with a reason.
2. feature/rules (FDE-3): the base Rule class and the four rule subclasses, each returning findings.
3. feature/storage (FDE-4): the SQLite schema, foreign keys on every connection, saving a run and its findings in one transaction, and connections closed with contextlib.closing.
4. feature/report-and-cli (FDE-5): report printing, exit codes, CHECKER_DB, and the command line entry point.
5. feature/integration-and-ci (FDE-6): one end-to-end test over the fixtures folder, and the GitHub Actions workflow with ruff and pytest jobs.
6. feature/docker (FDE-7): the Dockerfile, .dockerignore, read-only content mount, named volume for history, and the docker-build CI job.
7. feature/release-1-0-0 (FDE-8): CHANGELOG.md, the version in pyproject.toml, tag v1.0.0, Docker image 1.0.0, backup with Connection.backup, and restore.
8. feature/new-rule (FDE-9): the heading_skip rule, tag v1.1.0, Docker image 1.1.0, and the rollback to 1.0.0.

## Minimum tests per branch

The following table lists the least each branch must prove before its pull request is merged.

| Branch | Minimum tests |
| --- | --- |
| feature/settings-and-loader | Missing settings file, bad JSON, unreadable file, article versus lab |
| feature/rules | One planted violation per rule, plus the clean file returns nothing |
| feature/storage | Run saved with findings, failed save rolls back everything, foreign key enforced |
| feature/report-and-cli | Exit 0 on the clean file, exit 1 on violations, exit 2 on bad settings |
| feature/integration-and-ci | The integration test itself, with the workflow validated by actionlint |
| feature/docker | Tests pass inside the image, read-only mount rejects a write, history survives a second run |
| feature/release-1-0-0 | Restored database passes integrity_check with the original history |
| feature/new-rule | heading_skip fixture and tests, migration test if the schema changed, both images run against the same volume |

## Fixtures

The tests/fixtures folder holds one file per planted violation and one clean file for articles, plus one clean lab. Every rule test reads from it, so the fixtures are the real specification. The em dash fixture is built at run time from the code point U+2014, so no file in the repository contains the character.

## Risks

1. The checker flags its own source. The checker is scoped to the content folder only, and never scans the repository root.
2. A commit inside a helper function breaks the single transaction. Review every storage change for a commit outside the save function.
3. A connection that is never closed, or a foreign key pragma that is missing on a new connection.
4. A value pasted into an SQL string instead of passed as a parameter.
5. A Docker bind mount that is writable, or a database path that sits outside the named volume.
6. A 1.0.0 image run against a settings file that lists heading_skip exits with code 2. This is expected and is documented in the rollback steps.
7. The plan and the code drift apart. Any change to a decision updates this file first.
