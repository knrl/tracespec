# TraceSpec

[![CI](https://github.com/knrl/tracespec/actions/workflows/ci.yml/badge.svg)](https://github.com/knrl/tracespec/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](docs/getting-started.md)

**An automated requirements traceability matrix with acceptance-test-driven builds, run by agents.**

**The goal is full coverage in both directions.** Every requirement is covered by acceptance criteria and a passing test, and every
test and every function built for a change traces back to a requirement. Nothing requested goes untested, and nothing unrequested
gets built.

TraceSpec gets there with three things that spec tools usually leave out:

- **Independent agents.** Tests and code are written by separate agents that cannot see each other's work (a hook enforces it), so
  they can only agree through the written criteria.
- **A deterministic checker.** Coverage is decided from files and a real test run, never by a model's say-so.
- **A queryable trace** from ticket down to the function, which flags drift when code, tests or specs change outside the process.

**What we optimise for**

- **Less ambiguity.** A request becomes numbered rules and concrete examples before any code exists, so "done" has one meaning.
- **More traceability.** Any test, task or function can be followed up to the rule and the question behind it, and down to what
  proves it.
- **More control.** You make one decision. A checker, not the agent, says whether the work is complete, and a later edit cannot slip
  by unnoticed.
- **Less friction.** It works on code that already exists, in any language, with nothing but Python installed.

> **Status: 0.1.0, early.** It works end to end and is tested on Windows and Linux, but the format TraceSpec writes into your project
> may still change before 1.0; the [changelog](CHANGELOG.md) says when it does.

## See it in action

*An illustrative session; every file and check named here is real, see [Examples](docs/examples.md) for actual output.*

```
You: /tracespec explore
AI:  What would you like to explore?
You: A discount at checkout. I'm not sure where it belongs.
AI:  Totals are computed in shop/cart.py and nothing else touches them,
     so the discount fits there. Want to scope it?
You: Yes.

You: /tracespec propose add-discount
AI:  Two questions. From what order total does the discount apply?
You: Over 10000 cents, 10% off.
AI:  Created .tracespec/changes/add-discount/
     OK proposal.md       why, goals, assumptions, decisions
     OK specs/checkout    1 rule added, 1 modified, 1 removed, with criteria
     OK design.md         technical approach
     OK tasks.md          checklist, each task tied to a criterion
     Gates 1-2: passed. Summary for you to approve: ...
You: Approved.

You: /tracespec apply
AI:  T-1  tests written by agent A: AC-1, AC-3 fail, as required
     T-1  code written by agent B:  2 passed
     Gate 4: every criterion has a passing test. Task T-1 done.

You: /tracespec archive
AI:  Gate 5 passed. Archived to .tracespec/changes/archive/2026-11-25-add-discount/
     Living spec updated. Overview for you: docs/features/add-discount.md
```

## Use it in three steps

You need [Claude Code](https://claude.com/claude-code) and Python 3.10 or newer. Nothing else.

**1. Install** (once)

```bash
git clone https://github.com/knrl/tracespec.git
cd tracespec
python install.py
```

Then **restart Claude Code**: skills and agents are read when a session starts.

**2. Ask for a change** in the project you want to change

```
/tracespec add a 10% discount at checkout for orders over 100
```

It asks a few questions, then shows a short summary.

**3. Approve once**

Say yes to the summary. The tests are written (and fail), the code is written (and passes), the checker verifies it, and you get
one short overview of the feature in `docs/features/`. That is the whole loop.

## Cheat sheet

| You type | What happens |
|---|---|
| `/tracespec <request>` | Starts a change: questions, then a proposal for your one approval |
| `/tracespec explore <topic>` | Think it through first. Writes nothing. |
| `/tracespec apply` | Build the approved change: tests first, then code. Resumable. |
| `/tracespec update` | The plan changed: revise the documents |
| `/tracespec verify` | Independent review, writes the developer overview |
| `/tracespec archive` | Merge the change into the living specs |
| `/tracespec audit` | Find code, tests or specs that drifted since |
| `/tracespec trace <anything>` | Ask how a rule, test, file, function or ticket connects to the rest |
| `/tracespec list`, `show <change>`, `view` | See what is in flight |

Most of the time you only type the first line and answer questions; the agent moves through the other verbs itself.

## Ask the trace

```
/tracespec trace shop/cart.py:6
```
```
^ ref  ref SHOP-31
^ from  question add-discount/Q-1  From what order total does the discount apply? -- Over 10000 cents...
rule FR-1 [checkout]  The total of a cart is the sum of its item prices as a float, before any...
  covers  criterion AC-1 [checkout]  Given item prices 100 and 250, when the cart is totalled, then the total...
    serves  task add-discount/T-1  The float total and the discount
      ==> built by  code shop/cart.py::total  function   <ok>
    verifies  test tests/test_cart.py::test_AC1_total_is_a_float_before_any_discount   <ok>
```

That is real output from [`examples/shop`](examples/shop). You can ask about a rule or criterion ID, a test, a task, a file,
`file::symbol`, `file:line`, a ticket, or a whole capability. "Why does this line exist?", "What was built for ticket X?", "Which
tests protect this function?"

## Why TraceSpec?

- **Proof, not "the agent said it works".** You get a recorded chain you can audit and query afterwards.
- **One decision from you.** Answer questions, approve once. Everything else is a check that passes or refuses with a reason.

## Learn more

| | |
|---|---|
| [Getting started](docs/getting-started.md) | The same three steps, with every prompt and what you will see |
| [How it works](docs/how-it-works.md) | The full flow, with its gates and evidence, plus diagrams of the agents, the trace and drift |
| [Concepts](docs/concepts.md) | Living specs, deltas, the trace, the audit |
| [Commands](docs/commands.md) | Every verb, flag and finding code |
| [Customization](docs/customization.md) | Layout, stack presets, symbols, external ticket references, hooks |
| [Team workflow](docs/team-workflow.md) | Branches, pull requests, CI, merge conflicts |
| [Examples](docs/examples.md) | Real output from a finished project |
| [Comparison and limits](docs/comparison-and-limits.md) | How it differs from OpenSpec, Spec Kit and others; what it cannot do |
| [Troubleshooting](docs/troubleshooting.md), [FAQ](docs/faq.md), [Glossary](docs/glossary.md), [Roadmap](docs/roadmap.md) | |

Updating is `git pull` and `python install.py` again.

## Contributing

Issues and pull requests are welcome; small fixes can go straight to a pull request, anything bigger starts as an issue. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for the design rules and how to run the tests. Please follow the
[Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities privately, as described in [SECURITY.md](SECURITY.md). Maintainers are
listed in [MAINTAINERS.md](MAINTAINERS.md); agents working on this repository should read [AGENTS.md](AGENTS.md).

## Acknowledgements

TraceSpec's per-change workflow, living specs and deltas are inspired by [OpenSpec](https://github.com/Fission-AI/OpenSpec) (MIT). The
conduct policy is adapted from the [Contributor Covenant](https://www.contributor-covenant.org), and the changelog follows
[Keep a Changelog](https://keepachangelog.com).

## License

MIT. See [LICENSE](LICENSE).
