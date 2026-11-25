---
name: tracespec
description: TraceSpec (traceable spec-driven development) is an automated requirements traceability matrix combined with acceptance-test-driven builds, run by agents. It guides a developer through changing an existing project one change at a time, with as few stops as possible - explore, propose (clarify, then a change folder of proposal, delta specs, design and tasks, approved once), apply (tests written from the specs by one agent, code by another), verify (independent review, plus one concise developer overview per feature), archive (deltas merge into living specs that are locked and audited for drift). All agent-oriented files live in .tracespec/. Works with any language or framework. Use for "/tracespec <request>", "/tracespec explore|propose|apply|update|verify|archive|audit|trace|list|view", or when someone wants to start, continue or change work built with this process.
argument-hint: [explore|propose|apply|update|verify|archive|audit|trace|list|view] <request or change name>
---

# TraceSpec: traceable spec-driven development

> **An automated requirements traceability matrix combined with acceptance-test-driven development, run by agents.** Every requirement has acceptance criteria written first, every test comes from a criterion, every piece of code comes from a failing test, and a tool, not a model, proves the chain and keeps it true after the change ships.

Arguments: `$ARGUMENTS`. The first word may be a verb (below); a bare request means **propose**; no argument means continue the active change, or ask what to do.

You take a request for an **existing project** through a change: explore it, propose it, apply it, verify it, archive it. The specs live in two places. **Living specs** (`.tracespec/specs/<capability>/spec.md`) say how each capability behaves now; they change only by archiving a change. A **change** (`.tracespec/changes/<change>/`) says what differs, as a delta. The delta is approved before any test, the tests are written before the code, by **different agents** that never see each other's work, and a tool, not you, decides whether every rule is covered by a passing test.

**Two kinds of files.** Everything the agents work from (living specs, changes, locks, ledgers, matrices) lives in the dedicated directory `.tracespec/` and needs no human review. For people there is exactly **one** file per change: the **developer overview** `docs/features/<change>.md` (purpose, how it fits into the codebase, architecture, key components, data flow, and a generated facts block). It is written at the end of the change from the code that was actually built, and the developer reads it to build a mental model of the feature.

**The developer is stopped as little as possible:** the answers, and one approval (the proposal). Everything else is a check a tool decides. Read [process.md](process.md) once per conversation.

The user is a developer. Talk like a colleague, briefly. Use the language the developer writes in; documents too, in short sentences with one word for one thing. Never make them read process machinery; the checks in this file are your job, done in the background.

## The verbs

| Verb | Workflow | What it does | The developer |
|---|---|---|---|
| `explore <topic>` | [workflows/explore.md](workflows/explore.md) | Read-only thinking partner; writes nothing unless asked | talks |
| `propose <request>` | [workflows/propose.md](workflows/propose.md) | First time: discover the project. Clarify. Write proposal, delta specs, design, tasks in one pass. Check. | answers, then **approves once** |
| `apply [change]` | [workflows/apply.md](workflows/apply.md) | Skeleton, tests (fail first), then code task by task; resumable by checkbox | nothing, unless a spec gap needs a decision |
| `update [change]` | [workflows/update.md](workflows/update.md) | Revise the documents: an amendment, or a new version approved again | confirms |
| `verify [change]` | [workflows/verify.md](workflows/verify.md) | Converge, independent review, write the developer overview, readiness report | nothing |
| `archive [change]` | [workflows/archive.md](workflows/archive.md) | Merge the deltas into the living specs, lock them, refresh the overview's facts, move the change to the archive | nothing when clean |
| `audit` | [workflows/audit.md](workflows/audit.md) | Find drift in the living specs, tests and code; resolve it on purpose | decides how to resolve |
| `trace <anything>` | [workflows/trace.md](workflows/trace.md) | Ask how a rule, criterion, test, task, file, symbol or ticket relates to the rest | reads |
| `list` · `show <change>` · `view` | below | Changes with progress, a delta view, a one-screen dashboard | reads |

`list`, `show` and `view` are `check.py --list`, `--show <change> [--diff]` and `--view`: run them and show the output.

Nothing past archive. Committing, pull requests and deployment are not part of this process.

## Tiers: how much process a change gets

You propose the tier in propose; the developer can change it. It is stored as `tier` in the change's state.

| Tier | When | What changes |
|---|---|---|
| **small** | About 3 rules or fewer (FR and NFR together), about 3 files, one capability, no data migration | One document: `proposal.md` holds the request, the questions, the delta, the design and the tasks ([templates/small_proposal.md](templates/small_proposal.md)). No `specs/`, `design.md` or `tasks.md`. |
| **standard** | Anything larger | `proposal.md`, `specs/<capability>/spec.md` per capability, `design.md`, `tasks.md` |

The agents, the coverage checks, the trace store and the audit are the same in both tiers. If a small change grows past 3 rules the check warns (TIER001): switch it to standard.

## Every time you are started

1. **Find the project root:** the git top folder of the current directory, or the current directory. Look for `.tracespec.json` there. None: the first change here; propose does the discovery.
2. **Which change?** The argument, or `activeChange`. A new request while another change is unfinished: say so and ask which to work on.
3. **Read where it stands:** `.tracespec.json`, and the change's documents. Run the background check for the phase. **The files win** over the state file: tell the developer what you found, fix the state to match, and go on. **Never assume an approval that is not recorded**: ask for it again.
4. **Audit before you start** a propose or an apply: `check.py <project root> --audit --no-run`. Report drift; never hide it (see [workflows/audit.md](workflows/audit.md)).
5. **Say in one or two lines** where it stands: `{Change} · {phase} · {what is open} · tasks {done}/{total}`. For example: "add-discount · propose · 3 questions left · about 5 minutes".
6. **Load only what you need:** the workflow file for the verb, the templates when it says so.
7. **Follow the workflow.** Move on to the next phase in the same turn when no developer decision is needed (propose runs on into apply after the approval; apply into verify; verify into archive when clean). Stop only where the workflow says.

## Talking with the developer

- **Ask 2–3 questions per turn**, each with a concrete example from their own request or code.
- Use **AskUserQuestion** when a question has likely answers: 2–4 options, your proposal first marked "(Recommended)" when you have a reason. Each question must stand on its own. Put the ID (`Q-4`, `ASM-2`) in the header. Open questions (what it is for, what must never happen) are plain text, no options.
- **Recording a choice:** write the chosen option word for word, plus anything typed, marked "(chosen from options)".
- At the start of a phase, say honestly what it holds ("about 8 questions: 15 minutes"). At a natural break, say so.

## Rules you never break

1. **Ask 2–3 questions per turn.** Never dump a list on the developer.
2. **Never answer for the developer.** If you do not know, it is a question (Q-n), a usual choice from the repo's own conventions (ASM-n) or an open item (OPEN-n), each for them to confirm.
3. **Record answers word for word, as soon as they are given.** A correction is a new row; the old answer stays.
4. **Everything has a source.** Every FR, NFR, D and G names the Q, ASM, OPEN or G it came from. If there is no source, do not write it.
5. **IDs are project-wide and never reused or renumbered.** The next free ID comes from `check.py --next-id FR|NFR|AC|NG`. A dropped item is REMOVED, which withdraws it.
6. **Never record an approval yourself.** Only the developer's own yes counts, and `check.py --approve` records it.
7. **No test and no feature code before the proposal is approved.** Reading the project and the baseline test run are fine.
8. **The documents are the truth.** If they cannot be built or tested as written, stop. Do not improvise or work around them: change them ([workflows/update.md](workflows/update.md)).
9. **The living specs are written only by archive.** Never edit anything under `.tracespec/specs/`. A change proposes its edits as a delta; the audit flags any other edit.
10. **Delta rows change only through approval.** Edits that change no delta row are amendments the tool records. Everything else is a new draft version, approved again.
11. **The one who builds does not judge.** The tests and the code are written by two separate agents (`tracespec-test-writer`, `tracespec-coder`) that never see each other's work. You coordinate them and never pass test code to the coder or code to the tester. A third, fresh reviewer checks the result.
12. **Report truthfully.** Failing tests, failing checks, skipped steps and open assumptions are stated plainly.
13. **Fit the project.** Follow its structure, style and conventions. No unrelated refactor, no new dependency or public name the documents do not name. The tool checks that changed files stay inside "Affected areas".
14. **Coverage is decided by the tool, never by you.** A requirement is covered only when the tool says so (`check.py --matrix`, or `--trace` for the live view). Never write or say "covered" from your own reading. Never edit the trace store, a ledger or an exported matrix.
15. **One file is for people; everything else is not.** Do not put agent material in `docs/`. The developer overview (`docs/features/<change>.md`) is short, in plain words, and written from the built code, not copied from the specs. It is the only document the developer is expected to read.
16. **Skipping a check or a step:** say what it protects. If the developer insists, write one line in the review log (date, what, why). Never skip silently.
17. **Do not commit, push or open pull requests** unless the developer asks. A feature branch is created only after a yes.

## Approvals

There is one, and the tool does the bookkeeping.

1. **Show a short summary** of what is approved, in the developer's terms: the goal; per capability what is added, changed and removed; each rule with its criterion in one line; every assumption and usual choice they are accepting; the affected files. Keep it to one screen. Do not repeat the documents. **The developer is not asked to read the files under `.tracespec/`**: this summary, in the chat, is their review.
2. **Ask one question** ("Approve the proposal v{x}?", options "Yes, approve" / "No, I want changes"). A plain yes to that question is an approval. A yes with a request in it is not: apply the request, then ask again.
3. **Record it with the tool**, never by hand: `check.py <project> --approve change --by "<name>" --words "<their exact words>"`. The tool runs the checks first and **refuses on any error**. It writes the version, fingerprint, the delta-row hashes, the hashes of the living rows being modified or removed, the state, the Status line and the review-log row.
4. **Archive closes the change automatically** when `check.py <project> --archive --ir-open 0` passes. Ask for a build approval (`--approve build`) only if the developer wants to look first, or a review finding needs a decision.
5. A role-played or passed-on answer is never recorded as an approval.

### Changing an approved proposal
The tool compares the delta rows with what was approved. **Nothing in them changed:** an amendment, recorded with `--amend --note "..."`, no approval. **A delta row changed, was added or removed:** next version number, Status "Draft", approve again. And if another change was archived under you (DELTA010), rebase your delta on the new living row and approve again. Details in [workflows/update.md](workflows/update.md).

## Background check

`tools/check.py` checks documents and tests mechanically and writes the files only it may write. **You run it; the developer never has to.** It needs only Python.

```
python <skill folder>/tools/check.py <project>                         # during work
python <skill folder>/tools/check.py <project> --gate <n>              # 1 questions, 2 proposal, 3 tests, 4 build, 5 close (3, 4 and 5 run the tests)
python <skill folder>/tools/check.py <project> --change <name>         # a change other than the active one
python <skill folder>/tools/check.py <project> --baseline              # discovery: run the suite, record existing tests and uncommitted files
python <skill folder>/tools/check.py <project> --approve change|build --by NAME --words "..."
python <skill folder>/tools/check.py <project> --amend --note "..."
python <skill folder>/tools/check.py <project> --task-start T-n        # before a task
python <skill folder>/tools/check.py <project> --task-done T-n         # ticks it (criteria must pass), records its files
python <skill folder>/tools/check.py <project> --archive --ir-open N
python <skill folder>/tools/check.py <project> --audit [--no-run] [--ci]
python <skill folder>/tools/check.py <project> --reconfirm <capability|ID>... --note "..."
python <skill folder>/tools/check.py <project> --trace <target> [--up|--down|--story] [--depth N] [--limit N] [--json|--mermaid]
python <skill folder>/tools/check.py <project> --sync | --install-hooks                 # the live layer; git hooks that run --sync
python <skill folder>/tools/check.py <project> --matrix | --export FILE [--living]      # a matrix, printed or written on request
python <skill folder>/tools/check.py <project> --overview               # create docs/features/<change>.md, refresh its generated facts
python <skill folder>/tools/check.py <project> --list | --view | --show <change> [--diff] | --next-id FR|NFR|AC|NG
python <skill folder>/tools/check.py --fingerprint <file>   |   <project> --fingerprint code   |   --detect <project>
python <skill folder>/tools/results.py <project> [AC-n ...]            # run the tests; one safe line per test
```

When: on every start, after you change a document, after every task, before every gate. Exit 0: say nothing about it. Findings for `agent`: fix them in the source document and run again. Findings for `developer`: tell them in plain words. **A gate cannot pass with errors.** If Python is not available, do the consistency check below by hand and say so once.

### What the tool decides

Nothing here is judged by a model. The verdicts come from the tables in the documents, the task list, git, a real test run (JUnit XML), and the trace store.

| Check | Rule | Gate |
|---|---|---|
| SPEC001 / SPEC004 / SPEC014 | After the merge, every rule has a criterion and every criterion covers a rule of its capability | 2 |
| SPEC005 | Every FR, NFR and D names its source (Q, ASM, OPEN, G) | 2 |
| SPEC007 / SPEC008 / SPEC009 / SPEC013 | No open ASM or OPEN; the required sections exist; no TBD or placeholder; "Affected areas" lists a path | 2 |
| DELTA001 / 002 / 005 / 011 | ADDED must be new and unique project-wide; MODIFIED and REMOVED must exist; no clash with another active change | 2 |
| DELTA008 / 009 / 012 | Rows have their columns; a new capability has a Purpose; the change has delta rows | 2 |
| SPEC010 | An approved delta row changed: new draft version, approve again | any |
| SPEC012 | The approved proposal was edited but no delta row changed: `--amend` (warning; an error at gate 5) | any |
| DELTA010 | A living row this change modifies or removes changed after approval: rebase and approve again | 3 |
| TIER001 (warning) | A small-tier change touches more than 3 rules | 2 |
| TASK001 / 002 / 003 | Every ADDED or MODIFIED criterion and every D is in a task; a task serves nothing undefined | 3 |
| TEST001 | Every criterion has a test **in the run** whose name carries its AC number. A mention in a comment, or a skipped test, does not count | 3 |
| TEST002 | No test names a criterion that is undefined or that this change removes | 3 |
| TEST005 | A **new** test (not in the baseline) must name an AC. Existing tests are exempt | 3 |
| TEST006 (warning) / TEST007 | A new test that already passes: the test writer must explain. **A MODIFIED criterion whose tests still pass is an error** | 3 |
| TEST003 / TEST004 / TASK004 | Nothing fails (except `knownFailing`); every criterion passes; every task is ticked | 4 |
| OVERVIEW001–007 | The developer overview `docs/features/<change>.md` exists, has purpose, how it fits, architecture, key components and data flow with real content, no placeholders and a facts block, and every path in its component table exists (a warning above 120 lines) | 5 |
| CHG001 | No changed file outside "Affected areas" (tests, `docs/`, `.tracespec/`, build folders and files already dirty at the baseline are exempt; skipped without git) | 4 |
| REF001 / REF002 | Only when `layout.refRequired` or `layout.refPattern` is set: every goal has an external reference, and each matches the pattern | 2 |
| LINK001 (warning) | An ADDED or MODIFIED rule or criterion has no code recorded on its tasks (use `--task-start` and `--task-done`) | 4 |
| DRIFT-SPEC / DRIFT-CODE / DRIFT-TEST / UNCOVERED | The audit: the living specs, the linked code symbols and tests, against the baseline | audit |

There are **no matrix files**. `check.py --matrix` prints the change's matrix, `check.py --export FILE [--living]` writes Markdown on request, and `--trace` answers any single question from the live graph. The overview's facts block pulls its counts from the same checks.

## Living specs, the trace store and the ledger

- **`.tracespec/specs/<capability>/spec.md`**: Purpose, Behavior rules (FR, NFR), Acceptance criteria (AC), Non-goals (NG), Withdrawn. Written only by archive.
- **`trace.db`** (binary, one per capability, committed): the **baseline**. A graph of nodes and links with a hash for every row, symbol and file as at the last archive or reconfirm. The chain it holds: external reference → goal or question → rule → criterion → test, and rule or criterion → task → code **symbol**. It is read through `--trace`, never by hand, and written only by `check.py`.
- **`history.jsonl`**: append-only ledger. Each line holds the hash of the line before it, the hash of `spec.md` and the hash of `trace.db`, so a hand edit of the spec, the database or the ledger breaks the chain.
- **`.tracespec/cache/current.db`** (local, never committed; its folder gets its own `.gitignore`): the **live layer**: the current hash and symbols of every code and test file, the last test results, the task snapshots. Derived and rebuildable.
- All of it is in the protected paths (`.tracespec/**`, `docs/features/**`): the build agents can read it but never write it. The audit ([workflows/audit.md](workflows/audit.md)) is tamper-evident, not tamper-proof.

### Code links are symbols, not files
A link points at a symbol (a function, method or class) together with a hash of its own text, so an edit elsewhere in a shared file does not flag unrelated rules. Three resolvers, best first: Python's `ast` (exact); `universal-ctags` when it is installed (other languages); indentation regions, named by their first line (anything else, approximate but far tighter than a file). `--task-start` notes the hash of every code symbol; `--task-done` records the symbols that are new or changed on the task line (`symbols:`), and archive turns them into links. A symbol that was moved or renamed is recognised by its text. Not tracked: the call graph (a change in a callee does not flag its callers); a comment counts as part of its symbol's text.

### The live layer: why nothing is a snapshot
`check.py` syncs the live layer at the start of every command. It is incremental: a file whose size and modification time are unchanged is not even re-read, and symbols are re-resolved only for a file whose content changed (about a tenth of a second for 2,500 files when nothing changed). `--install-hooks` adds git hooks (post-commit, post-merge, post-checkout; they never block) and prints an optional Claude Code PostToolUse snippet, so the layer follows edits made between commands. There is no background process. Tests are not run automatically, because that is slow: a recorded result is marked **stale** as soon as a symbol or file it depended on changes, and fresh again after the next run.

### Asking the store: `/tracespec trace <anything>`
`check.py <project> --trace <target>` walks the graph. A target is a rule or criterion ID (`FR-12`, `AC-31`), a test name or part of it, a task (`T-2`, or `add-discount/T-2`), a file, `file::symbol`, `file:line` (why does this line exist?), an external reference (`JIRA-482`), or a capability. Direction: `--up` toward the ticket, `--down` toward the code, `--story` the whole of the rule it belongs to; with none of them a test, task or code target shows its whole story, and the others show both directions. `--depth`, `--limit`, `--json` (for agents) and `--mermaid` (a diagram) shape the answer. Every node shows its state: code and tests `ok`, `CHANGED since the last archive` or `MISSING`; criteria their last run, fresh or stale. A change that is still in flight is in the graph, marked as such. Details in [workflows/trace.md](workflows/trace.md).

### External references (optional)
Teams that use a tracker can tie the chain to it; teams that do not simply leave it out. Put `Ref: JIRA-482` in the proposal header to cover every rule the change adds or modifies, or fill a **Ref** column on a goal or question row (rules that cite that goal inherit it). A reference is any text (a ticket, an issue, a URL), several separated by commas. `layout.refPattern` (a regex) validates them and `layout.refRequired: true` makes a goal without one an error (REF001, REF002); both default to off. Then `--trace JIRA-482` lists everything built for the ticket, down to the tests and code.

## State file: `.tracespec.json` (project root)

```json
{
  "process": "tracespec", "processVersion": "2.0",
  "activeChange": "add-discount",
  "layout": {
    "tests": ["tests/**"], "code": ["src/**"],
    "protected": [".tracespec.json", ".tracespec-check.json", ".tracespec-junit.xml", ".tracespec/**", "docs/features/**"],
    "overviewDir": "docs/features",
    "refPattern": "", "refRequired": false,
    "testCmd": ["python", "-m", "pytest", "-q", "--junitxml=.tracespec-junit.xml"],
    "testEnv": {}, "junit": ".tracespec-junit.xml", "knownFailing": []
  },
  "checks": [ { "name": "lint", "cmd": "ruff check ." } ],
  "changes": {
    "add-discount": {
      "title": "Add discount", "tier": "standard", "phase": "propose",
      "spec": { "status": "draft" },
      "gates": [],
      "baselineTests": ["set by check.py --baseline"], "baselineDirty": ["set by check.py --baseline"],
      "returnTo": null
    }
  }
}
```

- `phase`: `propose`, `apply` (after the approval), `archived` (with `archivedAs`). `spec` is filled by `--approve change`: `version`, `status: "approved"`, `approvedBy`, `approvedOn`, `fingerprint`, `rows` (hashes of the delta rows) and `baseRows` (hashes of the living rows being modified or removed). `amendments` lists the recorded amendments.
- `layout` is read by the tools. Globs use `*` (inside a folder) and `**` (across folders); a plain folder name means everything below it. `tests` is hidden from the coder and the only place the tester writes; `code` is hidden from the tester; a path in both counts as a test; neither agent writes `protected`. `testCmd` runs the whole suite and writes JUnit XML to `junit` (a file or glob). `knownFailing` holds the exact names of tests that already failed in the baseline. Change `layout` only with the developer, and say so in the log.
- `returnTo`: `{ "phase": "propose", "reason": "spec gap" }` while work went back to an earlier phase. Clear it when that phase is done.

`.tracespec.json` is for you and the tools. `.tracespec/` holds every agent-oriented file: commit it too (the lock and the ledger make the audit work in CI), but nobody has to review it. `docs/features/` is for people, one overview per change.

## Going back

A spec gap found in apply, or a finding in verify, sends the work back to [update.md](workflows/update.md): amend or re-approve, then return. Batch the small gaps into one change.

## Agents

`tracespec-test-writer` and `tracespec-coder` live in `~/.claude/agents/`, installed from [templates/agents/](templates/agents/) by apply, with `{skill_dir}` replaced by this skill's folder. They are loaded when a session starts, so after installing, a new session may be needed. Their hook is [tools/guard.py](tools/guard.py). The coding loop is [workflows/build-loop.md](workflows/build-loop.md).

## Consistency check (by hand, when the tool cannot run)

Every ID a document names exists; every rule has a criterion after the merge; every criterion has a test whose name carries its ID; every ADDED or MODIFIED criterion and every D is in a task; no task or test changes behaviour the documents do not describe; no ASM or OPEN is open.
