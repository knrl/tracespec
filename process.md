# TraceSpec

**Traceable spec-driven development**: an automated requirements traceability matrix (RTM) combined with acceptance-test-driven development (ATDD), run by agents. Specs first, tests before code, a different agent for each, and a tool that proves the chain from ticket to function and flags drift afterwards.

## The process

One request, one **change**, against **living specs**. The change is explored, proposed, applied, verified and archived. Archiving merges its deltas into the living specs, which are then locked and audited.

```
                  living specs  .tracespec/specs/<capability>/spec.md  (+ trace.db, history.jsonl)
                      ▲   │ read                                           ▲ merge, lock, ledger
                      │   ▼                                                │
explore ─► propose ─► you approve ─► apply ─► verify ─► archive ───────────┘
 (talk)    questions    once         skeleton   converge   close, move to
           proposal     (the one     tests ✗    review     .tracespec/changes/archive/
           deltas       stop)        code ✓
           design
           tasks
                                       audit ◄── runs at the start of propose and apply; CI can run it too
```

## How much stopping
Only the proposal is approved by the developer. Every other gate is a tool check: it passes and the work goes on, or it refuses with a finding. Archive closes automatically when clean. A small change (about 3 rules or fewer) is one document with exactly one stop.

## Two kinds of files
- **For the agents: `.tracespec/`.** Living specs, changes, locks, ledgers and matrices. They are what the agents and the tool work from. Nobody has to review them; the developer's review is the short summary in the chat at the approval.
- **For people: `docs/features/<change>.md`.** One concise overview per change: purpose, how it fits into the existing codebase, architecture, key components, data flow. The narrative is written by the coordinator from the code that was built, and `check.py` refuses to close the change if it is missing, empty, a placeholder, or names a component path that does not exist. A generated facts block at its end (behaviour at a glance, where to look, how it is verified) is refreshed by the tool.

## Why this order
- **Clarify before the documents:** they must hold nothing that is a guess. Each gap is answered, taken from the repo or the living specs, or written down as an assumption the developer confirms.
- **Documents before tests:** they say what "right" is. They are what both build agents read.
- **Tests before code, by a different agent:** a test written by the one who writes the code checks that author's reading of the spec. Two agents, each blind to the other's work, can only agree through the documents. A test seen failing for the right reason shows it can fail.
- **A review by a third:** the builders do not judge their own work.
- **Deltas against living specs:** a change states only what differs, so a modified rule is visible as a modification, and a removed rule is withdrawn, never silently lost.
- **A trace store and an audit:** later edits to code, tests or specs outside a change become visible findings that name the rules and criteria to revisit, down to the symbol.

## Documents

Everything under `.tracespec/` is for the agents. Only the last row is for people.

| File | Written by | Holds |
|---|---|---|
| `.tracespec/specs/<capability>/spec.md` | archive | The living spec: rules, criteria, non-goals, withdrawn |
| `.tracespec/specs/<capability>/trace.db`, `history.jsonl` | archive, reconfirm | The baseline graph (binary: links and hashes down to code symbols) and the hash-chained ledger |
| `.tracespec/cache/current.db` | every `check.py` command | The live layer (local, not committed): current hashes and symbols, last results, task snapshots |
| `.tracespec/changes/<change>/proposal.md` | coordinator | Request, goal, questions with answers word for word, never-happen walk, assumptions |
| `.tracespec/changes/<change>/specs/<capability>/spec.md` | coordinator | The delta: ADDED, MODIFIED, REMOVED rows |
| `.tracespec/changes/<change>/design.md` | coordinator | Existing code facts, decisions (D), interfaces the tests call, affected areas, risks |
| `.tracespec/changes/<change>/tasks.md` | coordinator, `--task-done` | Checkbox tasks with what each serves and the files it changed |
| `.tracespec/changes/<change>/build_loop.md`, `review_log.md` | coordinator, `check.py` | Coding attempts with evidence; approvals, amendments, review findings |
| **`docs/features/<change>.md`** | coordinator (narrative), `check.py` (facts) | **The developer overview: the one file for people** |

## IDs
Q (question), G (goal), NG (non-goal), FR / NFR (rule), AC (acceptance criterion), D (design decision), R (risk), ASM (assumption), OPEN (open question), T (task), IR (independent review finding). FR, NFR, AC and NG are **project-wide counters** (`check.py --next-id`); the others are per change. Numbers are never reused.

## The chain the tool follows
Q → FR/NFR → AC → test (the AC number is in the test's name) → pass. AC and FR → task → code symbols (a symbol with a hash of its text, not a file); a ticket, if the team uses one, sits above the goal. D → task. A break anywhere is an error from `check.py`, and the matrix shows it. After archive the same chain is hashed into the lock, and the audit compares it with the project.

## Roles
- **Developer:** answers, approves the proposal (and the build only when asked), reads the diff, commits.
- **Coordinator (the main agent):** runs the process, writes the documents, runs the checks, dispatches the agents.
- **tracespec-test-writer:** tests only; sees the documents, the living specs and the tests, not the code.
- **tracespec-coder:** code only; sees the documents, the living specs and the code, not the tests.
- **Reviewer:** a fresh agent in verify; sees the documents, the changes and the tests.
- **check.py:** decides coverage, scope, approvals bookkeeping, the merge, the trace store and the audit, and answers `--trace`.
