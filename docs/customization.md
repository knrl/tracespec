# Customization

## The layout in `.tracespec.json`

Discovery writes this file; you can edit it. It tells the tools which paths are tests, which are code, and how to run the tests.

```json
{
  "layout": {
    "tests": ["tests/**"],
    "code": ["src/**"],
    "protected": [".tracespec.json", ".tracespec-check.json", ".tracespec-junit.xml", ".tracespec/**", "docs/features/**"],
    "testCmd": ["python", "-m", "pytest", "-q", "--junitxml=.tracespec-junit.xml"],
    "testEnv": {},
    "junit": ".tracespec-junit.xml",
    "knownFailing": [],
    "overviewDir": "docs/features",
    "refPattern": "",
    "refRequired": false
  },
  "checks": [ { "name": "lint", "cmd": "ruff check ." } ]
}
```

| Key | Meaning |
|---|---|
| `tests` | Globs of test files. Hidden from the coder; the only place the test writer may write. |
| `code` | Globs of code. Hidden from the test writer. A path in both lists counts as a test. |
| `protected` | Neither agent may write here. Both may read. |
| `testCmd` | The command (an argument list) that runs the whole suite and writes JUnit XML. |
| `testEnv` | Extra environment variables for `testCmd`. |
| `junit` | The JUnit file or glob that `testCmd` writes, relative to the project. |
| `knownFailing` | Exact names of tests that already failed in the baseline; never blamed on a change. |
| `overviewDir` | Where the one-file-per-change developer overview goes. |
| `refPattern`, `refRequired` | Optional rules for external references (below). |
| `checks` | Other commands (lint, types, build) the agent runs after each task. The tool does not run these itself. |

Globs use `*` inside a folder and `**` across folders; a plain folder name means everything below it.

## Stack presets

`check.py --detect <project>` guesses the layout and a test command from your project files. Discovery shows you the guess.

| Stack | Test command it suggests | JUnit output |
|---|---|---|
| Python | `python -m pytest -q --junitxml=...` (or `uv run pytest` when `uv.lock` exists) | built in |
| Node, vitest | `npx vitest run --reporter=junit --outputFile=...` | built in |
| Node, jest | `npx jest --reporters=jest-junit` with `JEST_JUNIT_OUTPUT_*` set | needs the `jest-junit` package |
| Go | `gotestsum --junitfile ... ./...` | needs `gotestsum` |
| Maven | `mvn -q test` | `target/surefire-reports/TEST-*.xml` |
| Gradle | `./gradlew test` | `build/test-results/test/*.xml` |
| .NET | `dotnet test --logger "junit;LogFilePath=..."` | needs the JUnit test logger package |

**Only the Python preset has been exercised in tests and dry runs.** The others follow each tool's documented options; if one is
wrong for you, set `testCmd` and `junit` yourself and please open an issue.

A test is tied to its criterion by the criterion number in its name, in whatever style your runner reports names: `test_AC31_...`,
`it("AC31 rejects an empty cart")`, `func TestAC31_RejectsEmptyCart`, `[Fact] void AC31_...`.

## Symbols

A code link points at a symbol and a hash of its text. Resolvers, best first:

1. **Python: `ast`.** Exact: functions, classes and methods (`Class.method`), plus `<module>` for the top-level statements outside any
   function (imports and constants; blank lines are ignored).
2. **Other languages: universal-ctags**, if `ctags` on your path reports "Universal Ctags". Used when it gives an end line for every
   tag; otherwise the file falls back to regions. The parser is covered by a test; the live call is not exercised in CI.
3. **Anything else: regions.** Indentation blocks named by their first line. Approximate, but much tighter than a whole file.

A comment inside a function is part of that function's text. Calls between functions are not traced (see the [roadmap](roadmap.md)).
If your project keeps test files next to code files (`foo.ts` and `foo.test.ts`), the build agents cannot search, because no search can
leave the hidden files out; they read files by name.

## External references

Tie the chain to a ticket or issue; leave it out if your team does not use a tracker.

- A `Ref: JIRA-482` line in the proposal header covers every rule that change adds or modifies.
- Or fill the **Ref** column on a goal row; rules that cite that goal inherit it.
- References are any text (a ticket key, `GH#45`, a URL), separated by commas.
- `layout.refPattern` is a regular expression each reference must match, for example `[A-Z]+-\d+`. `layout.refRequired: true` makes a
  goal without a reference an error. Both default to off.

Then `trace JIRA-482` lists everything built for the ticket, down to tests and code.

## Hooks and refreshing the live layer

`check.py` syncs the live layer at the start of every command. To keep it current between commands:

```bash
python ~/.claude/skills/tracespec/tools/check.py . --install-hooks
```

installs git hooks (post-commit, post-merge, post-checkout) that run `--sync` and never block, and prints an optional Claude Code
`PostToolUse` snippet for `.claude/settings.json` that refreshes after every edit. TraceSpec does not edit your Claude settings.

## Templates and workflows

The documents the agents write come from `templates/`, and their behaviour from `workflows/` and `SKILL.md`. To change them, edit your
clone and run `python install.py`; an update from upstream overwrites an installed copy.

The checker reads the **shape** of the templates, so keep these intact: the headings *Goal*, *Existing code facts*, *Interfaces the
tests call* and *Affected areas*; the `ADDED`, `MODIFIED` and `REMOVED` headings in a delta (its capability is the folder it sits in); the column order of
the rule, criterion and non-goal tables; and the checkbox format of tasks. Run the tests after any template change.

## Using the checks in CI

See [Team workflow](team-workflow.md#ci).
