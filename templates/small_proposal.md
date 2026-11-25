# Proposal: <<change title>>

Version: 0.1
Status: Draft
Change: <<change-name>>
Tier: small (one document: request, questions, delta, design and tasks)
Ref: <<optional: a ticket, issue or URL; leave the line out if the team has no tracker>>

> For a change of about 3 rules or fewer, about 3 files, one capability. If it grows past 3 rules the check warns:
> switch the change to the standard tier. Every FR, NFR and D names its source. IDs are never renumbered.
> The tests and the code are written from this file by two separate agents who never see each other's work.

## Request

> <<the developer's request, word for word>>

## Goal

| ID | Goal | Source |
|---|---|---|
| G-1 | <<who gets what, and why>> | Q-1 |

## Questions

Answers are copied word for word and never edited. A correction is a new row.

| ID | Question | Answer (word for word) |
|---|---|---|
| Q-1 | <<question, with a concrete example, or "answered by the repo: path">> | <<answer>> |

What must never happen (their words): <<...>>

## Assumptions

| ID | Item | Status | Source |
|---|---|---|---|
| ASM-1 | <<assumption>> | open | Q-1 |

## Capability: <<kebab-case-name>>

Purpose: <<only for a NEW capability: one sentence of at least 20 characters>>

### ADDED

#### Rules

| ID | Rule | Source |
|---|---|---|
| FR-<<n>> | <<When X, the system does Y>> | Q-1 |

#### Criteria

| ID | Covers | Given / When / Then | Source |
|---|---|---|---|
| AC-<<n>> | FR-<<n>> | Given <<state>>, when <<action with values>>, then <<exact result>> | Q-1 |

### MODIFIED

(same tables, full new text, same IDs)

### REMOVED

| ID | Reason | Migration |
|---|---|---|

## Existing code facts

- <<names, signatures, fixtures, test conventions, with paths>>

## Design decisions

| ID | Decision | Why | Source |
|---|---|---|---|
| D-1 | <<decision, inside the project's existing structure and style>> | <<reason>> | Q-1 |

## Interfaces the tests call

Exact name, location, signature, behaviour on error. Test names carry the criterion number, for example
`test_AC1_rejects_empty_cart`.

| Name and location | Signature | Behaviour on error |
|---|---|---|
| <<module.function>> | <<(arg: type) -> type>> | <<raises X / returns Y>> |

## Affected areas

| Path | New or changed | What |
|---|---|---|
| <<path>> | changed | <<what>> |

## Tasks

- [ ] T-1 The interfaces as stubs, coder only (serves D-1)
- [ ] T-2 <<behaviour>> (serves FR-<<n>>, AC-<<n>>, needs T-1)
