# archive: close the change, update the living specs

**Command:** `/tracespec archive [change]`. **Writes:** the living specs, their trace baseline and ledger, the overview's facts; moves the change folder. **Stops for:** nothing when clean.

Archive is the close of a change. It is the only way a living spec is written.

## Do
1. **Count the review findings still open** (an IR that is neither fixed nor "not a problem"). Run [verify.md](verify.md) first if it has not been run.
2. **Archive:** `python <skill folder>/tools/check.py <project root> --archive --ir-open N`. The tool refuses on any error or when N is above 0. It re-runs the full gate (tests, the matrix, scope, tasks ticked, amendments recorded, stale base, **the developer overview complete**) and then:
   - checks that every living spec it will change is clean (a hand-edited spec or a broken ledger refuses the archive);
   - merges the deltas into the living specs in memory, validates the result (every rule has a criterion, every criterion covers a rule, no ID collision), and only then writes: `.tracespec/specs/<capability>/spec.md` (ADDED rows appended, MODIFIED rows replaced, REMOVED rows moved to "Withdrawn" with the reason; IDs never reused);
   - writes the **baseline** (`trace.db`, binary): the graph from ticket to code symbol, with a hash of every spec row, symbol and file, and appends a **ledger** line (`history.jsonl`, each line holding the hash of the line before it, of `spec.md` and of `trace.db`);
   - refreshes the baseline of other capabilities whose linked symbols this change touched, **only if all their criteria pass** (logged as an automatic reconfirm);
   - records the archive in the review log and moves the folder to `.tracespec/changes/archive/<date>-<change>/`.
3. **Closed:** tell the developer in a short report: the change; per capability what changed (rules added, modified, withdrawn); the matrix summary; the number of tests; the review findings by outcome; the files changed; a link to the overview `docs/features/<change>.md` as the one thing worth reading; and what is left for them (read the diff, commit the code, `.tracespec/` and `docs/features/`, open the pull request). No question.
4. **Refused:** fix what it says. A decision (a spec gap, a file outside the affected areas that should stay, an open finding) goes to the developer, then archive again. If the developer wants to look at the build first, show the report, ask "Approve the build?" and record it with `check.py <project root> --approve build --by "<name>" --words "<their exact words>"`, then archive.
5. Make `activeChange` null when the developer has no other change running (the tool does this for the archived one).

This process does not commit, push or open a pull request.
