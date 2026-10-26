# Course Content Checker: Build Notes

Written October 25, 2026.

## What was built

A Python 3.12 command line tool that checks a folder of Markdown articles and labs against five content rules (em dash, pipe in a table cell, missing section, table without a lead-in, and heading level skip), saves every run to SQLite, and exits with code 1 when it finds a problem. It ships as a Docker image, runs ruff, pytest, and a Docker build in CI on every pull request, and has backup, restore, and a tested rollback from release 1.1.0 to 1.0.0.

The build used a written plan (PLAN.md), a file of working rules for the AI assistant (CLAUDE.md), one Linear issue per branch, tests written before code, and a human review of every change.

## Where the plan and the code disagreed

An audit of 118 plan decisions found 5 that differed from the build and 7 that no test covered. The five differences were:

1. Finding shape: the plan said five fields, but a rule returns four and the runner adds the file path.
2. The `.dockerignore` patterns only matched the top level, so egg-info folders and database files in subfolders went into the image.
3. Backup used a temporary file and a rename, while the plan said "copy".
4. The branch list and the CI wording drifted. "Both jobs" became three jobs, and one branch was never added.
5. A heading inside a code block counted as a required section, and the plan said nothing about it.

The plan also never decided these, so the assistant had to ask or guess:

- What an empty rules list means.
- What an empty content folder means.
- Whether an empty database path variable counts as unset.
- What happens when saving the run fails.
- The exact layout of the report.

## What took longest in Docker

Installing Docker Desktop and understanding images versus containers took longer than writing the Dockerfile.

1. Docker Desktop was not installed, which took about 20 minutes.
2. Images and containers got confused. The Containers tab was empty because the run command used `--rm`, which deletes a container when it exits.
3. A named volume needs its folder owned by the non-root user, set before the `USER` line.
4. The test stage must copy every folder the tests read, or CI fails while the laptop passes.
5. One test is skipped inside Docker, because the container runs as root.

## What the AI assistant got wrong or missed

Green tests proved little on their own. Three mutation checks, where the code is broken on purpose to see a test fail, were the real proof.

1. Two error tests checked only the exception type. Counting `pytest.raises` against `match=` caught it.
2. One assertion ended in `or True` and could never fail. Reading the test caught it.
3. A test took its folder snapshot before the folder existed, so correct code would have failed it. Reading the test caught it.
4. The file tool wrote an em dash escape as the real character twice. A `grep` caught it, and a repository-wide scan test now guards it.
5. The rollback tests accepted any exception, and the first version of the prompt let the failure happen before any write, so a rollback was never exercised. A mutation check that removed the rollback caught it.

The assistant also did well in two places. It stopped and asked when the plan was silent. It stopped again when its own experiment showed the spec was wrong, because a zeroed database page raises a "malformed" error instead of failing `integrity_check`.

## Time per phase

The build took about 7.5 hours with the assistant writing the code. The table below shows approximate minutes per phase, taken from message times, and it includes waiting and detours.

| Phase | Minutes |
| --- | --- |
| Decisions | 10 |
| Repository, board, PLAN.md, CLAUDE.md | 90 |
| Five feature branches | 180 |
| Docker | 45 |
| Release 1.0.0, backup, and restore | 30 |
| Release 1.1.0 and rollback | 25 |
| Demo folder and README | 15 |
| Audit and fixes | 25 |
| Detour into Word and file conversion | 35 |
| Total | 455 |

The first feature branch took about 75 minutes. Later ones took 20 to 55 minutes once the pattern was set.

## Easy to get wrong

These are the places a learner is most likely to lose time.

1. Pasting a prompt into the chat instead of the coding assistant, or pasting the same prompt twice.
2. `brew` waits at a `[y/n]` prompt, and learners paste more commands behind it.
3. The default Python was 3.14, so `python3.12` was not found.
4. A terminal restart drops the `(.venv)` prompt.
5. The Git pager traps the terminal until you press `q`.
6. A Markdown code fence pasted into the shell leaves an unclosed quote.
7. `git diff` on a file Git does not track yet prints nothing, which looks like a clean revert.
8. Closing the assistant panel in the middle of an approval hides what was written, so check `git status`.
9. Docker prints a "Debug with Gordon" tip after any non-zero exit. Exit code 1 means findings were reported, not a crash.
10. `ubuntu-latest` can change under a passing pipeline.
11. Ruff import-order complaints appeared on files that had passed before, and the cause was never fully explained. Telling ruff that the package is first-party stopped them.

## The biggest lesson

Test how the real input reaches the tool before building anything on top of it. The plan assumed the articles were Markdown files in a folder. The real articles lived in an LMS and in Word, and exporting them cost more time than checking them by hand. Nobody tried that path until the end.

The checker is still useful as an exact, repeatable gate over many files before a bulk upload. For a single article, pasting it into an AI chat along with the rules is faster.
