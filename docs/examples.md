# Examples

The repository includes a finished project, [`examples/shop`](../examples/shop), built by running the real tools through two changes
(`scripts/make_example.py`). Everything below is real output from it. On this page `check.py` stands for `python ~/.claude/skills/tracespec/tools/check.py` (where `install.py` puts it).

## The story

1. **`add-cart`** created the `checkout` capability: *the total of a cart is the sum of its item prices* (FR-1) and *a gift card is
   accepted as a payment method* (FR-2), each with an acceptance criterion and a test.
2. **`add-discount`** then **modified** FR-1 (the total becomes a float, before any discount), **added** FR-3 (orders over 10000 get
   10% off) and **removed** FR-2 (gift cards moved to another service). Its test for AC-1 was updated to fail first, AC-3's test was
   added, and AC-2's test was deleted.

## The living spec after both changes

`.tracespec/specs/checkout/spec.md` (shortened):

```
## Behavior rules
| ID   | Rule                                                                              | Source                 |
| FR-1 | The total of a cart is the sum of its item prices as a float, before any discount | ASM-1 (add-discount)   |
| FR-3 | An order whose total is over 10000 gets 10% off                                   | Q-1 (add-discount)     |

## Withdrawn
| ID   | Was                                    | Reason                                    | By change    |
| AC-2 | Given the gift card GC-1, ...          | Gift cards moved to the payments service  | add-discount |
| FR-2 | A gift card is accepted as a payment...| Gift cards moved to the payments service  | add-discount |
```

## Ask the trace

*What was built for ticket SHOP-31?*

```
$ check.py . --trace SHOP-31 --depth 3
==> ref SHOP-31
  ref  goal add-discount/Change  the change add-discount
    from  rule FR-1 [checkout]  The total of a cart is the sum of its item prices as a float, before any...
      covers  criterion AC-1 [checkout]  Given item prices 100 and 250, when the cart is totalled, then the total...
      serves  task add-discount/T-1  The float total and the discount
    from  rule FR-3 [checkout]  An order whose total is over 10000 gets 10% off
      covers  criterion AC-3 [checkout]  Given one item priced 15000, when the cart is totalled, then the total i...
      serves  task add-discount/T-1  The float total and the discount   (children shown above)
```

*Why does line 6 of `shop/cart.py` exist?* (shortened)

```
$ check.py . --trace shop/cart.py:6
^ ref  ref SHOP-31
^ from  question add-discount/Q-1  From what order total does the discount apply? -- Over 10000 cents, whic...
rule FR-1 [checkout]  The total of a cart is the sum of its item prices as a float, before any...
  covers  criterion AC-1 [checkout]  Given item prices 100 and 250, when the cart is totalled, then the total...
    serves  task add-discount/T-1  The float total and the discount
      ==> built by  code shop/cart.py::total  function   <ok>
    verifies  test tests/test_cart.py::test_AC1_total_is_a_float_before_any_discount   <ok>
```

`^` marks what is above the target (why it exists); unmarked indented lines are what is below it (what was built and what proves it).
`<ok>` means the symbol still matches the baseline.

## The developer overview

`docs/features/add-discount.md` is the one file a reviewer reads. Its narrative sections are written from the code that was built; the
block at the end is generated:

```
### Behavior at a glance
| Rule | Change   | What it says                                                                       |
| FR-1 | modified | The total of a cart is the sum of its item prices as a float, before any discount |
| FR-3 | added    | An order whose total is over 10000 gets 10% off                                    |
| FR-2 | removed  | A gift card is accepted as a payment method                                        |

### Where to look
- Code: `shop/cart.py`
- Tests: `tests/test_cart.py`
- Living specs: `.tracespec/specs/checkout/spec.md`
```

## Drift: edit a linked function

Edit `total` in `examples/shop/shop/cart.py`, then audit (hash checks only, so no pytest is needed):

```
$ check.py . --audit --no-run
[checkout]
  DRIFT-CODE error shop/cart.py::total changed since the last archive; it serves FR-1, FR-3 and criteria AC-1, AC-3:
  if the behaviour changed, propose a change; if it did not, `--reconfirm`
audit: 1 capability, 1 error(s), 0 warning(s) (tests not run)
```

Add an unrelated function to the same file instead, and the audit stays clean: links are to symbols, not files. If the edit was a
refactor that did not change behaviour, `check.py . --reconfirm checkout --note "same behaviour"` re-baselines it, but only when every
criterion of `checkout` has a passing test.

## Try it yourself

```bash
cd examples/shop
python ../../tools/check.py . --view
python ../../tools/check.py . --audit --no-run
python ../../tools/check.py . --trace FR-3
```

To rebuild the example from scratch with the current tools: `pip install pytest`, then `python scripts/make_example.py`.
