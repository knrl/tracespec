# update: revise a change's documents

**Command:** `/tracespec update [change]`. **Writes:** the change's documents. **Stops for:** the developer's confirmation of what you will change.

Use it when a question was answered differently, a spec gap showed up in apply, the developer wants a rule or criterion changed, or another change was archived under this one.

## Do
1. Find the change. Read all its documents. If the developer gave no revision, run a **coherence review**: do `proposal.md`, the deltas, `design.md` and `tasks.md` still say the same thing? List what does not.
2. **Show what you will change** before you write it, one document at a time: the rows, in plain words. Write after the developer confirms. A correction to an earlier answer is a new row under "Corrections", never an edit of the old answer. Update everything that cites it and tell them what changes.
3. **Is it an amendment or a new version?** The tool decides, by comparing the delta rows with what was approved:
   - **No delta row changed** (wording elsewhere, code facts, design details, affected areas, assumptions, tasks): an **amendment**. Record it: `python <skill folder>/tools/check.py <project root> --amend --note "what and why"`. No approval needed; the review log keeps the note. Ticking a task and its `files:` are progress, not edits.
   - **A delta row changed, was added or removed:** set the next version number in `proposal.md`, Status "Draft", fix the documents, run `--gate 2`, show the short summary and ask for approval again, recorded with `--approve change`. The earlier approval stays in the log. Then tell the agents which version counts.
4. **IDs.** New rules, criteria and non-goals take their number from `check.py --next-id`. A dropped item is REMOVED, never renumbered or reused.
5. **A living row changed under you** (DELTA010: another change was archived and touched a row this change modifies or removes): read the new living row, rebase your delta on it (a MODIFIED row repeats the new living text with your edit), and approve again.
6. After a change of an approved document, tests and code that were written from the old version may be wrong. Say which tasks and tests are affected (`check.py --trace <ID>`) and fix them through the normal agents.
