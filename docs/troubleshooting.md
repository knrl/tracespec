# Troubleshooting

Start with `check.py <project> --doctor`: it checks Python, git, the agents and their guard hook, and your test command, and
says how to fix what it finds. On this page `check.py` stands for `python ~/.claude/skills/tracespec/tools/check.py` (where `install.py` puts it).

## Setup

**`/tracespec` or the agents are not found.** Skills and agents load when a Claude Code session starts. Run `python install.py`, then
start a new session. Check that `~/.claude/skills/tracespec/SKILL.md` and `~/.claude/agents/tracespec-coder.md` exist.

**`CANNOT RUN: layout.testCmd is empty`.** Discovery could not detect your stack. Set `layout.testCmd` and `layout.junit` in
`.tracespec.json` ([Customization](customization.md)).

**`CANNOT RUN: the test command wrote no JUnit file`.** The command failed before running any test, or does not write JUnit XML where
`layout.junit` says. Run `testCmd` yourself to see why. Node with jest needs `jest-junit`; Go needs `gotestsum`; .NET needs the JUnit
logger package.

**`no .tracespec.json found`.** Run the command inside the project, or pass the project path. The first `/tracespec propose` creates it.

**The agent keeps asking to read files by name instead of searching.** Your tests sit next to your code (`foo.ts` and `foo.test.ts`), and
no search can leave the hidden files out, so the build agents have searching switched off. This is by design.

## Checks that refuse

| You see | What it means | What to do |
|---|---|---|
| `TEST001` | A criterion has no test in the run | The test name must carry the criterion number (`test_AC31_...`); a comment or a skipped test does not count |
| `TEST005` | A new test names no criterion | Add the number to its name, or delete the test |
| `TEST007` | A modified criterion's tests still pass | Update a test to the new behaviour so it fails before the code changes |
| `TEST002` naming a removed criterion | A test still exists for a criterion this change removes | Delete that test |
| `TASK004` | A task is not ticked | Run `--task-start`/`--task-done`, or finish the task |
| `SPEC010` | An approved delta row was changed | Make a new version and approve again |
| `SPEC012` | The approved proposal was edited, no delta row changed | `check.py --amend --note "what and why"` |
| `DELTA010` | Another change was archived and touched a row you modify or remove | Read the new living row, rebase your delta on it, approve again |
| `CHG001` | A changed file is outside "Affected areas" | Revert it, or add the path to `design.md` (an amendment if no rule changes) |
| `OVERVIEW00x` | The developer overview is missing or incomplete | `check.py --overview`, then write the narrative sections; every path in the components table must exist |

Every finding prints its code and a message that says what to fix. `--approve` and `--archive` refuse on any error and write nothing.

## Drift and the audit

**`DRIFT-CODE` / `DRIFT-TEST` after a refactor.** The linked symbol or test changed. If behaviour did not change,
`check.py . --reconfirm <capability> --note "..."`; it works only when every criterion of the capability passes. If behaviour changed,
propose a change.

**`DRIFT-CODE ... was deleted or renamed`.** The symbol is gone. If the same text now lives elsewhere, the message says where, and
`--reconfirm` follows it. Otherwise the link is dropped and reported.

**`DRIFT-SPEC` and you did not edit the spec.** A pull or merge may have changed `spec.md`, `trace.db` or `history.jsonl` without the
others (a conflict resolved the wrong way). Restore all three from the same commit.

**A result shows `stale`.** A symbol it depended on changed since the last run. `check.py . --audit` runs the tests again.

**The audit is noisy after I changed a shared helper.** Links are to symbols and calls between functions are not traced, so a callee's
change does not flag its callers. If you see unrelated findings, check that the changed symbol really is linked: `check.py . --trace file::symbol`.

## Other

**Strange characters in the output on Windows.** The tool switches its output to UTF-8. If your terminal still shows garbage, run
`chcp 65001` or use Windows Terminal.

**The live layer seems wrong.** It is only a cache: delete `.tracespec/cache/` and run any command; it rebuilds.

**A conflict in `trace.db`.** See [Team workflow](team-workflow.md#merge-conflicts-in-tracedb).

**Something else.** Open an issue with the form: include `check.py --version`, your OS and Python version, your test runner, and the
full output of the failing command.
