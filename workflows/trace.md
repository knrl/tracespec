# trace: ask how things relate

**Command:** `/tracespec trace <anything>`. **Writes:** nothing. **Stops for:** nothing.

The mappings are stored in a binary graph (`trace.db` per capability, plus the live layer), so nobody reads them by hand. This is how a person, or you, asks them. Use it whenever the developer asks "what does X cover", "which tests protect Y", "why does this code exist", "what was built for ticket Z", "what breaks if I change this".

## Do
Turn the question into a target and run `python <skill folder>/tools/check.py <project root> --trace <target>`:

| The developer asks | Target | Example |
|---|---|---|
| "What does this test check, and why?" | the test name, or a part of it | `--trace test_AC31_rejects_empty_cart` |
| "Why does this code exist?" | `file::symbol`, or `file:line` | `--trace shop/cart.py::checkout`, `--trace shop/cart.py:120` |
| "What is built for this rule or criterion?" | the ID | `--trace FR-12`, `--trace AC-31 --down` |
| "What was built for the ticket?" | the external reference | `--trace JIRA-482` |
| "What is in this capability?" | the capability | `--trace checkout` |
| "What did task T-2 change?" | the task | `--trace T-2` (or `add-discount/T-2` if two changes use it) |
| "What does this file serve?" | the file | `--trace shop/cart.py` |

Direction: `--up` goes toward the ticket (why), `--down` toward the code and tests (what). `--story` shows the whole of the rule a node belongs to. With none of them, a test, task or code target shows its whole story with the target marked `==>`, and a rule, criterion or ticket shows both directions. `--depth N` (default 8) and `--limit N` (default 120 lines) keep the answer short; the output says when it was cut. `--json` is for you to read programmatically, `--mermaid` produces a diagram the developer can paste into a document.

## Reading the answer
```
==> criterion AC-31 [checkout]  total([]) is rejected   <run: PASS (fresh)>
  ^ covers  rule FR-12 [checkout]  An empty cart cannot be checked out
    ^ from  question add-cart/Q-3  ... -- ...
      ^ ref  ref JIRA-482
  serves  task add-cart/T-2  Reject empty cart
    built by  code shop/cart.py::checkout  function   <ok>
  verifies  test tests/test_cart.py::test_AC31_rejects_empty_cart   <ok>
```
- `^` marks what is above the target (why it exists); unmarked indented lines are what is below it.
- State in angle brackets: code and tests are `ok`, `CHANGED since the last archive` or `MISSING` (with "same text now at ..." when it moved); a criterion shows its last test run and whether it is `fresh` or `stale` (a linked symbol changed since the run).
- `in flight: added|modified` marks a change that is not archived yet; its rows are in the graph already.
- A node whose children were already shown is marked "(children shown above)".

## When it finds nothing
Say what was tried and ask for a better target: an ID, a test name, a file, `file::symbol`, `file:line`, a ticket or a capability. A symbol the audit calls MISSING can be found by its old id only while the baseline still holds it.

## Keeping it current
The live layer syncs at the start of every `check.py` command, so an answer reflects the working tree. Run `--audit` for a fresh test run (stale results turn fresh). `--export FILE [--living]` writes a matrix as Markdown for anyone who wants a document, on request. `--install-hooks` makes git refresh the layer after commit, merge and checkout.
