# Claude Code Instructions

This project is the Course Content Checker, a Python 3.12 command line tool. PLAN.md is the source of truth for every design decision. Read it before writing any code.

## Working rules

1. Never change a decision in PLAN.md. If a decision seems wrong or incomplete, stop and ask first.
2. Write or update the tests first, then write the code that makes them pass.
3. Work on one feature branch at a time, as listed in PLAN.md. Do not start the next branch.
4. Never commit to main. Work happens on a feature branch and goes through a pull request.
5. Make small changes and explain what each one does.
6. Do not use em dashes in any file you write. Use commas or periods.
7. The checker scans the content folder only. It never scans its own source or the repository root.

## Folder layout

1. src/content_checker holds the package.
2. tests holds the pytest tests.
3. tests/fixtures holds the planted violation files and the clean files.
4. PLAN.md holds the decisions. CLAUDE.md holds these instructions.

## Commands

1. Run the tests with pytest.
2. Run the linter with ruff check .
3. Both must pass before any change is committed.

## Code rules

1. Use only the Python standard library, plus pytest and ruff for development.
2. Use parameterized SQL. Never build SQL from strings.
3. Open every database connection with contextlib.closing and switch foreign keys on right after opening.
4. Only the save function commits. Helper functions never commit.
5. Rules receive text and return findings. They do not read files.