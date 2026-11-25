# Security Policy

## Reporting a vulnerability

Report privately through [GitHub Security Advisories](https://github.com/knrl/tracespec/security/advisories/new). Please do not open a
public issue for a suspected vulnerability.

Include what you can: the affected version (`check.py --version`), reproduction steps, and the impact you believe it has. We aim to
acknowledge a report within a week and to ship a fix or a decision within 30 days. Valid reports are credited in the advisory unless
you would rather stay anonymous.

## Supported versions

Fixes land in the latest release. Older versions are not patched; update to pick up a fix (`python install.py` again).

## Threat model

TraceSpec is a set of local tools and agent instructions. It has no server, no network listener and no daemon, and it makes no
network requests. It runs with your own user permissions, inside the repository you point it at, and it has no dependencies beyond
Python's standard library.

What it does that is worth knowing about:

- **It runs your project's test command.** `check.py` runs the command stored in `.tracespec.json` (`layout.testCmd`) to produce test
  results. Treat `.tracespec.json` like a `Makefile` or a `package.json` script: **do not run TraceSpec in a repository you do not
  trust**, because its state file decides what command runs.
- **It reads and parses your source files** to find symbols (Python's `ast`, or `ctags` if you installed it).
- **It can install git hooks** (`--install-hooks`), only when you ask. They run `check.py --sync` and never block.
- **The agent hooks are a guard, not a sandbox.** `guard.py` stops the test agent and the coder agent from reading each other's files
  and from writing protected paths. It is built to catch honest mistakes. A shell command can be written in a way no pattern catches,
  and it is not a security boundary against a hostile agent.
- **The audit is tamper-evident, not tamper-proof.** The ledger and the trace baseline make edits outside the process visible.
  Anyone with write access to the repository can rewrite all of them together. Protect `.tracespec/` with code owners, branch
  protection and a CI run of `check.py --audit`.

That shapes what is and is not a vulnerability here:

| In scope | Out of scope |
| --- | --- |
| A spec, template, state file or source file that makes TraceSpec run code other than the configured test command | Running `layout.testCmd` as configured in a repository you chose to run it in |
| A path in a spec, task line or state file that makes a tool write outside the project | Reading or writing a path you passed to a command yourself |
| The guard failing to block a plain, documented case (for example a direct read of a hidden path) | A shell command crafted to evade the guard's patterns (a documented limit) |
| A crafted `trace.db` that makes `check.py` execute code or corrupt files | Rewriting `trace.db`, the ledger and the spec together to hide drift (a documented limit) |
| Leaking file contents or credentials into logs, reports or generated files | Denial of service against your own machine with your own input |

If you think something sits on the boundary, report it and we will work it out together.

## What is published

The repository contains the skill (`SKILL.md`, `workflows/`, `templates/`), the tools, tests, documentation and the installer. Nothing
is published to a package registry. Releases are tagged commits on GitHub.
