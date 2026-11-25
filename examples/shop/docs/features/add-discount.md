# Add a discount

> Developer overview. Read this to understand the feature without opening the agent files in `.tracespec/`.

## Purpose

Larger orders should cost less, and gift cards are moving to the payments service. This change gives orders over 100.00 a 10% discount
and removes gift card handling from the cart.

## How it fits into the codebase

It only touches `shop/cart.py`. `total` now returns a float and applies the discount; `accept_gift` is gone, so any caller must use
the payments service instead (`payments.accept_gift`). The catalogue is untouched.

## Architecture

Still two small pieces: one function that prices a cart, and a constant for the discount threshold. The discount lives inside `total`,
so it can only be applied once.

## Key components

| Component | Path | Responsibility |
|---|---|---|
| Cart pricing | `shop/cart.py` | Totals item prices and applies the 10% discount over the threshold |

## Data flow

1. The caller passes item prices (cents) to `total`.
2. `total` sums them as a float.
3. If the sum is over the threshold (10000), it multiplies by 0.9. The result is returned.

## Facts (generated)

<!-- tracespec:facts:begin -->
**Status:** archived 2026-11-25 · **Change:** `add-discount` · **Capabilities:** checkout
**Agent records (no review needed):** `.tracespec/changes/archive/2026-11-25-add-discount`

### Behavior at a glance

**checkout**: Prices a shopper's cart: its total, discounts and the payment methods accepted at checkout.

| Rule | Change | What it says |
|---|---|---|
| FR-1 | modified | The total of a cart is the sum of its item prices as a float, before any discount |
| FR-3 | added | An order whose total is over 10000 gets 10% off |
| FR-2 | removed | A gift card is accepted as a payment method |

0 other rule(s) of this capability are unchanged.

### Where to look

- Code: `shop/cart.py`
- Tests: `tests/test_cart.py`
- Living specs: `.tracespec/specs/checkout/spec.md`

### How it is verified

- 2 of 2 rules and 2 of 2 criteria pass in the last run (3 tests).
- Each criterion has a test whose name carries its number (`check.py` decides this, not the author).
<!-- tracespec:facts:end -->
