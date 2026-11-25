# How it compares, and what it does not do

## How it compares

The spec-driven space is busy and every tool makes different trade-offs. These are the stated focuses, from each project's own
documentation; check them for what they offer today.

| Tool | Stated focus |
|---|---|
| [Spec Kit](https://github.com/github/spec-kit) | An open-source toolkit and CLI for spec-driven development across many coding agents |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | Lightweight, per-change spec workflow with living specs and deltas, through slash commands |
| [Kiro](https://kiro.dev) | An agentic IDE with spec-driven development built in |
| [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | A team of specialised agents following an agile method |
| [Tessl](https://tessl.io) | Treating the spec as the long-lived source of truth |

TraceSpec shares the per-change, spec-first workflow, and borrows its living-spec and delta model from OpenSpec. Its own focus is
what comes after the spec: **independent test and code agents, coverage decided by a checker from real test runs, a queryable
trace down to functions, and an audit for drift after shipping.**

## Limits

- The checker proves each criterion has a passing test and that the chain is intact. It cannot prove the criteria are the right ones.
- A weak test with the right name passes the checker. The independent review is the only guard against that.
- No call graph: a change in a function does not flag the functions that call it ([roadmap](roadmap.md)).
- A comment edited inside a function changes that function's hash.
- Tamper-evident, not tamper-proof: anyone with write access can rewrite spec, baseline and ledger together.
- Symbols are exact for Python, good with universal-ctags, approximate otherwise. Only the Python stack preset has been exercised.
- Tests are not run automatically (they are slow). A recorded result is marked stale when something it depended on changes.
- Tested on Python 3.10, 3.12, 3.13 and 3.14, on Linux and Windows. macOS is covered by CI only.
