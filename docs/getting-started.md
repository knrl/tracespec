# Getting started

## What you need

- [Claude Code](https://claude.com/claude-code).
- Python 3.10 or newer. TraceSpec has no other dependencies.
- A project with a test runner that can write JUnit XML (pytest, vitest, jest with `jest-junit`, Go with `gotestsum`, Maven, Gradle,
  dotnet with a JUnit logger). For Python, `pip install pytest`. Step 0 of your first change runs the suite and tells you what is
  missing; if it cannot run, [Troubleshooting](troubleshooting.md) lists the usual causes.
- Optional: `git` (enables the scope check, finding CHG001, and git hooks; without it the check is skipped with a warning) and [universal-ctags](https://ctags.io) (better symbols for languages other
  than Python).

## Install

```bash
git clone https://github.com/knrl/tracespec.git
cd tracespec
python install.py
```

This copies the skill to `~/.claude/skills/tracespec` and writes the two agents (`tracespec-test-writer`, `tracespec-coder`) to
`~/.claude/agents/` with the right hook path. **Restart Claude Code**: skills and agents are read when a session starts. To update,
pull and run `python install.py` again.

## Your first change

Open Claude Code in the project you want to change, then type:

```
/tracespec propose add a 10% discount at checkout for orders over 100
```

Here is what happens, in order.

**1. Discovery (only the first time in a project).** The agent reads your project and tells you what it found: the stack, which folders
are tests and which are code, the command that runs your tests, and a baseline (how many tests exist and pass today). It writes
`.tracespec.json`. Correct anything that is wrong now; later steps rely on it.

**2. Questions, two or three at a time.** Expect options with a recommendation, and a few plain-text questions: what must never
happen, and one or two real input-and-result examples. The examples become acceptance criteria. Your answers are recorded word for word.
The agent skips questions your code already answers.

**3. The change folder.** The agent writes, in one pass, under `.tracespec/changes/<change>/`: the proposal, a delta spec (what is
added, modified or removed), a design, and a task list. It runs the checks and fixes its own errors before showing you anything.

**4. Your one approval.** You get a short summary in the chat, not the files: the goal, each rule with its criterion, the
assumptions you are accepting, and the files that will change. Answer "Yes, approve" or ask for changes. **This is the only approval
you give.**

**5. Apply.** One agent writes tests that must fail first (and the tool checks that they do, for the right reason). A different agent,
which cannot see those tests, writes the code, one task at a time. After each task the tool ticks the box only when the criteria it
serves pass. You can leave: a new session resumes at the first unchecked task.

**6. Verify and archive.** A fresh agent reviews the work against the documents. Then the tool merges the delta into the living spec,
writes the trace baseline and a ledger line, and moves the change to the archive. You get one closing report and one file worth
reading: `docs/features/<change>.md`.

You then read the diff, commit, and open your pull request. TraceSpec never commits or pushes.

## Start smaller, or start by thinking

- **Not sure what to build?** Start with `/tracespec explore <topic>`. It reads your code and thinks with you, and writes nothing.
- **A tiny change** (about three rules or fewer, one capability): the agent proposes the *small* tier, one document and one approval.
- **A large existing codebase:** you do not document all of it. A capability's spec starts with what your first change adds and grows
  from there. Behaviour that never went through a change simply is not watched yet.

## What to commit

| Path | Commit it? |
|---|---|
| `.tracespec.json` | Yes |
| `.tracespec/specs/`, `.tracespec/changes/` | Yes. The trace baseline and ledger are what make the audit work in CI. |
| `.tracespec/cache/` | No. It is local and gitignored by its own `.gitignore`. |
| `docs/features/` | Yes. It is the documentation. |
| `.tracespec-junit.xml`, `.tracespec-check.json` | No. Generated; add them to your `.gitignore`. |

## Next

- [Concepts](concepts.md) explains the ideas behind what you just did.
- [Examples](examples.md) shows real output from a finished project.
- [Troubleshooting](troubleshooting.md) if a step did not go as described.
