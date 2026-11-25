# Glossary

| Term | Meaning |
|---|---|
| **Acceptance criterion (AC)** | A concrete example, with real values, that a rule must satisfy. Every test carries its number. |
| **Amendment** | An edit to an approved proposal that changes no delta row. Recorded with `--amend`; needs no approval. |
| **Archive** | Closing a change: merge its delta into the living specs, write the baseline and ledger, move it to the archive. |
| **Baseline** | The trace as it was at the last archive or reconfirm (`trace.db`). The audit compares against it. |
| **Capability** | One area of behaviour with its own living spec, for example `checkout`. |
| **Change** | The unit of work: a folder with a proposal, delta specs, a design and tasks. |
| **Criterion** | See acceptance criterion. |
| **Delta** | The part of a change that says what is added, modified or removed in a capability's spec. |
| **Design decision (D)** | How something will be built, with its reason and source. Every one is served by a task. |
| **Drift** | Code, tests or a spec differing from the baseline without a change that explains it. |
| **External reference** | An optional ticket, issue or URL attached to a goal or a whole change. |
| **Gate** | A phase check run by `check.py --gate N`. It refuses with finding codes when something is wrong. |
| **Ledger** | `history.jsonl`: an append-only list of archive, amendment and reconfirm events, each holding the hash of the line before it. |
| **Live layer** | The local cache of current hashes, symbols and test results (`.tracespec/cache/`). |
| **Living spec** | The current behaviour of a capability. Written only by archive. |
| **Non-goal (NG)** | What a capability deliberately does not do. |
| **Overview** | The one human-facing file per change, `docs/features/<change>.md`. |
| **Proposal** | `proposal.md`: request, goal, questions and answers, assumptions. What you approve. |
| **Reconfirm** | Re-baselining a capability after a change to code or tests that did not change behaviour; allowed only when every criterion passes. |
| **Rule (FR / NFR)** | A statement of what the system does (FR) or a limit it respects (NFR). |
| **Stale** | A recorded test result whose linked symbols or files have changed since the run. |
| **Symbol** | A function, method or class (or an approximate region) with a hash of its own text. The unit a code link points at. |
| **Task (T)** | One checkbox line in `tasks.md`. Ticked only when the criteria it serves pass. |
| **Tier** | How much process a change gets: *small* (one document) or *standard*. |
| **Trace** | The graph from external reference through goal, rule, criterion and test, and from task to code symbol. |
| **Verify** | Converging code against the documents, an independent review, and writing the overview. |
