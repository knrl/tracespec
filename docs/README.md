# TraceSpec documentation

TraceSpec helps you and your coding agents **agree on what to build before code is written, and prove afterwards that it was built**.
You describe a change; the agents ask what they need, write the requirements and acceptance criteria, and stop for your one approval.
Then one agent writes tests that must fail, a different agent writes the code, and a checker, not a model, decides whether every
requirement is covered by a passing test. Afterwards it keeps watch for code, tests or specs drifting away from that record.

If you read nothing else, read these two pages:

1. [Getting started](getting-started.md): install, make your first change.
2. [Concepts](concepts.md): the handful of ideas everything else rests on.

## Pick your path

| I want to | Read |
|---|---|
| Install it and try it on a real change | [Getting started](getting-started.md) |
| Understand living specs, deltas, the trace and the audit | [Concepts](concepts.md) |
| See the diagrams: agents, the trace, drift, what lands in the repo | [How it works](how-it-works.md) |
| Compare it with other tools, or see its limits | [Comparison and limits](comparison-and-limits.md) |
| See real output from a finished project | [Examples](examples.md), and the project in [`examples/shop`](../examples/shop) |
| Look up a command, a flag or a finding code | [Commands](commands.md) |
| Fit it to my language, test runner or team rules | [Customization](customization.md) |
| Use it with a team, branches, pull requests and CI | [Team workflow](team-workflow.md) |
| Fix something that went wrong | [Troubleshooting](troubleshooting.md) |
| Check a term | [Glossary](glossary.md) |
| Quick answers (is it tied to Claude Code? what about OpenSpec?) | [FAQ](faq.md) |
| See what is planned and what is deliberately not | [Roadmap](roadmap.md) |

## Two halves

TraceSpec has two halves, and knowing which is which saves the most common confusion:

- **Slash commands you give to Claude Code**, for example `/tracespec propose add a discount`. This is where you work.
- **A command-line tool, `check.py`,** that the agent runs for you in the background (and that you can run yourself): it runs the
  checks, records approvals, merges changes, and answers `trace` questions. You rarely type it; [Commands](commands.md) lists it all.

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md). Security reports go through [SECURITY.md](../SECURITY.md).
