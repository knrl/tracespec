# Contributing

Thanks for helping improve TraceSpec. This project is small, so the process is light, but a few rules keep the tool trustworthy.

## How to contribute

- **Typos, small docs fixes, obvious bugs with a test:** open a pull request directly.
- **Anything else** (a new check, a new command, a change to the process or to how something behaves): open an issue first, using
  [the forms](https://github.com/knrl/tracespec/issues/new/choose). TraceSpec runs inside agents, test runners and repositories we
  cannot see, so a change that helps one setup can break another. Talking first saves everyone a rewrite.
- **Bug reports:** say what you were trying to do, what happened, what you expected, and the shortest steps that reproduce it from a
  fresh project. Paste the `check.py` output. Mention your OS, Python version, test runner and `check.py --version`.
- **Ideas for new language support or a new stack preset:** an issue with an example project is the best start.

If an AI agent drafted your issue or pull request, read it through and make it yours. Say which agent and model you used.

## Development setup

You need Python 3.10 or newer. There are no dependencies: the whole tool is the standard library.

```bash
git clone https://github.com/knrl/tracespec.git
cd tracespec/tools
python -m unittest discover -s . -p "test_*.py"
```

CI runs those tests on Linux, macOS and Windows, and CodeQL on the Python code. A green local run on your machine is the best
predictor of a green CI run. A few tests need `git`; they skip themselves when it is missing.

To try the skill itself, install it from your checkout and restart Claude Code:

```bash
python install.py
```

## Design rules

These are what make a check worth trusting. A pull request that breaks one needs a very good reason.

1. **The tool decides, the model does not.** Anything a check asserts must be derived from files, git or a real test run, never from
   a model's say-so. If you are tempted to let an agent "confirm" something, make it a check instead.
2. **Standard library only.** No dependencies, no network access, no telemetry.
3. **Every finding code has two tests:** one that triggers it and one that shows the clean case. Add them to `tools/test_flow.py`,
   `tools/test_trace.py` or `tools/test_basics.py`, whichever fits.
4. **The tools write only what they own.** Outside the named commands, `check.py` is read-only. Writes go to `.tracespec/`,
   `docs/features/` and the state file. The agents never write there (`guard.py` enforces it).
5. **Output is plain ASCII where it can be.** Windows consoles still choke on a stray arrow or dash.
6. **Be honest about limits.** If a check is approximate, the output and the docs say so.
7. **Docs change with the code.** A new command or finding code updates `SKILL.md`, `docs/commands.md` and, if users will notice,
   `CHANGELOG.md`.

## Where things go

| You want to | Look at |
|---|---|
| Add a check on proposals and deltas | `check_text`, `check_deltas` and `evaluate` in `tools/check.py`; merge rules in `tools/living.py` |
| Add a coverage or test check | `check` in `tools/tracing.py` |
| Change what the audit flags | `audit` and `reconfirm` in `tools/ledger.py` |
| Change the trace graph or its query | `tools/links.py` (building), `tools/graph.py` (query and rendering), `tools/store.py` (storage) |
| Support another language's symbols | `resolve` in `tools/symbols.py` |
| Add a stack preset | `detect` in `tools/check.py`, with a case in `DetectTests` (`tools/test_basics.py`) |
| Change a workflow or a verb | `workflows/*.md`, the verb table in `SKILL.md`, `docs/commands.md` |
| Change a template | `templates/*.md` (the check reads their table shapes, so run the tests) |
| Change the agents | `templates/agents/*.md`; `install.py` renders the hook path into them |

## Pull requests

1. One focused change per pull request. Link the issue (`Closes #123`).
2. Run the tests. If you can, run them on a second operating system too; CI will do the rest.
3. Add a line under **Unreleased** in `CHANGELOG.md` if the change affects users.
4. Use a clear commit message: a short imperative first line, then why. No tag conventions required.

## Releases

Maintainers: update `VERSION` and `CHANGELOG.md`, commit, tag `vX.Y.Z`, and push the tag. The release workflow checks that the tag
matches `VERSION`, runs the tests, and publishes a GitHub release with that version's changelog section.

## Conduct

Be kind and assume good faith. See the [Code of Conduct](CODE_OF_CONDUCT.md). Security issues go through
[SECURITY.md](SECURITY.md), not public issues.
