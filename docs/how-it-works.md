# How it works

The picture behind the quick start: who does what, what gets recorded, and what happens when something changes later. For the
vocabulary, see [Concepts](concepts.md); for every command, see [Commands](commands.md).

## The full flow

From a request to a closed change, and what keeps watching afterwards.

```mermaid
flowchart TB
    REQ(["your request<br/>(optional ticket ref)"])

    subgraph SPEC["1 - Clarify and specify"]
        direction LR
        Q["agent asks questions"] --> DOC["proposal, delta specs<br/>rules FR-n, criteria AC-n,<br/>design, tasks"]
    end
    G12{{"CHECKER gates 1-2<br/>every rule has a criterion,<br/>no TBD, IDs unique"}}
    YOU{{"YOU approve once"}}

    subgraph TESTS["2 - Acceptance tests first"]
        direction LR
        TW["agent A writes tests<br/>named after AC-n<br/>(never sees the code)"] --> RED["tests must FAIL first<br/>a modified criterion that<br/>already passes is rejected"]
    end
    G3{{"CHECKER gate 3<br/>every criterion has a test,<br/>every test has a criterion"}}

    subgraph BUILD["3 - Build, task by task"]
        direction LR
        CO["agent B writes code<br/>(never sees the tests)"] --> GREEN["real test run<br/>must pass"]
    end
    G4{{"CHECKER gate 4<br/>task ticked only when its<br/>criteria pass; symbols recorded"}}

    subgraph CLOSE["4 - Verify and archive"]
        direction LR
        REV["independent review<br/>+ one developer overview"] --> ARCH["deltas merge into<br/>the living specs"]
    end
    G5{{"CHECKER gate 5<br/>full suite green,<br/>chain unbroken"}}

    subgraph STORE["Evidence kept in the repo"]
        direction LR
        LS[("living specs")] ~~~ DB[("trace.db<br/>ticket - rule - criterion<br/>- test - task - symbol")] ~~~ LED[("hash-chained<br/>ledger")]
    end

    subgraph WATCH["5 - Watching afterwards"]
        direction LR
        EDIT["code, test or spec<br/>edited outside the process"] --> SYNC["sync hashes symbols,<br/>marks results stale"] --> AUD["audit: DRIFT finding<br/>names the rules and tests<br/>to revisit"]
    end

    REQ --> SPEC --> G12 --> YOU --> TESTS --> G3 --> BUILD --> G4 --> CLOSE --> G5
    G5 --> STORE
    STORE --> WATCH
    AUD -. "update the spec, or revert" .-> SPEC
    ASK(["/tracespec trace<br/>why does this exist?"]) -.-> DB

    classDef human fill:#fde68a,stroke:#b45309,color:#1f2937
    classDef agent fill:#bfdbfe,stroke:#1d4ed8,color:#1f2937
    classDef tool fill:#bbf7d0,stroke:#15803d,color:#1f2937
    classDef store fill:#e9d5ff,stroke:#7e22ce,color:#1f2937
    class REQ,YOU,ASK human
    class Q,DOC,TW,CO,REV agent
    class G12,G3,G4,G5,RED,GREEN,SYNC,AUD,ARCH tool
    class LS,DB,LED store
```

<sub>Yellow is you, blue is agent work, green is decided by the deterministic checker from files and real test runs, purple is
what stays in your repository.</sub>

## What do the specs look like?

Plain Markdown tables, no special syntax. A change is written as a delta against the living spec: it lists only what it adds,
modifies and removes. This is the real delta from [`examples/shop`](../examples/shop):

```markdown
## ADDED

| ID   | Rule                                            | Source |
|------|-------------------------------------------------|--------|
| FR-3 | An order whose total is over 10000 gets 10% off | Q-1    |

| ID   | Covers | Given / When / Then                                                                  |
|------|--------|--------------------------------------------------------------------------------------|
| AC-3 | FR-3   | Given one item priced 15000, when the cart is totalled, then the total is 13500.0    |

## REMOVED

| ID   | Reason                                   | Migration                   |
|------|------------------------------------------|-----------------------------|
| FR-2 | Gift cards moved to the payments service | Call payments.accept_gift   |
```

Your agent writes these, you review the summary before any code is written, and the criterion number `AC-3` ends up in the name of
the test that proves it.

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

## Traceability at a glance

Every ticket, rule, criterion, test and function is a node, and every link is recorded. `check.py --trace <anything> --mermaid`
draws the neighbourhood of whatever you ask about, in layers from the request to the code. The two diagrams below are that real output
for ticket `SHOP-31` in [`examples/shop`](../examples/shop).

**Healthy: every layer is linked, and the last test run passed.** Green means the check passes or the code and test still match the
baseline.

```mermaid
flowchart LR
  subgraph L_Request["Request"]
    n4["ref SHOP-31"]
    n5["goal add-discount/Change<br/>the change add-discount"]
  end
  subgraph L_Rules["Rules"]
    n2["FR-1<br/>The total of a cart is the sum of its item pri..."]
    n3["FR-3<br/>An order whose total is over 10000 gets 10% of..."]
  end
  subgraph L_Criteria["Criteria"]
    n0["AC-1<br/>Given item prices 100 and 250, when the cart i..."]
    n1["AC-3<br/>Given one item priced 15000, when the cart is ..."]
  end
  subgraph L_Tests["Tests"]
    n9["test_cart.py::test_AC1_total_is_a_float_before_any_discount"]
    n10["test_cart.py::test_AC3_orders_over_the_threshold_get_ten_percent_off"]
  end
  subgraph L_Tasks["Tasks"]
    n6["task T-1<br/>The float total and the discount"]
  end
  subgraph L_Code["Code"]
    n7["cart.py (module level)"]
    n8["cart.py::total"]
  end
  n2 -->|covers| n0
  n3 -->|covers| n1
  n5 -->|from| n2
  n5 -->|from| n3
  n4 -->|ref| n5
  n0 -->|serves| n6
  n1 -->|serves| n6
  n6 -->|built by| n7
  n6 -->|built by| n8
  n0 -->|verifies| n9
  n1 -->|verifies| n10
  classDef good fill:#bbf7d0,stroke:#15803d,color:#1f2937
  classDef warn fill:#fde68a,stroke:#b45309,color:#1f2937
  classDef bad fill:#fecaca,stroke:#b91c1c,color:#1f2937
  classDef idle fill:#e5e7eb,stroke:#6b7280,color:#1f2937
  class n0,n1,n7,n8,n9,n10 good
```

**After someone edits `total` and deletes the test file.** Nothing else changed, yet the picture shows exactly what is affected:
amber is a function that changed since the last archive (and the criteria whose result is now stale), red is a test that no longer
exists. A rule with no criterion, or a criterion with no test, is red too: that is a gap in coverage.

```mermaid
flowchart LR
  subgraph L_Request["Request"]
    n4["ref SHOP-31"]
    n5["goal add-discount/Change<br/>the change add-discount"]
  end
  subgraph L_Rules["Rules"]
    n2["FR-1<br/>The total of a cart is the sum of its item pri..."]
    n3["FR-3<br/>An order whose total is over 10000 gets 10% of..."]
  end
  subgraph L_Criteria["Criteria"]
    n0["AC-1<br/>Given item prices 100 and 250, when the cart i..."]
    n1["AC-3<br/>Given one item priced 15000, when the cart is ..."]
  end
  subgraph L_Tests["Tests"]
    n9["test_cart.py::test_AC1_total_is_a_float_before_any_discount"]
    n10["test_cart.py::test_AC3_orders_over_the_threshold_get_ten_percent_off"]
  end
  subgraph L_Tasks["Tasks"]
    n6["task T-1<br/>The float total and the discount"]
  end
  subgraph L_Code["Code"]
    n7["cart.py (module level)"]
    n8["cart.py::total"]
  end
  n2 -->|covers| n0
  n3 -->|covers| n1
  n5 -->|from| n2
  n5 -->|from| n3
  n4 -->|ref| n5
  n0 -->|serves| n6
  n1 -->|serves| n6
  n6 -->|built by| n7
  n6 -->|built by| n8
  n0 -->|verifies| n9
  n1 -->|verifies| n10
  classDef good fill:#bbf7d0,stroke:#15803d,color:#1f2937
  classDef warn fill:#fde68a,stroke:#b45309,color:#1f2937
  classDef bad fill:#fecaca,stroke:#b91c1c,color:#1f2937
  classDef idle fill:#e5e7eb,stroke:#6b7280,color:#1f2937
  class n7 good
  class n0,n1,n8 warn
  class n9,n10 bad
```

How to read it: follow an arrow from left to right to see what implements and proves a request; follow it right to left to see why a
line of code exists. The same graph answers questions in text: `--trace shop/cart.py:6` (why does this line exist), `--trace AC-3`
(what proves it), `--trace SHOP-31` (what was built for the ticket).

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
| `docs/features/<change>.md` | **One short overview per feature**: purpose, design, key components | **you** |

Commit `.tracespec/` (the baseline and ledger are what make the audit work in CI) and `docs/features/`. Nobody has to review the
files under `.tracespec/`; your review of a proposal is a summary shown in the chat.
