# Course Content Checker

The Course Content Checker is a small command line tool that reads a folder of Markdown course articles and labs and flags anything that breaks your content rules. Every run is saved to a SQLite history database, so you can see how a course changes over time.

What it checks and what it gives you:

- Five rules: em dash, pipe in a table cell, missing section, table without lead-in, and heading skip.
- Article and lab detection, so each file is held to the sections that fit its kind.
- Run history in SQLite, saved in one transaction per run.
- Backup and restore commands for the history database.
- A Docker image with a read-only content mount and a named volume for history.
- CI on every pull request, with ruff, pytest, and docker-build jobs.

## Install

You need a Mac with Python 3.12, Docker Desktop, and Git. These commands clone the project, create a virtual environment, and install the checker with its development tools.

```bash
git clone https://github.com/EZE22/course-content-checker.git
cd course-content-checker
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Check that the command works:

```bash
content-checker --version
```

```text
content-checker 1.1.0
```

## The rules

The table below lists the five rules you can switch on in the settings file, with what each one flags.

| Rule | What it flags |
| --- | --- |
| em_dash | The em dash character anywhere in a file, one finding per occurrence. |
| table_pipe | A table row with more cells than its header row, including an escaped pipe inside a cell. |
| missing_section | A required section heading that is missing for the kind of file, one finding per missing section. |
| table_lead_in | A table that comes straight after a heading, another table, a list item, or the start of the file. |
| heading_skip | A heading that jumps more than one level deeper than the heading before it. |

## Settings file

The checker is driven by a JSON settings file. This is the one that ships with the demo, examples/settings.json:

```json
{
  "content_folder": "course",
  "rules": ["em_dash", "table_pipe", "missing_section", "table_lead_in", "heading_skip"],
  "required_sections": {
    "article": [
      "Common Mistakes",
      "Try It Yourself",
      "Why This Matters for an FDE",
      "Comprehension Check"
    ],
    "lab": ["Problem Statement", "Requirements", "Grading Rubric"]
  }
}
```

- content_folder is the folder of Markdown files to scan, and a relative path is resolved from the settings file, not from where you run the command.
- rules is the list of rule names to run, in the order you want them run.
- required_sections is an object that says which headings must appear in each kind of file.
- required_sections.article is the list of headings every article must have.
- required_sections.lab is the list of headings every lab must have.

## Run it on the demo

The examples folder holds nine dummy files for a made-up Python basics course. The history database path comes from the CHECKER_DB environment variable, and there is no default, so you always set it. These commands start from a clean database and run the check.

```bash
rm -f /tmp/demo.db
CHECKER_DB=/tmp/demo.db content-checker check examples/settings.json
echo "exit code: $?"
```

```text
article-03-functions.md:1 missing_section error Missing required section: Comprehension Check
article-04-files.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
article-05-errors.md:19 table_pipe error Table row has 3 cells but the header has 2.
article-06-modules.md:24 heading_skip error Heading jumps from level 2 to level 4.
article-07-testing.md:1 missing_section error Missing required section: Why This Matters for an FDE
article-07-testing.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
lab-02-inventory.md:1 missing_section error Missing required section: Grading Rubric
Checked 9 files, 7 findings, 0 rejected.
exit code: 1
```

Each finding line reads path, line, rule, severity, and message. The last line is always the summary.

## Exit codes

The table below shows the three exit codes the check command can return.

| Code | Meaning |
| --- | --- |
| 0 | Every readable file is clean. |
| 1 | At least one finding was reported, or at least one file was rejected. |
| 2 | A settings or usage error, such as a bad settings file, an unknown rule, or CHECKER_DB not set. |

## What the demo does not store

Two cases are not kept in the repository: a file with an em dash, and a file that is not valid text. You can make them in a temporary copy. The printf commands write the bytes for you, so the em dash character never appears in this file.

```bash
rm -rf /tmp/demo2 && cp -r examples /tmp/demo2
printf 'A line with a dash \xe2\x80\x94 in it.\n' >> /tmp/demo2/course/article-01-variables.md
printf '\xff\xfe not valid text' > /tmp/demo2/course/article-08-broken.md
CHECKER_DB=/tmp/demo2.db content-checker check /tmp/demo2/settings.json
echo "exit code: $?"
```

```text
article-01-variables.md:35 em_dash error Em dash found. Use a comma or a period.
article-03-functions.md:1 missing_section error Missing required section: Comprehension Check
article-04-files.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
article-05-errors.md:19 table_pipe error Table row has 3 cells but the header has 2.
article-06-modules.md:24 heading_skip error Heading jumps from level 2 to level 4.
article-07-testing.md:1 missing_section error Missing required section: Why This Matters for an FDE
article-07-testing.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
lab-02-inventory.md:1 missing_section error Missing required section: Grading Rubric
Rejected files:
article-08-broken.md: Not valid UTF-8: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
Checked 10 files, 8 findings, 1 rejected.
exit code: 1
```

The broken file is listed under Rejected files with the reason, and it still counts in the total.

## History

Every run is saved, even a clean one. Run the demo twice with the same database and then look at the runs table.

```bash
export CHECKER_DB=/tmp/demo.db
rm -f "$CHECKER_DB"
content-checker check examples/settings.json
content-checker check examples/settings.json
sqlite3 "$CHECKER_DB" "select id, checker_version, files_checked, finding_count from runs"
```

Both checks print the same seven findings and exit with code 1, as in the demo above. The runs table then shows one row per run:

```text
1|1.1.0|9|7
2|1.1.0|9|7
```

## Backup and restore

Backup copies the history database to a new file and checks the copy. Restore puts a verified backup back in place. This example backs up, deletes the database, restores it, and counts the runs before and after. It uses the same CHECKER_DB as the History section.

```bash
rm -rf /tmp/readme-backups
content-checker backup /tmp/readme-backups/history.bak
echo "exit code: $?"
sqlite3 "$CHECKER_DB" "select count(*) from runs"
rm "$CHECKER_DB"
content-checker restore /tmp/readme-backups/history.bak
echo "exit code: $?"
sqlite3 "$CHECKER_DB" "select count(*) from runs"
```

```text
Backup saved: /tmp/readme-backups/history.bak
Integrity check: ok
exit code: 0
2
Restored: /tmp/demo.db
Integrity check: ok
exit code: 0
2
```

The run count is 2 before the database is deleted and 2 after the restore, so the history came back whole.

## Docker

The runtime image runs as a non-root user. The content folder is mounted read-only at /content, the settings file is mounted read-only at /config/settings.json, and history lives in a named volume at /data. The container settings file is docker/settings.json, and its content_folder is /content.

Build the image and make a copy of the demo course to mount:

```bash
docker build -q --target runtime -t content-checker:1.1.0 .
rm -rf /tmp/demo-content && cp -r examples/course /tmp/demo-content
docker volume rm -f readme-data
```

Run it against the demo. DOCKER_CLI_HINTS=false keeps Docker from printing tips.

```bash
DOCKER_CLI_HINTS=false docker run --rm \
  -v /tmp/demo-content:/content:ro \
  -v "$PWD/docker/settings.json":/config/settings.json:ro \
  -v readme-data:/data \
  content-checker:1.1.0
echo "exit code: $?"
```

```text
article-03-functions.md:1 missing_section error Missing required section: Comprehension Check
article-04-files.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
article-05-errors.md:19 table_pipe error Table row has 3 cells but the header has 2.
article-07-testing.md:1 missing_section error Missing required section: Why This Matters for an FDE
article-07-testing.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
lab-02-inventory.md:1 missing_section error Missing required section: Grading Rubric
Checked 9 files, 6 findings, 0 rejected.
exit code: 1
```

This settings file lists the four original rules, so there is no heading_skip finding and the total is 6. Next, prove the mount is read-only by trying to write into it:

```bash
DOCKER_CLI_HINTS=false docker run --rm --entrypoint sh \
  -v /tmp/demo-content:/content:ro \
  content-checker:1.1.0 -c 'touch /content/test.txt'
echo "exit code: $?"
```

```text
touch: cannot touch '/content/test.txt': Read-only file system
exit code: 1
```

Finally, run the check a second time and count the runs in the volume. The image has no sqlite3 program, so the count uses Python.

```bash
DOCKER_CLI_HINTS=false docker run --rm \
  -v /tmp/demo-content:/content:ro \
  -v "$PWD/docker/settings.json":/config/settings.json:ro \
  -v readme-data:/data \
  content-checker:1.1.0
echo "exit code: $?"
DOCKER_CLI_HINTS=false docker run --rm --entrypoint python -v readme-data:/data \
  content-checker:1.1.0 \
  -c 'import sqlite3; print(sqlite3.connect("/data/history.db").execute("select count(*) from runs").fetchone()[0])'
```

```text
article-03-functions.md:1 missing_section error Missing required section: Comprehension Check
article-04-files.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
article-05-errors.md:19 table_pipe error Table row has 3 cells but the header has 2.
article-07-testing.md:1 missing_section error Missing required section: Why This Matters for an FDE
article-07-testing.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
lab-02-inventory.md:1 missing_section error Missing required section: Grading Rubric
Checked 9 files, 6 findings, 0 rejected.
exit code: 1
2
```

The count is 2 because the container from the first run is gone but its history stayed in the volume. (The volume was fresh when these two runs started, so the count only includes them.)

## Releases and rollback

The version number lives only in pyproject.toml, and the installed package metadata is where the checker reads it from. Each release is a git tag plus a Docker image with the same version number. The history database is shared between versions because there is no schema change between 1.0.0 and 1.1.0.

The rollback below uses a fresh volume called rollback-readme and the two images content-checker:1.0.0 and content-checker:1.1.0. First make a settings file that adds heading_skip to the container settings:

```bash
mkdir -p /tmp/rollback-cfg
sed 's/"table_lead_in"\]/"table_lead_in", "heading_skip"]/' docker/settings.json > /tmp/rollback-cfg/settings.json
docker volume rm -f rollback-readme
```

Step 1. Run 1.0.0 on the demo content:

```bash
DOCKER_CLI_HINTS=false docker run --rm \
  -v /tmp/demo-content:/content:ro \
  -v "$PWD/docker/settings.json":/config/settings.json:ro \
  -v rollback-readme:/data \
  content-checker:1.0.0
echo "exit code: $?"
```

```text
article-03-functions.md:1 missing_section error Missing required section: Comprehension Check
article-04-files.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
article-05-errors.md:19 table_pipe error Table row has 3 cells but the header has 2.
article-07-testing.md:1 missing_section error Missing required section: Why This Matters for an FDE
article-07-testing.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
lab-02-inventory.md:1 missing_section error Missing required section: Grading Rubric
Checked 9 files, 6 findings, 0 rejected.
exit code: 1
```

Step 2. Back up before upgrading, using the 1.0.0 image:

```bash
DOCKER_CLI_HINTS=false docker run --rm -v rollback-readme:/data \
  content-checker:1.0.0 backup /data/pre-upgrade.bak
echo "exit code: $?"
```

```text
Backup saved: /data/pre-upgrade.bak
Integrity check: ok
exit code: 0
```

Step 3. Run 1.1.0 with the settings file that adds heading_skip:

```bash
DOCKER_CLI_HINTS=false docker run --rm \
  -v /tmp/demo-content:/content:ro \
  -v /tmp/rollback-cfg/settings.json:/config/settings.json:ro \
  -v rollback-readme:/data \
  content-checker:1.1.0
echo "exit code: $?"
```

```text
article-03-functions.md:1 missing_section error Missing required section: Comprehension Check
article-04-files.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
article-05-errors.md:19 table_pipe error Table row has 3 cells but the header has 2.
article-06-modules.md:24 heading_skip error Heading jumps from level 2 to level 4.
article-07-testing.md:1 missing_section error Missing required section: Why This Matters for an FDE
article-07-testing.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
lab-02-inventory.md:1 missing_section error Missing required section: Grading Rubric
Checked 9 files, 7 findings, 0 rejected.
exit code: 1
```

Step 4. Roll back by running 1.0.0 again on the same volume with the original settings file:

```bash
DOCKER_CLI_HINTS=false docker run --rm \
  -v /tmp/demo-content:/content:ro \
  -v "$PWD/docker/settings.json":/config/settings.json:ro \
  -v rollback-readme:/data \
  content-checker:1.0.0
echo "exit code: $?"
```

```text
article-03-functions.md:1 missing_section error Missing required section: Comprehension Check
article-04-files.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
article-05-errors.md:19 table_pipe error Table row has 3 cells but the header has 2.
article-07-testing.md:1 missing_section error Missing required section: Why This Matters for an FDE
article-07-testing.md:13 table_lead_in error Table follows a heading. Add a lead-in sentence.
lab-02-inventory.md:1 missing_section error Missing required section: Grading Rubric
Checked 9 files, 6 findings, 0 rejected.
exit code: 1
```

Step 5. Print the runs table. All three runs are there, and the old version read the history the new version wrote:

```bash
DOCKER_CLI_HINTS=false docker run --rm --entrypoint python -v rollback-readme:/data \
  content-checker:1.0.0 \
  -c 'import sqlite3; [print("|".join(map(str, r))) for r in sqlite3.connect("/data/history.db").execute("select id, checker_version, files_checked, finding_count from runs")]'
```

```text
1|1.0.0|9|6
2|1.1.0|9|7
3|1.0.0|9|6
```

Step 6. Last, show what happens when 1.0.0 is given the settings file that lists heading_skip. It does not know that rule, so it stops with exit code 2. That is correct and expected.

```bash
DOCKER_CLI_HINTS=false docker run --rm \
  -v /tmp/demo-content:/content:ro \
  -v /tmp/rollback-cfg/settings.json:/config/settings.json:ro \
  -v rollback-readme:/data \
  content-checker:1.0.0
echo "exit code: $?"
```

```text
Error: Settings key rules names an unknown rule: heading_skip
exit code: 2
```

If a future release changes the database schema, stop the container, restore the pre-upgrade backup with the older image's restore command, and only then roll back.

## Known limits

- A content folder with no Markdown files exits 0.
- A leftover journal file from a crash may sit next to a restored database.
- Backup checks that the destination is free and then moves the copy in, so a file created in between is overwritten.

## Development

Run the tests with `pytest` and the linter with `ruff check .`. Both must pass before a change is committed. CI runs a ruff job, a pytest job, and a docker-build job that builds the test image, runs the tests inside it, and builds and smoke tests the runtime image.

Design decisions live in PLAN.md, and the history of each release lives in CHANGELOG.md.
