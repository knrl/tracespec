# Proposal: Add a cart
Version: 1.0
Status: Approved
Change: add-cart
Ref: SHOP-12

## Request

> Add a cart that totals the items in it and lets a shopper pay with a gift card.

## Goal

| ID | Goal | Source | Ref |
|---|---|---|---|
| G-1 | A shopper sees what a cart costs and can pay with a gift card | Q-1 | SHOP-12 |

## Capabilities touched

| Capability | New or existing | Why |
|---|---|---|
| checkout | new | The pricing and payment rules of a cart |

## Questions

| ID | Question | Answer (word for word) | Kind |
|---|---|---|---|
| Q-1 | How are item prices represented? | Whole numbers, in cents. | asked |
| Q-2 | Which payment methods must work first? | Gift cards. Cards come later. | asked |

What must never happen (their words): A shopper is charged more than the items cost.

## Assumptions

| ID | Item | Status | Source |
|---|---|---|---|
| ASM-1 | Item prices are never negative | confirmed | Q-1 |
