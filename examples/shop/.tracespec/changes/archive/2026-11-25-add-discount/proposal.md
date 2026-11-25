# Proposal: Add a discount
Version: 1.0
Status: Approved
Change: add-discount
Ref: SHOP-31

## Request

> Give orders over 100 a 10% discount. Gift cards are moving to the payments service.

## Goal

| ID | Goal | Source | Ref |
|---|---|---|---|
| G-1 | Larger orders cost less, and the cart no longer owns gift cards | Q-1 | SHOP-31 |

## Capabilities touched

| Capability | New or existing | Why |
|---|---|---|
| checkout | existing | A new discount rule, a changed total, and one rule withdrawn |

## Questions

| ID | Question | Answer (word for word) | Kind |
|---|---|---|---|
| Q-1 | From what order total does the discount apply? | Over 10000 cents, which is 100.00. | asked |
| Q-2 | What happens to gift cards in the cart module? | The payments service takes them over. Remove them here. | asked |

What must never happen (their words): A discount is applied twice.

## Assumptions

| ID | Item | Status | Source |
|---|---|---|---|
| ASM-1 | The total becomes a float because 10% of a whole number of cents need not be whole | confirmed | Q-1 |
