# Team workflow

## One change, one branch, one pull request

A TraceSpec change maps naturally onto a branch and a pull request:

1. Create a branch, then `/tracespec propose ...` on it.
2. Apply, verify and archive. Everything lands in the branch: the code, the tests, the updated living specs, the baseline, the
   archived change and the overview.
3. Open the pull request. Reviewers read **`docs/features/<change>.md`** first (purpose, how it fits, architecture, data flow), then
   the diff. They do not need to read the files under `.tracespec/`; those are for the agents and the tool.

## Commit these

`.tracespec.json`, `.tracespec/specs/`, `.tracespec/changes/` and `docs/features/`. Do not commit `.tracespec/cache/` (it has its own
`.gitignore`), `.tracespec-junit.xml` or `.tracespec-check.json`.

## Ownership

Treat the specs like code that needs an owner. In `CODEOWNERS`:

```
/.tracespec/   @your-team
/docs/features/ @your-team
```

## CI

Run the audit in your pipeline so drift fails the build. This is a sketch; adjust it to your CI and pin the version you use:

```yaml
- uses: actions/checkout@v4                     # your project
- name: Install your dependencies and test tools   # whatever your testCmd needs
  run: pip install -r requirements.txt pytest
- name: Get TraceSpec
  run: git clone --depth 1 --branch v0.1.0 https://github.com/knrl/tracespec.git "$RUNNER_TEMP/tracespec"
- name: Audit
  run: python "$RUNNER_TEMP/tracespec/tools/check.py" . --audit
```

`--audit` runs your `testCmd`, so the job needs your test dependencies. Use `--audit --no-run` for the hash checks only, which needs
nothing but Python.

## Several changes at once

You can have more than one change in flight; they go through apply independently. The tool protects the shared specs:

- **Two changes add the same ID** (DELTA005): take another ID with `check.py --next-id`.
- **Another change was archived under yours and touched a row you modify or remove** (DELTA010): read the new living row, rebase your
  delta on it (a MODIFIED row repeats the new text with your edit), and approve again.
- **Archive one change at a time.** Archiving rewrites the capability's spec, baseline and ledger.

## Merge conflicts in `trace.db`

`trace.db` is binary, so a conflict cannot be merged by hand. Take either side, run `check.py . --sync`, then
`check.py . --audit`. If the spec and baseline still agree with the code, `--reconfirm <capability>` re-baselines it, and only when
every criterion passes. If the two sides each archived a different change, archive them in order instead: rebase the second change's
delta (DELTA010) and archive it again.

## Reviewing a change

A two-minute pass that catches a wrong turn while it is still cheap:

1. **The proposal summary** the agent showed you at approval: does each rule and example say what you meant?
2. **The overview**, `docs/features/<change>.md`: does the data flow match your mental model, and are the key components the ones you
   expected?
3. **The diff**, with the overview's "Where to look" list as a guide.
4. For a risky area, `/tracespec trace <file>` shows every rule, criterion and test that depends on it before you change it.
