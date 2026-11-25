# Concepts

## Living specs and capabilities

A **capability** is one area of behaviour: `checkout`, `auth`, `search`. Each has a **living spec**,
`.tracespec/specs/<capability>/spec.md`, that says how it behaves **now**: its rules, its acceptance criteria, its non-goals, and the
rules that were withdrawn. Nobody edits a living spec by hand. It changes only when a change is archived.

## Changes and deltas

A **change** is the unit of work, one folder under `.tracespec/changes/<change>/`:

| File | Holds |
|---|---|
| `proposal.md` | The request, the goal, the questions with answers word for word, the assumptions |
| `specs/<capability>/spec.md` | The **delta**: only what differs from the living spec |
| `design.md` | Existing code facts, design decisions, the interfaces the tests call, the affected files |
| `tasks.md` | A checkbox list, one line per task, with what each serves |

A delta has three sections. **ADDED** rows are new. **MODIFIED** rows repeat an existing row with its full new text and the same ID.
**REMOVED** rows give a reason and what callers do instead; the rule moves to the spec's "Withdrawn" table and its ID is never reused.
Archiving merges the delta into the living spec. A **small** change keeps everything in one `proposal.md`.

## Rules, criteria and IDs

- A **rule** (FR for behaviour, NFR for a limit such as speed or size) says what the system does.
- An **acceptance criterion** (AC) is a concrete example with real values: *given this, when that, then exactly this*. Every rule needs
  at least one; every criterion names the rule it covers.
- A **non-goal** (NG) says what a capability deliberately does not do.

FR, NFR, AC and NG numbers are **project-wide counters** (`check.py --next-id AC` hands out the next free one) and are never reused or
renumbered. Questions, goals, assumptions, tasks and design decisions are numbered per change.

## Tests carry the criterion number

A test is tied to its criterion by the criterion's number **in its name**: `test_AC31_rejects_empty_cart`, `it("AC31 rejects an empty
cart")`. `AC31`, `AC_31` and `AC-31` all count. This is deliberately language-neutral. The checker reads the names from a real test
run, so a number in a comment does not count and a skipped test does not count.

## Red before green

New and modified criteria need a test that **fails first**, for the right reason (missing behaviour or a missing interface, not a
typo in the test). A *modified* criterion whose existing test still passes is rejected: that test checks the old behaviour. A removed
criterion's tests must be deleted.

## Two agents, who never see each other's work

`tracespec-test-writer` reads the documents and the existing tests, never the code. `tracespec-coder` reads the documents and the
code, never the tests. A hook (`guard.py`) enforces both, and keeps both away from the protected paths. Tests run only through
`results.py`, which prints test names, criterion numbers and pass or fail, never test or code text. So when a test passes, the code
does what the **documents** say, not what the test's author expected the code to do. A third, fresh agent reviews at the end.

## What the tool decides

You (and the agents) never get to say "covered". `check.py` derives it from the tables in the documents, the task list, git, and a real
test run. At each gate it refuses with a finding code when something is wrong ([the full list](commands.md#finding-codes)):

1. every rule has a criterion, every criterion covers a rule, every rule and decision names its source;
2. every criterion has a test in the run, and every new test names a criterion;
3. every added or modified criterion and every design decision is in a task;
4. a modified criterion has a failing test; nothing fails afterwards; every task is ticked;
5. no changed file lies outside the change's "Affected areas";
6. the developer overview exists, is complete, and names only components that exist.

## The trace

For each capability the tool keeps a graph, in a binary store you query rather than read:

```
external reference ─► goal / question ─► rule ─► criterion ─► test
                                            └──► task ─► code symbol
```

Code links are **symbols** (a function, method or class) with a hash of their own text, so editing an unrelated function in the same
file flags nothing. See [Customization](customization.md#symbols) for how symbols are found. Ask the graph with `trace`:
`/tracespec trace test_AC31_rejects_empty_cart`, `... trace shop/cart.py:120` (why does this line exist?), `... trace SHOP-31` (what
was built for a ticket?).

## Baseline and live layer

- The **baseline** (`trace.db` per capability, plus the hash-chained `history.jsonl`) is written only at archive or reconfirm. It is
  what was true when the change shipped.
- The **live layer** (`.tracespec/cache/`, local) is what is true now: current hashes and symbols, and the last test results. It syncs
  at the start of every command. A recorded result is marked **stale** the moment something it depended on changes.

## Audit, drift and reconfirm

`check.py --audit` compares the working tree with the baseline and reports drift: a spec edited by hand, a linked symbol or test that
changed, was deleted or moved, a criterion with no passing test. Each finding names the rules and criteria involved. Resolve it on
purpose: if behaviour changed, propose a change; if it did not (a refactor), `--reconfirm` works only when every criterion of the
capability passes. A moved or renamed symbol is recognised by its text. The audit is **tamper-evident, not tamper-proof**.

## Tiers and approvals

There is one developer approval per change: the proposal. A **small** change (about three rules or fewer, about three files, one
capability) is one document. Edits to an approved proposal that change no delta row are recorded as **amendments** and need no new
approval; a changed delta row needs a new version approved again. Archive closes automatically when everything is clean.

## The developer overview

Everything under `.tracespec/` is for the agents and needs no review. Each change also gets **one** file for people,
`docs/features/<change>.md`: purpose, design and key components (with real paths, checked), short and with nothing generated.
It is written from the code that was actually built.
