# Design: Add a cart

## Existing code facts

- Tests are plain pytest functions in `tests/`, named `test_*.py`.
- `shop/catalog.py` already prices single items with `price_of(sku)`. The cart builds on that idea but does not change the catalogue.

## Design decisions

| ID | Decision | Why | Source |
|---|---|---|---|
| D-1 | Two pure functions in a new module `shop/cart.py` | It matches `shop/catalog.py`: plain functions, no state | Q-1 |

## Interfaces the tests call

Test naming rule: every test name carries the number of the criterion it checks, for example `test_AC1_...`.

| Name and location | Signature | Behaviour on error |
|---|---|---|
| shop.cart.total | total(items: list[int]) -> int | none |
| shop.cart.accept_gift | accept_gift(card: str) -> bool | returns False for a card that is not a gift card |

## Affected areas

| Path | New or changed | What |
|---|---|---|
| shop/cart.py | new | total and accept_gift |

## Risks

| ID | Risk | What limits it |
|---|---|---|
| R-1 | A cart total that differs from the sum of the item prices | AC-1 pins the sum |
