# Course Content Checker Plan

This file records the decisions made before any code was written. Every prompt to Claude Code points back here. If a decision needs to change, update this file first, then change the code.

## Decisions

### Finding shape

A finding has five fields: file, line, rule, severity, message. A rule returns the last four, and the runner adds the file path.

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
6. An empty CHECKER_DB is treated the same as an unset one.

### Rule design

1. A base class Rule has a class attribute name and a method check(self, text, file_kind) that returns a list of findings. The base method raises NotImplementedError.
2. Rules receive text, not paths. The runner fills in the file path.
3. Required section names come from the settings file and are passed to the missing section rule when it is created.
4. A registry maps rule names to classes. The settings loader checks names against it.
5. Rules never raise on odd input. An empty file or a file with no tables returns an empty list.
6. The table rules, missing_section, and heading_skip skip fenced code blocks. The em dash rule scans the whole file.

### Violation definitions

1. Em dash: the character U+2014 anywhere in the file, including code blocks and tables. One finding per occurrence, on the line where it appears.
2. Pipe in a table cell: a table is a header row, a separator row, and body rows. A row is flagged when it has more cells than the header row. An escaped pipe is also flagged. One finding per offending row.
3. Missing section: no heading at any level whose text equals a required section name for that file kind, ignoring case and surrounding spaces. One finding per missing section, on line 1. Bold text does not count as a heading. A heading line starts with one to six # characters followed by whitespace, and a line inside a fenced code block is never a heading.
4. Table without lead-in: a table whose closest preceding non-blank line is a heading, another table, a list item, or the start of the file.

### Command line

1. Subcommands are check, backup, and restore. Only check is built in Phase 2.
2. The entry point is a console script named content-checker.
3. Usage is content-checker check [settings_path]. A top level --version flag is added in Phase 4.
4. The report has one line per finding in the form path:line rule severity message, sorted by path and then line.
5. Rejected files are listed in their own block after the findings, each with its reason.
6. A summary line is always printed last, with files checked, findings, and rejected files.
7. The report goes to stdout. Settings and usage errors go to stderr.
8. Rejected files are listed after the findings under the line "Rejected files:", one line per file in the form "path: reason", sorted by path. The block is left out when no file was rejected.
9. The summary line reads "Checked N files, F findings, R rejected." where N counts every .md file found, including rejected ones. The words stay plural.
10. Findings are sorted by path, then line, then rule name.
11. Settings and usage errors print one line to stderr in the form "Error: message" and exit with code 2. A missing or unknown subcommand is a usage error.
12. The order of work is: load settings, check CHECKER_DB, read files, run rules, save the run, print the report. Settings are checked before CHECKER_DB, so when both are wrong the settings message is shown. Rules run only on readable files, in the order the settings list them. If saving fails, the report is still printed, then "Error: message" goes to stderr and the exit code is 2.
13. The checker version saved with each run comes from the installed package metadata, so the version number lives only in pyproject.toml.

### Continuous integration

1. The workflow file is .github/workflows/ci.yml. It runs on every pull request and on every push to main.
2. It has two jobs for now, ruff and pytest. The docker-build job is added in feature/docker.
3. Jobs run on ubuntu-latest with Python 3.12 and install the package with pip install -e ".[dev]".
4. The versions of pytest and ruff are pinned in pyproject.toml under the dev extra, so local runs and CI use the same tools.
5. The workflow grants only read access to the repository contents, and each job has a timeout.
6. The workflow file is validated with actionlint before it is committed. This is a manual step run on the Mac, not a CI job.
7. A pull request is merged only when all jobs are green. The first four branches were merged before CI existed, on local green pytest and ruff.

### Docker

1. The Dockerfile uses python:3.12-slim and has a shared base stage, then a test stage, then a runtime stage. Runtime is the last stage, so it is the default.
2. The runtime stage installs the package with pip install (not editable), runs as a non-root user named checker, and uses content-checker as the entry point, with check /config/settings.json as the default command.
3. The test stage adds the tests folder, the examples folder, and the dev extra, and its default command is pytest.
4. The content folder is mounted read-only at /content. The settings file is mounted read-only at /config/settings.json, and its content_folder is /content.
5. History lives in a named Docker volume mounted at /data. The image sets CHECKER_DB to /data/history.db.
6. A .dockerignore keeps the virtual environment, .git, .github, caches, egg-info, and any database file out of the build.
7. The docker-build CI job builds the test stage and runs the tests inside it, then builds the runtime image.
8. The example container settings file is docker/settings.json.

### Release 1.0.0, backup, and restore

1. The version number lives only in pyproject.toml. Release 1.0.0 sets it to 1.0.0.
2. content-checker --version prints "content-checker 1.0.0" to stdout and exits 0. The number comes from the installed package metadata.
3. content-checker backup DESTINATION copies the history database to DESTINATION with sqlite3 Connection.backup. The source is opened read-only, so backup can never create or change the history database. Backup works while no check is running.
4. The destination must not already exist, and its parent folder is created if needed. Backup never overwrites a file.
5. Backup copies into a temporary file next to DESTINATION, runs PRAGMA integrity_check on it, and moves it to DESTINATION only if the result is ok. Otherwise the temporary file is removed and the command fails.
6. content-checker restore BACKUP_FILE replaces the history database from a backup file. The backup is verified first: integrity_check returns ok, user_version is 1, and the runs, files, and findings tables exist.
7. Restore copies the verified backup to a temporary file next to the history database, verifies that copy, then swaps it into place with os.replace. If a history database already exists, it is first copied aside next to it with the suffix .before-restore.
8. backup and restore read the database path from CHECKER_DB, with the same rules as check: unset or empty is an error.
9. backup prints "Backup saved: DESTINATION" and then "Integrity check: ok". restore prints "Restored: DB_PATH" and then "Integrity check: ok".
10. Success exits 0. Any failure prints "Error: message" to stderr, exits 2, and leaves the history database as it was.
11. The release is a CHANGELOG.md entry, a v1.0.0 tag on main after the merge, and a Docker image tagged 1.0.0 built from that commit.
12. If the .before-restore file already exists, restore fails with an error and changes nothing, so an earlier safety copy is never overwritten.
13. Any sqlite3 error while copying or verifying is reported as a BackupError whose message includes the path and SQLite's own error text.

### Demo

1. The examples/course folder holds nine dummy Markdown files for a made-up Python basics course. It contains no client names and no real course material.
2. examples/settings.json lists all five rules, and its content_folder is "course".
3. Running the checker on it gives exactly 7 findings in 9 files and exit code 1. tests/test_demo.py keeps this true.
4. The em dash and unreadable file cases are not stored in the repository. The README creates them in a temporary copy.

### Release 1.1.0 rule

The fifth rule is heading_skip. It flags a heading that jumps more than one level deeper than the heading before it. The first heading is never flagged, going back up is fine, and fenced code blocks are skipped. It applies to articles and labs. It needs no schema change.

A 1.0.0 image given a settings file that lists heading_skip exits with code 2 and an unknown rule error. That is correct and goes in the rollback steps.

1. A finding is reported on the line of the heading that jumped, with severity error and a message that names both levels.
2. The level of a heading is its number of leading # characters. A heading line starts with one or more # characters followed by a space.
3. Each heading is compared with the heading directly before it, even when that heading was itself flagged.
4. The rule is registered in RULE_REGISTRY under the name heading_skip, so a settings file can list it. A settings file that does not list it behaves exactly as in 1.0.0.
5. The fixture for this rule lives in tests/fixtures_heading_skip, so the counts for the existing fixtures folder stay the same.

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
9. docs/demo-and-readme (FDE-10): the demo course folder, its test, and the README with real command output.
10. chore/audit-fixes (FDE-11): the fixes found by auditing this plan against the build.

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

## Manual checks

These checks are done by hand and are shown with real output in README.md.

1. The Docker runtime image refuses a write into the read-only content mount, and run history survives in the named volume across containers.
2. Both release images run against the same volume, no history is lost in either direction, and the 1.0.0 image stops with exit code 2 on a settings file that lists heading_skip.
3. The v1.0.0 and v1.1.0 images are built from the commits their tags point to.
4. actionlint is run on the workflow file before it is committed.

## Risks

1. The checker flags its own source. The checker is scoped to the content folder only, and never scans the repository root.
2. A commit inside a helper function breaks the single transaction. Review every storage change for a commit outside the save function.
3. A connection that is never closed, or a foreign key pragma that is missing on a new connection.
4. A value pasted into an SQL string instead of passed as a parameter.
5. A Docker bind mount that is writable, or a database path that sits outside the named volume.
6. A 1.0.0 image run against a settings file that lists heading_skip exits with code 2. This is expected and is documented in the rollback steps.
7. The plan and the code drift apart. Any change to a decision updates this file first.
