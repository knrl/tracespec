# Add a cart

> Developer overview. Read this to understand the feature without opening the agent files in `.tracespec/`.

## Purpose

Shoppers need to see what their cart costs and to pay for it with a gift card. This change adds the first rules of the `checkout`
capability: the total of a cart, and gift cards as a payment method.

## How it fits into the codebase

It adds one module, `shop/cart.py`, next to `shop/catalog.py`. The cart reads item prices as whole numbers in cents, the same unit the
catalogue uses, and does not call or change the catalogue. Nothing existing calls the cart yet.

## Architecture

Two pure functions with no state. `total` adds up prices; `accept_gift` decides whether a card is a gift card.

## Key components

| Component | Path | Responsibility |
|---|---|---|
| Cart pricing | `shop/cart.py` | Totals a list of item prices and recognises gift cards |

## Data flow

1. The caller passes item prices (cents) to `total` and gets their sum.
2. To pay, the caller passes a card identifier to `accept_gift`, which answers whether it is a gift card (`GC-` prefix).

## Facts (generated)

<!-- tracespec:facts:begin -->
**Status:** archived 2026-11-25 · **Change:** `add-cart` · **Capabilities:** checkout
**Agent records (no review needed):** `.tracespec/changes/archive/2026-11-25-add-cart`

### Behavior at a glance

**checkout**: Prices a shopper's cart: its total, discounts and the payment methods accepted at checkout.

| Rule | Change | What it says |
|---|---|---|
| FR-1 | added | The total of a cart is the sum of its item prices |
| FR-2 | added | A gift card is accepted as a payment method |

0 other rule(s) of this capability are unchanged.

### Where to look

- Code: `shop/cart.py`
- Tests: `tests/test_cart.py`
- Living specs: `.tracespec/specs/checkout/spec.md`

### How it is verified

- 2 of 2 rules and 2 of 2 criteria pass in the last run (3 tests).
- Each criterion has a test whose name carries its number (`check.py` decides this, not the author).
<!-- tracespec:facts:end -->
