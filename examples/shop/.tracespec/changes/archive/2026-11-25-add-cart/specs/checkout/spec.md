# Delta: checkout

Purpose: Prices a shopper's cart: its total, discounts and the payment methods accepted at checkout.

## ADDED

### Rules

| ID | Rule | Source |
|---|---|---|
| FR-1 | The total of a cart is the sum of its item prices | Q-1 |
| FR-2 | A gift card is accepted as a payment method | Q-2 |

### Criteria

| ID | Covers | Given / When / Then | Source |
|---|---|---|---|
| AC-1 | FR-1 | Given item prices 100 and 250, when the cart is totalled, then the total is 350 | Q-1 |
| AC-2 | FR-2 | Given the gift card GC-1, when it is offered as payment, then it is accepted | Q-2 |
