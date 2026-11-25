# apply: tests first, then code, task by task

**Command:** `/tracespec apply [change]`. **Writes:** tests (test agent), code (coder agent), `tasks.md` ticks (the tool). **Stops for:** nothing, unless a spec gap needs a decision.

Goal: tests written from the approved documents by an agent that never sees the code, seen failing for the right reason, then code written by another agent that never sees the tests, until every criterion passes, in the project's own style, with the existing tests still passing.

**Tests and code are written by different agents, and neither sees the other's work.** The test writer reads the change's documents, the living specs and the existing tests; the coder reads the same documents and the code. A passing test then means the code does what the specs say, not what the test's author expected. Hooks enforce it. Tests run only through `tools/results.py`, which reports test names, spec IDs and pass or fail, never test or code text.

A fresh session is a good place to start apply; progress lives in the checkboxes of `tasks.md`, so a new session resumes at the first unchecked task.

## Start
1. Find the change (the argument, or `activeChange`). Run `python <skill folder>/tools/check.py <project root> --audit --no-run`. Drift in a capability this change touches must be settled first (see [audit.md](audit.md)); drift elsewhere is reported, not blocking.
2. **The proposal must be approved** (`phase` is apply). No test and no feature code exists before that. If the tool says a living row changed since approval (DELTA010), another change was archived first: re-read it, update the delta, approve again (see [update.md](update.md)).
3. **Make sure the two agents are installed** (once per computer): if `tracespec-test-writer` and `tracespec-coder` are not among the agents you can start, ask the developer, then copy [../templates/agents/tracespec-test-writer.md](../templates/agents/tracespec-test-writer.md) and [../templates/agents/tracespec-coder.md](../templates/agents/tracespec-coder.md) to `~/.claude/agents/`, replacing `{skill_dir}` with this skill's folder (forward slashes). Agents load when a session starts: after installing, tell the developer to start a new session and run `/tracespec apply` again. Never write the tests and the code in one context; that needs a skipped-check line in the review log.

## A. Skeleton and tests
1. **T-1, the skeleton.** `python <skill folder>/tools/check.py <project root> --task-start T-1` (it notes the hash of every code symbol, so the tool can tell later which symbols the task touched), then start `tracespec-coder` with T-1: it creates the interfaces of design.md as stubs that do nothing useful, so tests fail on behaviour, not on a missing import. Then `--task-done T-1`. If an interface cannot exist as a stub, say so in tasks.md; a test may then fail with "cannot load" naming that interface, which is a right reason.
2. **Tests, for every ADDED or MODIFIED criterion.** Start `tracespec-test-writer` with the project's absolute path, the change name and the criteria (IDs only, never code). It writes the tests and shows with `results.py` that they fail. Its rules for changes:
   - ADDED criterion: a new test whose name carries the AC number.
   - **MODIFIED criterion: update an existing test to the new behaviour**, so it fails before the code changes. A test that still passes proves nothing; the tool rejects it (TEST007).
   - **REMOVED criterion: delete its tests.** A test that names a removed criterion is an error.
   - Criteria the delta does not name keep their tests untouched.
3. **Check**, from the `results.py` lines only: each new or updated test fails with a reason that names missing behaviour or a missing interface (a failing import in the test, a typo or a crash in its setup is not a right reason; send it back).
4. **Run the gate:** `python <skill folder>/tools/check.py <project root> --gate 3`. It runs the tests and decides, deterministically: every criterion has a test in the run whose name carries its number (a comment or a skipped test does not count); no test names a criterion that is undefined or removed; every new test names one; every ADDED or MODIFIED criterion and every D is in a task; a MODIFIED criterion has a failing test. A warning (TEST006) means a new test already passes: the test writer must explain or fix it. It writes the change's `traceability.md`. Fix findings: test problems go back to the test writer with the finding; spec problems are handled in [update.md](update.md). **Never judge coverage yourself.**
5. Tell the developer in two or three lines: the matrix summary (every criterion has a test, none passing yet), the number of tests, that the existing tests still pass. Do not wait; go on.

## B. Code, task by task
For each remaining task, the first unchecked one whose `needs` are done:
1. `check.py <project root> --task-start T-n`.
2. Run the [build loop](build-loop.md) for this project and T-n. It dispatches the hooked `tracespec-coder`, compares test evidence, and limits coding attempts to three per task across sessions unless the developer extends the budget. Its log is `.tracespec/changes/<change>/build_loop.md`. What you pass to the coder is the project path, the change, the task, the spec IDs and `results.py` summaries. **Never paste test code** into its prompt and never describe how a test checks something; point to the criterion.
3. `check.py <project root> --task-done T-n`. It ticks the box only when every criterion the task serves has a passing test, and writes the **symbols** the task touched (functions, methods, classes that are new or changed) and their files onto the task line. Archive turns those into code links, so a later edit to an unrelated function in the same file does not flag this task's rules. Then run the project's other `checks` (lint, types, build) and the full suite with `results.py`: nothing that passed before fails.

## When something is wrong
- **One agent says the other is wrong.** The coder believes a test contradicts the spec, or the tester finds the spec silent. Neither changes the other's work. Read the criterion both cite: if the test does not match it, the test writer fixes the test, given the criterion text, not the code; if the code does not match it, the coder fixes the code; if the spec does not say, it is a spec gap.
- **A spec gap, or the spec cannot be built as written: stop.** Do not improvise. If behaviour the developer cares about is affected, ask them. Either way change the documents as [update.md](update.md) says, then tell the agents which version counts. Collect small gaps into one change where you can.
- **A new wish** is not built now. Write it in the review log as a follow-up, unless the developer says the change cannot ship without it; then it is a spec change.
- **Do not commit or push.**

## End
When every task is checked, run `python <skill folder>/tools/check.py <project root> --gate 4`: every criterion passes, nothing fails except `knownFailing`, no task is open, and no file changed outside the change's "Affected areas" (revert it, or add the path to design.md as an amendment). Then go on to [verify.md](verify.md).
