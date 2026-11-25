# TraceSpec

**Traceable spec-driven development for Claude Code.** An automated requirements traceability matrix combined with
acceptance-test-driven development, run by agents.

Every requirement gets acceptance criteria written first. Every test comes from a criterion. Every piece of code comes from a
failing test. A tool, not a model, proves that chain, records it from ticket down to the function, and flags it when code, tests
or specs drift away from it later.

```
explore ─► propose ─► you approve ─► apply ─► verify ─► archive
 (talk)    questions    once         tests ✗    review    deltas merge into
           proposal                  (agent A)             the living specs,
           deltas                    code ✓                locked and audited
           design                    (agent B)
           tasks
```

## Why

- **Agents build against a written contract**, and you get proof afterwards, not "the agent said it works".
- **Tests and code are written by different agents** that never see each other's work (enforced by hooks), so they can only agree
  through the specification.
- **Coverage is decided by a checker** from a real test run: a requirement is covered when an acceptance criterion names it and a
  test carrying that criterion's number ran and passed. The model never gets to say "covered".
- **One decision from you.** You answer questions and approve the proposal once. Everything else is a check that passes, or refuses
  with a reason.
- **It stays true.** After a change ships, edits made outside the process show up as findings that name the rules and tests to
  revisit.

## Install

You need [Claude Code](https://claude.com/claude-code) and Python 3. Nothing else is required (git and
[universal-ctags](https://ctags.io) are optional, see below).

```bash
git clone https://github.com/knrl/tracespec.git
cd tracespec
python install.py          # skill -> ~/.claude/skills/tracespec, agents -> ~/.claude/agents
```

or clone straight into the skills folder and install only the agents:

```bash
git clone https://github.com/knrl/tracespec.git ~/.claude/skills/tracespec
python ~/.claude/skills/tracespec/install.py
```

**Restart Claude Code** afterwards: skills and agents are read when a session starts. `python install.py --claude-dir DIR` installs
somewhere other than `~/.claude`. Updating is the same command again.

## Use it

Open Claude Code in the project you want to change.

```
/tracespec add a 10% discount at checkout for carts over 100, not for gift cards
```

| Verb | What happens |
|---|---|
| `explore <topic>` | Read-only thinking partner. Writes nothing unless you ask. |
| `propose <request>` | Discovers the project (first time), asks 2–3 questions at a time, writes the change folder in one pass, and stops for your **one approval**. |
| `apply` | Skeleton, then tests that must fail first (agent A), then code (agent B), task by task. A new session resumes at the first unchecked task. |
| `update` | Revises the documents: an amendment, or a new version approved again. |
| `verify` | Converges code against the documents, gets an independent review, writes the developer overview. |
| `archive` | Merges the deltas into the living specs, writes the trace baseline and a hash-chained ledger line, moves the change to the archive. |
| `audit` | Finds drift in specs, code and tests, and says how to resolve it. |
| `trace <anything>` | Asks the store how a rule, criterion, test, task, file, symbol or ticket relates to the rest. |
| `list` · `show` · `view` | Changes with progress, a delta view, a one-screen dashboard. |

A bare `/tracespec <request>` means `propose`. A small change (about three rules or fewer) is one document with one approval.

### Ask the trace

```
/tracespec trace test_AC31_rejects_empty_cart
```
```
^ from  question add-cart/Q-3  ...
^ ref  JIRA-482
rule FR-12 [checkout]  An empty cart cannot be checked out
  covers  criterion AC-31  total([]) is rejected   <run: PASS (fresh)>
    serves  task add-cart/T-2  Reject empty cart
      built by  code shop/cart.py::checkout   <ok>
    ==> verifies  test tests/test_cart.py::test_AC31_rejects_empty_cart   <ok>
```

Targets: a rule or criterion ID, a test name, a task, a file, `file::symbol`, `file:line` ("why does this code exist?"), an external
reference such as a ticket, or a capability. `--up`, `--down`, `--story`, `--depth`, `--limit`, `--json`, `--mermaid` shape the answer.
Code and tests show `ok`, `CHANGED since the last archive` or `MISSING`; a criterion shows its last run and whether it is stale.

## What lands in your repository

| Where | What | Who reads it |
|---|---|---|
| `.tracespec.json` | State and layout (which paths are tests and code, the test command) | the tool |
| `.tracespec/specs/<capability>/` | The **living specs**, a binary trace baseline (`trace.db`) and a hash-chained ledger (`history.jsonl`) | the tool and the agents |
| `.tracespec/changes/<change>/` | A change in flight: proposal, delta specs, design, tasks. Archived changes move to `changes/archive/`. | the agents |
| `.tracespec/cache/` | Local live layer. Gitignored by its own `.gitignore`. | the tool |
| `docs/features/<change>.md` | **One short overview per feature**: purpose, how it fits the codebase, architecture, key components, data flow | **you** |

Commit `.tracespec/` (the baseline and ledger are what make the audit work in CI) and `docs/features/`. Nobody has to review the
files under `.tracespec/`; your review of a proposal is a summary shown in the chat.

## How it works

- **Living specs and deltas.** `.tracespec/specs/<capability>/spec.md` says how a capability behaves now. A change states only what
  differs (ADDED, MODIFIED, REMOVED rules and criteria). Archive merges them. IDs (FR, NFR, AC, NG) are project-wide and never reused.
- **Red before green.** A new criterion needs a test that fails first. A *modified* criterion whose existing test still passes is
  rejected, because that test checks the old behaviour.
- **Code links are symbols, not files.** A link points at a function, method or class with a hash of its own text, so editing an
  unrelated function in the same file flags nothing. Python is resolved exactly (`ast`); other languages use universal-ctags if it is
  installed, otherwise indentation regions (approximate).
- **Optional external references.** Put `Ref: JIRA-482` in a proposal header, or a Ref column on a goal, to tie the chain to a ticket
  or issue. `layout.refPattern` and `layout.refRequired` can enforce it. Teams without a tracker leave it out.
- **Tamper-evident, not tamper-proof.** The ledger holds the hash of the previous line, of the spec and of the trace baseline, so
  edits outside the process break the chain visibly. Anyone with write access can still rewrite everything; protect `.tracespec/`
  with code owners and run `check.py --audit` in CI.
- **Language-neutral.** Tests are run through whatever command your project uses, as long as it can write JUnit XML (pytest, vitest,
  jest-junit, gotestsum, Maven, Gradle, dotnet). A test is tied to its criterion by the criterion number in its name
  (`test_AC31_...`, `it("AC31 ...")`).

## Limits

- The checker proves each criterion has a passing test and that the chain is intact. It cannot prove the criteria are the right ones.
- A weak test with the right name passes the checker. The independent review is the only guard against that.
- No call graph: a change in a function does not flag the functions that call it.
- A comment edited inside a function changes that function's hash.
- Symbols from the indentation-region fallback are approximate. The universal-ctags path is covered by a parser test only.
- Tests are not run automatically (they are slow). A recorded result is marked stale when something it depended on changes.
- Developed and tested with Python 3.14 on Windows. Other versions and operating systems are untested; the code uses only the
  standard library.

## Develop

```bash
cd tools
python -m unittest discover -s . -p "test_*.py"
```

| Path | Contents |
|---|---|
| `SKILL.md`, `process.md` | The skill and the process |
| `workflows/` | One document per verb, plus the build loop |
| `templates/` | Proposal, delta, design, tasks, overview, and the two agent definitions |
| `tools/` | `check.py` (checks and commands), `results.py` (safe test runner), `guard.py` (the agents' hook), and the trace store and graph modules, with their tests |
| `install.py` | Installer |

## License

MIT. See [LICENSE](LICENSE).
