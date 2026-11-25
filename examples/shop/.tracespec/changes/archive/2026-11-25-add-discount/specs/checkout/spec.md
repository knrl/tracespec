# Delta: checkout

## ADDED

### Rules

| ID | Rule | Source |
|---|---|---|
| FR-3 | An order whose total is over 10000 gets 10% off | Q-1 |

### Criteria

| ID | Covers | Given / When / Then | Source |
|---|---|---|---|
| AC-3 | FR-3 | Given one item priced 15000, when the cart is totalled, then the total is 13500.0 | Q-1 |

## MODIFIED

### Rules

| ID | Rule | Source |
|---|---|---|
| FR-1 | The total of a cart is the sum of its item prices as a float, before any discount | ASM-1 |

### Criteria

| ID | Covers | Given / When / Then | Source |
|---|---|---|---|
| AC-1 | FR-1 | Given item prices 100 and 250, when the cart is totalled, then the total is the float 350.0 | ASM-1 |

## REMOVED

| ID | Reason | Migration |
|---|---|---|
| FR-2 | Gift cards moved to the payments service | Call payments.accept_gift |
| AC-2 | Gift cards moved to the payments service | Call payments.accept_gift |
