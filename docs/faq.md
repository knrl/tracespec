# FAQ

**Is TraceSpec only for Claude Code?**
Today, yes. The skill, the two agents and the hook that keeps them apart use Claude Code features. `check.py` and the other tools are
plain Python and work without it, but the workflow documents and the agent definitions would need porting to another agent host.

**Do I need git?**
No. Git adds the scope check (no file changed outside the change's "Affected areas") and optional hooks. Without git those are skipped.

**Which languages does it work with?**
Any whose test runner can write JUnit XML. Symbols are exact for Python, good for other languages if universal-ctags is installed, and
approximate otherwise. Only the Python stack preset has been exercised in tests; see [Customization](customization.md#stack-presets).

**How is it different from OpenSpec, Spec Kit, Kiro or BMAD?**
It shares the per-change, spec-first workflow, and its living specs and deltas are inspired by [OpenSpec](https://github.com/Fission-AI/OpenSpec).
What it adds is a stricter chain: test and code written by agents that cannot see each other's work, coverage decided by a checker from
a real test run, a queryable trace down to functions, and an audit for drift after shipping. We have not audited every other tool in
depth, so check their docs for what they offer today.

**Can I edit a spec by hand?**
Not a living spec: the audit flags it. Edit the change's documents before approval, or use `/tracespec update` after. A change to a
delta row after approval needs a new version approved again; any other edit is recorded as an amendment.

**Why only one approval?**
Because the later gates are things a tool can decide, and a tool's refusal with a reason is faster and more reliable than a person
re-reading documents. Your review is of the summary of what will be built; everything after that is checked mechanically.

**My tests are slow. When do they run?**
At gates 3, 4 and 5, when a task is ticked, and for `--audit`. Never in the background. `--audit --no-run` does the hash checks only.
A recorded result is marked stale when a symbol it depended on changes.

**Is the trace tamper-proof?**
No, tamper-evident. The ledger holds the hash of the previous line, of the spec and of the trace baseline, so edits outside the process
break the chain visibly. Anyone with write access can rewrite all of it together. Use code owners and run `--audit` in CI.

**Does it send anything over the network?**
No. There is no telemetry and no network access in the tools.

**Is it safe to run in a repository I do not trust?**
No. `check.py` runs the command in `.tracespec.json` (`layout.testCmd`). Treat that file like a `Makefile`. See [SECURITY.md](../SECURITY.md).

**What does "traceable spec-driven development" mean here?**
Specification-driven, with an automated requirements traceability matrix and acceptance-test-driven development built in: every
requirement traces forward to criteria, tests, tasks and code, and back to the question or ticket it came from.

**Is this related to the `@tracespec/*` packages on npm?**
No. Those are an unrelated project with a similar name; this repository is not affiliated with it. Both use a `.tracespec/` folder name,
so do not use both tools in the same repository.

**How do I uninstall it?**
Delete `~/.claude/skills/tracespec` and the two agent files `~/.claude/agents/tracespec-*.md`. In a project, remove `.tracespec.json`,
`.tracespec/` and `docs/features/` if you no longer want them, and the block between `# tracespec:begin` and `# tracespec:end` in
`.git/hooks/post-commit`, `post-merge` and `post-checkout` if you installed hooks.

**Which models does it use?**
Whatever your Claude Code session uses. The behaviour of the agents depends on the model; the checks do not.
