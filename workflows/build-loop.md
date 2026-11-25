# build loop: one task, a bounded number of coding attempts

**Used by:** [apply.md](apply.md), part B, once per task. **Writes:** `.tracespec/changes/<change>/build_loop.md` (the coordinator's log). **Stops for:** nothing, unless it ends in "spec gap" or "environment blocked".

You run this loop as the coordinator, never inside the coder or the test writer. It implements one task of an approved change. It does not approve anything and does not replace the independent review.

## The rules
- **At most three coding attempts per task**, counting the first. Read `build_loop.md` before you start and count the attempts already begun for this task: resuming a session does not reset the budget. Only the developer can grant more; record the new total and who granted it.
- **Record an attempt before you dispatch the coder**, so an interrupted call still counts.
- **Evidence is test names and IDs, never test code.** The coder may be told which criteria fail and what `results.py` says about them. It is never given test source or a description of how a test checks something; point it to the criterion.
- **Never weaken a test to get a pass.** A test that looks wrong is a dispute: see apply.md, "When something is wrong".

## One attempt
1. **Baseline.** Run `python <skill folder>/tools/results.py <project root>` and note the pass, fail and error counts and the failing criterion IDs.
2. **Propose.** Write one hypothesis tied to a failing criterion or to the task itself: what behaviour is missing or wrong, in terms of the documents. After a failed attempt, narrow it with the new evidence; do not repeat an unchanged attempt.
3. **Implement.** Start the hooked `tracespec-coder` with the project's absolute path, the change, the task, the spec IDs, the hypothesis and the `results.py` summary.
4. **Probe.** Run `results.py` again, first for the task's criteria (`results.py <project root> AC-12 AC-13`), then the full suite. Exit 0 counts only when the criteria the task serves actually ran: a missing or empty selection is not a pass.
5. **Compare.** Which failing criteria now pass, and did anything that passed before fail? A lower failure count alone proves nothing. Keep what helped; do not merge alternative implementations blindly.
6. **Decide.** Failures remain and budget is left: new hypothesis, next attempt. Stop early when the same failure repeats with no new evidence.

## The log
One row per attempt in `build_loop.md`:

| Task and attempt | Starting evidence | Hypothesis and criteria | Result and remaining failures | Next action |
|---|---|---|---|---|

Record names, IDs, counts and the exit status. Keep test source, code excerpts and raw tracebacks out of it: both build agents can read this file.

## How it ends
Report exactly one of these, and never mark an unfinished task done.

| Outcome | When | What you do |
|---|---|---|
| **verified task** | The full suite passes and the task's criteria have passing tests | Run `check.py --task-done T-n`; it ticks the box and records the symbols touched |
| **spec gap** | The documents say too little, or contradict themselves, or cannot be built as written | Stop. Go to [update.md](update.md) |
| **environment blocked** | A tool, dependency or timeout stops the run | Record the missing prerequisite and stop; repeated code edits cannot fix it |
| **budget exhausted** | Three attempts used | Leave the task unchecked, note the failing IDs, attempts and changed files, and ask the developer |
| **no progress** | The same failure with no new evidence | Same as budget exhausted |
