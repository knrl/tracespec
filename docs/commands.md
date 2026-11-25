# Commands

## Slash commands (in Claude Code)

| Command | What it does |
|---|---|
| `/tracespec <request>` | Same as `propose`. With no argument it continues the active change. |
| `/tracespec explore <topic>` | Read-only thinking partner. Writes nothing unless you ask. |
| `/tracespec propose <request>` | Discover the project (first time), ask questions, write the change folder, stop for your approval. |
| `/tracespec apply [change]` | Skeleton, tests that fail first, then code, task by task. Resumable. |
| `/tracespec update [change]` | Revise the documents: an amendment, or a new version approved again. |
| `/tracespec verify [change]` | Converge code against documents, independent review, write the overview, readiness report. |
| `/tracespec archive [change]` | Merge the delta into the living specs, write the baseline and ledger, move to the archive. |
| `/tracespec audit` | Find drift in specs, code and tests; resolve it on purpose. |
| `/tracespec trace <target>` | Ask how something relates to the rest of the graph. |
| `/tracespec list`, `show <change>`, `view` | Changes with progress, a delta view, a one-screen dashboard. |

## The command-line tool

`check.py` lives in the skill's `tools/` folder (`~/.claude/skills/tracespec/tools/check.py` once installed). The agent runs it for
you; run it yourself when you want a quick answer. `<project>` is the project root.

```
python check.py <project> [options]
```

### Setup and health

| Command | Purpose |
|---|---|
| `<folder> --init` | Create `.tracespec.json` from what the folder looks like: stack, test and code paths, test command. Never overwrites, and refuses inside an existing project. |
| `[<project>] --doctor [--no-run]` | Is this machine and project ready? Checks Python 3.10+, git (optional), the two agents and their guard hook (it asks the real hook to read a hidden file and expects a refusal), that the test command exists and, unless `--no-run`, that it runs once and writes a JUnit report. Prints `ok`, `warn` or `FAIL` per check with the fix; exit 1 when anything fails. |

### Checks

| Command | Purpose |
|---|---|
| *(no option)* | Structural checks of the active change |
| `--gate N` | Checks for a phase: 1 questions, 2 proposal, 3 tests written, 4 build, 5 close. Gates 3, 4 and 5 run the tests. |
| `--run` | Run the tests as part of a check that would not run them on its own |
| `--change NAME` | A change other than the active one |
| `--matrix` | Run the tests and print the change's traceability matrix |
| `--audit [--no-run] [--ci]` | Compare the working tree with the baseline. `--no-run` does the hash checks only. Exit 1 on any error. |

### Commands that write

The tool does the bookkeeping; the build agents cannot write these.

| Command | Purpose |
|---|---|
| `--baseline` | Run the suite and record the existing tests and uncommitted files |
| `--approve change --by NAME --words "..."` | Record the developer's approval of the proposal. Refuses on any error. |
| `--approve build --by NAME --words "..."` | Record a build approval (only when asked for) |
| `--amend --note "..."` | Record an edit of an approved proposal that changed no delta row |
| `--task-start T-n` / `--task-done T-n` | Bracket a task. `--task-done` ticks it only when its criteria pass, and records the symbols touched. |
| `--overview` | Create the skeleton of `docs/features/<change>.md` (it never rewrites an existing one) |
| `--archive --ir-open N` | Close the change. `N` is the number of review findings still open and must be 0. |
| `--reconfirm <capability or ID>... --note "..."` | Refresh the baseline after a refactor. Every criterion must pass. |
| `--install-hooks` | Git hooks (post-commit, post-merge, post-checkout) that run `--sync` and never block |

### Reading

| Command | Purpose |
|---|---|
| `--trace TARGET` | Walk the graph (below). `--impact` is an alias. |
| `--list`, `--view`, `--show CHANGE [--diff]` | Status views |
| `--next-id FR\|NFR\|AC\|NG` | The next free ID |
| `--export FILE [--living]` | Write a matrix as Markdown, on request |
| `--sync [--quiet]` | Refresh the live layer (it runs at the start of every command anyway) |
| `--fingerprint FILE`, `--fingerprint code`, `--detect`, `--version`, `--help` | Helpers (`--help` and `--version` work anywhere) |

The project folder always comes first. An unknown option, a missing value or a number out of range stops the command with exit 2
and a message; it never runs a different check by accident.

### `--trace`

A target is a rule or criterion ID (`FR-12`, `AC-31`), a test name or part of it, a task (`T-2`, or `add-discount/T-2`), a file,
`file::symbol`, `file:line`, an external reference (`JIRA-482`), or a capability.

| Option | Meaning |
|---|---|
| `--up` | Toward the ticket: why it exists |
| `--down` | Toward the code and tests: what was built for it |
| `--story` | The whole of the rule the target belongs to (the default for a test, task, symbol or file) |
| `--depth N`, `--limit N` | How far to walk (default 8) and how many lines to print (default 120) |
| `--json`, `--mermaid` | Machine-readable output, or a diagram to paste into a document |

Each node shows its state in angle brackets: code and tests are `ok`, `CHANGED since the last archive` or `MISSING` (with "same text now
at ..." when it moved); a criterion shows its last run and whether it is `fresh` or `stale`; a change not yet archived is marked
`in flight`.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | No errors |
| 1 | Findings with errors, or a refusal |
| 2 | The command could not run (bad arguments, no project, tests cannot run) |

### Finding codes

Warnings never fail a gate. Errors do.

| Code | Meaning |
|---|---|
| STATE001, STATE002 | Invalid `layout` in `.tracespec.json`; no active change |
| SPEC000 | `proposal.md` is missing |
| SPEC001, SPEC004, SPEC014 | After the merge, a rule has no criterion, a criterion covers no rule, or it covers a rule that is not there |
| SPEC002, SPEC003 | An ID is named but defined nowhere, or defined twice |
| SPEC005 | A rule or design decision names no source (a Q, ASM, OPEN or G) |
| SPEC006 | `proposal.md` lacks its Version and Status header lines |
| SPEC007, SPEC008, SPEC009, SPEC013 | An assumption is still open; a required section is missing; TBD or a placeholder remains; "Affected areas" lists no path |
| SPEC010 | An approved delta row changed: new version, approve again |
| SPEC011 | The proposal says Approved but no approval is recorded |
| SPEC012 | The approved proposal was edited but no delta row changed: record an amendment (a warning, an error at gate 5) |
| CLR001 | No question was recorded |
| DELTA001, DELTA002 | ADDED id already exists; MODIFIED or REMOVED id does not |
| DELTA005, DELTA011 | An ID clashes with another active change, or is used in two capabilities |
| DELTA006, DELTA008, DELTA009, DELTA012 | A row is outside a `Capability:` heading; a row has too few columns; a new capability has no Purpose; the change has no delta rows |
| DELTA010 | A living row this change modifies or removes changed after approval (another change was archived) |
| TIER001 | A small change touches more than three rules (warning) |
| GATE001 | The proposal is not approved yet |
| TASK000, TASK001, TASK002, TASK003, TASK004 | No task list; a criterion or decision is in no task; a task serves something undefined; a task is not done |
| TEST001 | A criterion has no test in the run |
| TEST002 | A test names a criterion that is undefined or that the change removes |
| TEST003, TEST004 | Tests cannot run or fail; a criterion has no passing test |
| TEST005 | A new test names no criterion |
| TEST006, TEST007 | A new test already passes (warning); a modified criterion's tests still pass (error) |
| TEST008 | No baseline of existing tests is recorded (warning) |
| CHG001, CHG002 | A changed file lies outside "Affected areas"; the scope check was skipped because there is no git repository (a warning) |
| LINK001 | A rule or criterion has no code recorded on its tasks (warning) |
| REF001, REF002 | An external reference is missing or does not match `refPattern` (only when configured) |
| OVERVIEW001 ... OVERVIEW007 | The developer overview is missing, lacks a section (purpose, design, key components), is a placeholder or empty, names a component that does not exist, or is too long (a warning above 60 lines) |
| DRIFT-SPEC, DRIFT-CODE, DRIFT-TEST | The audit: a spec, a linked symbol, or a linked test differs from the baseline |
| UNCOVERED | The audit: a criterion has no passing test in a fresh run |
| UNLINKED-TEST | The audit: a test names a criterion no living spec defines (a warning) |
