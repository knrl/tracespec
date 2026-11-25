# Delta: <<capability>>

Purpose: <<only for a NEW capability: one sentence, at least 20 characters, saying what the capability is for>>

> A delta lists only what differs from the living spec `.tracespec/specs/<capability>/spec.md`. Take new IDs from
> `check.py --next-id FR|NFR|AC|NG`. IDs are project-wide and never reused.
> A MODIFIED row carries the **full new text** of the row, with the same ID. A REMOVED row gives the reason and what
> callers do instead. Delete a rule's criteria in the same change, or modify them so they no longer cover it.
> Every rule needs at least one criterion once the change is merged. Each test name carries its AC number.

## ADDED

### Rules

| ID | Rule | Source |
|---|---|---|
| FR-<<n>> | <<When X, the system does Y>> | Q-1 |

### Criteria

Concrete input and result, with real values.

| ID | Covers | Given / When / Then | Source |
|---|---|---|---|
| AC-<<n>> | FR-<<n>> | Given <<state>>, when <<action with values>>, then <<exact result>> | Q-1 |

### Non-goals

| ID | Not part of this capability | Source |
|---|---|---|
| NG-<<n>> | <<thing someone might expect, but is out>> | Q-1 |

## MODIFIED

### Rules

| ID | Rule | Source |
|---|---|---|

### Criteria

| ID | Covers | Given / When / Then | Source |
|---|---|---|---|

## REMOVED

| ID | Reason | Migration |
|---|---|---|
