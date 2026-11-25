# Capability: checkout

Purpose: Prices a shopper's cart: its total, discounts and the payment methods accepted at checkout.

> Living spec: how this capability behaves now. Written only by `check.py --archive`; never edit it by hand.
> A change proposes edits as a delta; the audit flags any other edit.

## Behavior rules

| ID | Rule | Source |
|---|---|---|
| FR-1 | The total of a cart is the sum of its item prices as a float, before any discount | ASM-1 (add-discount) |
| FR-3 | An order whose total is over 10000 gets 10% off | Q-1 (add-discount) |

## Acceptance criteria

| ID | Covers | Given / When / Then | Source |
|---|---|---|---|
| AC-1 | FR-1 | Given item prices 100 and 250, when the cart is totalled, then the total is the float 350.0 | ASM-1 (add-discount) |
| AC-3 | FR-3 | Given one item priced 15000, when the cart is totalled, then the total is 13500.0 | Q-1 (add-discount) |

## Non-goals

| ID | Not part of this capability | Source |
|---|---|---|

## Withdrawn

Kept so an ID is never reused.

| ID | Was | Reason | By change |
|---|---|---|---|
| AC-2 | Given the gift card GC-1, when it is offered as payment, then it is accepted | Gift cards moved to the payments service | add-discount |
| FR-2 | A gift card is accepted as a payment method | Gift cards moved to the payments service | add-discount |
