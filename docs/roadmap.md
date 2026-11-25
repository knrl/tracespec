# Roadmap

These are ideas and known gaps, not promises. Open an issue to discuss one, or to argue for something that is not here.

## Known gaps

- **No call graph.** A change in a function does not flag the functions that call it. A design exists: store each linked symbol's
  callees to a small depth (Python through `ast`, other languages by matching identifiers), report a changed dependency as a separate,
  lower-severity finding, and resolve it with `--reconfirm` when the tests pass. Open questions: the default depth, how noisy name
  matching is outside Python, and whether a changed dependency should be a warning or an error.
- **Criteria are prose, not executable.** The link from criterion to test is a naming convention plus a run, so a weak test with the
  right name passes the checker. An optional executable format (for example Gherkin-style steps) could close that, at the cost of
  tying the tool to a test framework.
- **Languages other than Python are second-class.** Symbols rely on universal-ctags or approximate regions, and only the Python stack
  preset has been exercised in tests.
- **File-level fallback.** A language with no symbols resolver falls back to indentation regions, which can mis-split unusual layouts.
  A tree-sitter based resolver, as an optional extra, would help.
- **Claude Code only.** The agents and the hook use Claude Code features.

## Ideas

- A ready-made GitHub Action to run `--audit` in CI, instead of cloning the repository in a step.
- Watching lockfiles: list `requirements.txt` or `package-lock.json` so a dependency change flags every capability once.
- A `depends:` note on a task line for dependencies the analysis cannot see (for example injected at runtime).
- More export formats for the matrix, for audit and compliance reviews.
- Dogfooding: managing this repository's own changes with TraceSpec.
- Support for other agent hosts, if the workflow documents can be made host-neutral.

## Deliberately not planned

- **Telemetry or network access** in the tools.
- **Dependencies.** The tools stay standard-library only.
- **Letting a model decide coverage.** Checks derive their verdicts from files, git and a real test run.
- **Committing, pushing or deploying for you.**
