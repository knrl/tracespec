# How it works

The picture behind the quick start: who does what, what gets recorded, and what happens when something changes later. For the
vocabulary, see [Concepts](concepts.md); for every command, see [Commands](commands.md).

## How the pieces fit

The two build agents only meet through the written criteria, and the checker, not a model, decides what counts as covered.

```mermaid
flowchart TB
    SPEC[("Criteria<br/>AC-1, AC-2 ...")]
    SPEC -->|"reads criteria only"| TW["Agent A<br/>test writer"]
    SPEC -->|"reads criteria only"| CO["Agent B<br/>coder"]
    TW -->|"writes"| TESTS["tests<br/>test_AC1_..."]
    CO -->|"writes"| CODE["source code"]
    TESTS -. "hook blocks reading code" .- CO
    CODE -. "hook blocks reading tests" .- TW
    TESTS --> RUN["real test run<br/>(JUnit result)"]
    CODE --> RUN
    RUN --> CHK{"checker<br/>every criterion has a<br/>passing test that names it?"}
    CHK -->|yes| OK["covered"]
    CHK -->|no| FIND["finding with a code<br/>(TEST001, TEST007 ...)"]
```

## What it records

Each link in this chain is stored in a small binary trace and can be queried from either end with `/tracespec trace`.

```mermaid
flowchart BT
    SYM["code symbol<br/>shop/cart.py::total"] -- "built by" --> TASK["task T-1"]
    TASK -- "serves" --> AC["criterion AC-1"]
    TEST["test<br/>test_AC1_..."] -- "verifies" --> AC
    AC -- "covers" --> FR["rule FR-1"]
    FR -- "source" --> Q["question Q-1"]
    FR -- "ref" --> REF["ticket SHOP-31<br/>(optional)"]
```

## Staying true after it ships

The live layer hashes your files and symbols on every command. An edit made outside the process turns into a finding that names
what to revisit.

```mermaid
flowchart LR
    ED["someone edits<br/>shop/cart.py::total"] --> SYNC["sync: hash differs<br/>from the baseline"]
    SYNC --> STALE["last test result<br/>marked stale"]
    SYNC --> DRIFT["audit: DRIFT finding<br/>names AC-1, FR-1,<br/>test_AC1_..."]
    DRIFT --> CHOICE{"your call"}
    CHOICE -->|"the change was right"| UPD["update the spec and<br/>tests, then --reconfirm"]
    CHOICE -->|"the change was wrong"| REV["revert the edit"]
```

## What lands in your repository

| Where | What | Who reads it |
|---|---|---|
| `.tracespec.json` | State and layout (which paths are tests and code, the test command) | the tool |
| `.tracespec/specs/<capability>/` | The **living specs**, a binary trace baseline (`trace.db`) and a hash-chained ledger (`history.jsonl`) | the tool and the agents |
| `.tracespec/changes/<change>/` | A change in flight: proposal, delta specs, design, tasks. Archived changes move to `changes/archive/`. | the agents |
| `.tracespec/cache/` | Local live layer. Gitignored by its own `.gitignore`. | the tool |
| `docs/features/<change>.md` | **One short overview per feature**: purpose, how it fits the codebase, architecture, key components, data flow | **you** |

Commit `.tracespec/` (the baseline and ledger are what make the audit work in CI) and `docs/features/`. Nobody has to review the
files under `.tracespec/`; your review of a proposal is a summary shown in the chat.
