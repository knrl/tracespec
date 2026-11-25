# Best practices

How to get the most from TraceSpec once you have made your first change. Each practice says why it matters, so you can judge when it
does not apply to you. Terms are in the [glossary](glossary.md).

## Where your effort counts

**Review the proposal summary carefully.** Approving it is your one decision. The checker proves that every criterion has a passing
test; it cannot tell whether the criteria are the right ones. If a rule is vague or a question was answered wrongly, fix it at the
proposal, where a change costs a sentence, not after the code exists.

**Make criteria concrete.** "Given item prices 100 and 250, when the cart is totalled, then the total is 350.0" gets a real test.
"The total is correct" gets a test that passes without proving much, and the checker accepts it because the name carries the right
number. The independent review in `verify` is the only guard against weak tests, so read its findings instead of skimming them.

**Keep changes small.** One behaviour per change. A small-tier change that touches more than three rules gets a `TIER001` warning:
split it, or move it to the standard tier. Small changes also make later drift findings precise, because each finding points at a
few rules instead of a dozen.

**Say what is out of scope.** A non-goal (`NG-n`) costs one line and stops an agent from building the thing someone might expect.
Anything the documents do not describe is a question for you, not a decision for the agent.

## Setting up a project

**Run `--doctor` first, and again after an upgrade.**

```bash
python ~/.claude/skills/tracespec/tools/check.py . --doctor
```

It checks Python, git, both agents, and the test command, and it asks the real guard hook to refuse a read of a hidden file. That
last check catches the failure that is easiest to miss: a hook that never starts, which silently turns the isolation off. For a new
project, `--init` writes `.tracespec.json` from what it finds.

**Make sure your test runner writes JUnit XML and that the layout is right.** Coverage is judged from a real test run, so the test
command and the paths in `layout.tests` and `layout.code` are the foundation. If tests and code sit in the same files, searches are
off for the build agents (see [Customization](customization.md)), so keep them in separate folders where you can.

**Record the baseline.** Step 0 runs your suite and records which tests exist and which already fail. Add a failing test to
`knownFailing` only as a deliberate decision, because every name there is excused from the gate.

**Commit `.tracespec/` and `docs/features/`.** The baseline and ledger are what make the audit work in CI and for teammates. Do
not hand-edit anything under `.tracespec/`; the tools write it, and an edit is reported as drift. Add `.tracespec-junit.xml` and
`.tracespec-check.json` to `.gitignore`.

## While building

**Start `apply` in a fresh session.** Progress lives in the checkboxes of `tasks.md`, so a new session resumes at the first unticked
task, and a clean context suits the build agents.

**Never relax a test to get a pass.** A test that looks wrong is a dispute: stop, and go back to the criterion with `update`. The
build loop allows three coding attempts per task for a reason; a fourth attempt without new evidence is a signal that the spec has
a gap.

**Do not edit tests and code in the same sitting as an agent task.** The two agents are kept apart so that they can only agree
through the written criteria. If you write both sides yourself, you lose that check for that change; say so in the review log.

**Add a ticket reference if you use a tracker.** Put `Ref: JIRA-482` in the proposal header. Then
`/tracespec trace JIRA-482` lists everything built for the ticket, down to tests and code.

## Keeping the human file useful

**Write the overview design first, and short.** About 30 lines: purpose, design, key components. Put the key decision and the
alternative that was rejected in the design section, because that is what a reviewer cannot recover from the code. Leave out
anything `--trace` already answers.

## After it ships

**Trace before you change risky code.** `/tracespec trace shop/cart.py::total` shows every rule, criterion and test that depends
on that function. This matters most for shared helpers, because the tool has no call graph: an edit inside a function does not flag
the functions that call it.

**Run the audit in CI.**

```bash
python tools/check.py . --audit --no-run     # hash checks only: fast, needs no test runner
python tools/check.py . --audit              # also runs the tests
```

Pin the TraceSpec version in your pipeline and see [Team workflow](team-workflow.md) for a full snippet. A pull request that edits a
linked function, a test or a living spec outside a change then fails with a finding that names the rules and tests to revisit.

**Choose the right response to drift.**

| What happened | Do this |
|---|---|
| Behaviour changed | `/tracespec propose` a change, so the spec, tests and code move together |
| Behaviour did not change (refactor, a fix inside the rules) | `check.py . --reconfirm <capability> --note "why"`; it works only when every criterion of the capability passes |
| The spec was edited by hand | Revert the edit, or redo it through a change |
| A test result shows `stale` | Run `--audit`; stale only means a linked symbol changed since the last run |

**Keep the live layer fresh between commands.** `--install-hooks` adds git hooks that run `--sync` after commit, merge and checkout.
They never block. Without them the layer is still refreshed at the start of every command, so this is a convenience, not a need.

**Resolve a `trace.db` merge conflict by taking either side.** It is binary and cannot be merged by hand. Run `--sync`, then
`--audit`; if spec and baseline still agree with the code, `--reconfirm` re-baselines it.

## Know the limits

- The checker proves coverage and an intact chain, not that the criteria are right and not that a test is strong.
- No call graph: a change in a callee does not flag its callers.
- A comment edited inside a function counts as a change to it.
- Tamper-evident, not tamper-proof: anyone with write access can rewrite the spec, baseline and ledger together. Git history and
  code review are the real protection.
- Symbols are exact for Python, good with universal-ctags, and approximate otherwise. Only the Python preset has been exercised, so
  for another stack check with `--doctor` that the JUnit report really is written.
