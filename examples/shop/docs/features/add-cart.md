# Add a cart

> Developer overview: read this to understand the feature without opening the agent files in `.tracespec/`. Keep it short.

## Purpose

Shoppers need to see what their cart costs and to pay with a gift card. This change adds the first rules of the `checkout`
capability: the total of a cart, and gift cards as a payment method.

## Design

One new module, `shop/cart.py`, next to `shop/catalog.py`. It is two pure functions with no state: `total` adds up item prices and
`accept_gift` recognises a gift card by its `GC-` prefix. Prices are whole numbers in cents, the unit the catalogue already uses, so the
cart never calls or changes the catalogue. Nothing existing calls the cart yet.

Key decision: plain functions rather than a `Cart` class, because there is no state to hold. A class can wrap them later without
changing callers.

## Key components

| Component | Path | Responsibility |
|---|---|---|
| Cart pricing | `shop/cart.py` | Totals a list of item prices and recognises gift cards |
