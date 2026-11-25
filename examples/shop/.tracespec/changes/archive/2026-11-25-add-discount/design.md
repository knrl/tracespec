# Design: Add a discount

## Existing code facts

- `shop/cart.py` has `total(items)` returning an int, and `accept_gift(card)`. Both are covered by tests in `tests/test_cart.py`.
- Tests are plain pytest functions, named `test_*`.

## Design decisions

| ID | Decision | Why | Source |
|---|---|---|---|
| D-1 | The discount is applied inside `total` and the result becomes a float | One place to apply it, so it cannot be applied twice | Q-1 |

## Interfaces the tests call

| Name and location | Signature | Behaviour on error |
|---|---|---|
| shop.cart.total | total(items: list[int]) -> float | none |

## Affected areas

| Path | New or changed | What |
|---|---|---|
| shop/cart.py | changed | the discount in total; accept_gift removed |

## Risks

| ID | Risk | What limits it |
|---|---|---|
| R-1 | The discount applied twice | D-1 and AC-3 |
