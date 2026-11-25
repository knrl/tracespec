# audit: find drift in the living specs, then resolve it on purpose

**Commands:** `/tracespec audit`, and the checks that run it for you at the start of propose and apply. **Writes:** nothing, except `reconfirm`.

The living specs are only worth anything if edits outside the process are noticed. After every archive the tool writes a **baseline** (`trace.db`): the graph from ticket to code symbol, with a hash of every spec row, symbol and file. The audit compares the project with it. It is **tamper-evident, not tamper-proof**: anyone with write access can rewrite the baseline too. The protection is that the build agents cannot, that the ledger is hash-chained (it holds the hash of the spec and of the database), and that CI plus git history catch the rest.

## Run it
`python <skill folder>/tools/check.py <project root> --audit` (add `--no-run` for the hash checks only, `--ci` in a pipeline: exit 1 on any error). `check.py <project root> --view` shows a drift count per capability.

| Finding | Meaning |
|---|---|
| DRIFT-SPEC | a living `spec.md`, `trace.db` or `history.jsonl` was edited outside an archive, or the ledger chain is broken. Names the rows. |
| DRIFT-CODE | a linked code **symbol** changed, was deleted or renamed since the last archive. Names the rules and criteria it serves; a moved symbol is recognised by its text. |
| DRIFT-TEST | a linked test symbol (or, for a language without symbols, test file) changed or was deleted. Names the criteria. |
| UNCOVERED | a living criterion has no passing test in a fresh run. |
| UNLINKED-TEST (warning) | a test names a criterion no living spec defines (a change in flight may add it). |

The report is grouped by capability: "checkout: shop/cart.py changed; it serves FR-10 and criteria AC-20, AC-21".

## Look before you edit
`check.py <project root> --trace <file, file::symbol, or ID>` shows everything linked to it (see [trace.md](trace.md)); `--impact` is the same command. Explore and propose use it for the areas the developer names, so a proposal starts with the affected criteria already listed. `check.py <project root> --view` shows a drift count per capability and how many recorded test results are stale.

## Resolve it: nothing is accepted silently
| Situation | Resolution | What the tool requires |
|---|---|---|
| The behaviour really changed | **Propose a change.** Start it from the drift: the capability, the rules and criteria the finding names as MODIFIED rows, the tests to update. | The normal checks, including a failing test for every MODIFIED criterion |
| The code or tests changed but the behaviour did not (refactor, a fix inside the rules) | `check.py <project root> --reconfirm <capability or ID>... --note "why the behaviour did not change"` | **Every criterion of the capability has a passing test in a fresh run**, and no spec row changed. It refreshes the hashes, **follows a symbol that was renamed or moved** (same text, new place), unlinks one that is gone and says so, and appends a ledger line. |
| A living spec was edited by hand | Revert it, or redo the edit through a change. | The audit stays red until one of those happens. A reconfirm refuses while the spec drifted. |

Links are at symbol level, so an edit to an unrelated function in a shared file does not flag anything. What is still not seen: the call graph (a change in a callee does not flag its callers), and behaviour that never went through a change (no links, not watched). Symbols come from Python's `ast` (exact), `universal-ctags` when installed, or indentation regions (approximate); say which one a file got when the answer matters.

## CI
One line in a pipeline, plus an owner for the spec folders:

```
python <skill folder>/tools/check.py . --audit --ci
```
and in CODEOWNERS: `.tracespec/specs/  @your-team`
