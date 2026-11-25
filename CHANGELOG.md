# Changelog

All notable changes are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html). While the version is below 1.0.0, minor versions may change the
format of what TraceSpec writes into a project; the notes say so when they do.

## [Unreleased]

## [0.1.0] - 2026-11-25

First public release.

### Added

- **The process.** Verbs `explore`, `propose`, `apply`, `update`, `verify`, `archive`, `audit` and `trace`, driven from Claude Code with
  `/tracespec`. One developer approval (the proposal); every other gate is a tool check.
- **Living specs and deltas.** Per-capability specs that change only by archiving a change, which states what it adds, modifies and
  removes. Project-wide, never-reused IDs for rules (FR, NFR), criteria (AC) and non-goals (NG).
- **Independent agents.** `tracespec-test-writer` and `tracespec-coder`, kept apart by a hook: the test writer never sees code and the
  coder never sees tests. Tests are written to fail first; a modified criterion whose test still passes is rejected.
- **A deterministic coverage checker** driven by a real test run (JUnit XML): every criterion needs a test carrying its number, every
  new test needs a criterion, every task is ticked only when its criteria pass.
- **A trace store.** A binary SQLite baseline per capability (ticket, goal or question, rule, criterion, test, task, code symbol) with a
  hash-chained ledger, and a local live layer that follows the working tree and marks test results stale.
- **Symbol-level code links.** Python through `ast`, other languages through universal-ctags when installed, otherwise indentation
  regions.
- **An audit** that reports drift in specs, tests and code, and `reconfirm` for refactors that do not change behaviour.
- **`trace`**: ask how a rule, criterion, test, task, file, symbol, `file:line`, ticket or capability relates to the rest, with
  `--up`, `--down`, `--story`, `--json` and `--mermaid`.
- **Optional external references** (`Ref:` in a proposal, a Ref column on goals), with `layout.refPattern` and `layout.refRequired`.
- **A developer overview** per change in `docs/features/`, checked for completeness, with a generated facts block.
- **Tiers.** A small change is one document and one approval.
- **Git hooks** (`--install-hooks`) and an `install.py` installer.
- **Documentation**, an example project (`examples/shop`), and 90 unit tests.

### Tested

Python 3.10, 3.12 and 3.13 on Linux (git-dependent tests skipped), Python 3.14 on Linux and Windows. macOS and other Python versions
are covered by CI only.

### Known limits

- No call graph: a change in a function does not flag the functions that call it.
- A weak test with the right name passes the checker; the independent review is the only guard.
- Tamper-evident, not tamper-proof.

[Unreleased]: https://github.com/knrl/tracespec/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/knrl/tracespec/releases/tag/v0.1.0
