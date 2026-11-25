#!/usr/bin/env python3
"""Build or check the example project in examples/shop.

    python scripts/make_example.py            rebuild examples/shop with the real tools (needs pytest: pip install pytest)
    python scripts/make_example.py --check    audit the committed example; hash checks only, so pytest is not needed

The example is a tiny shop that goes through two changes: add-cart creates the `checkout` capability, and add-discount modifies one
rule, withdraws another and adds a third. Every step is a real `check.py` call; nothing in `.tracespec/` is written by hand except
the documents an agent would write (proposal, delta spec, design, tasks, overview). Dates in the archive come from the day you run it.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
OUT = ROOT / "examples" / "shop"
TRANSIENT_DIRS = {".git", ".pytest_cache", "__pycache__"}
TRANSIENT_FILES = {".tracespec-junit.xml", ".tracespec-check.json"}


def w(path: Path, text: str) -> None:
    """Write text with LF line endings on every platform, so the example is byte-identical across systems."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def check(proj: Path, *args: str, expect: int = 0) -> str:
    p = subprocess.run([sys.executable, str(TOOLS / "check.py"), str(proj), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != expect:
        print(p.stdout + p.stderr)
        raise SystemExit(f"check.py {' '.join(args)} exited {p.returncode}, expected {expect}")
    return p.stdout


def register(proj: Path, name: str, title: str) -> None:
    state = json.loads((proj / ".tracespec.json").read_text(encoding="utf-8"))
    state["changes"][name] = {"title": title, "tier": "standard", "phase": "propose", "spec": {"status": "draft"}}
    state["activeChange"] = name
    w(proj / ".tracespec.json", json.dumps(state, indent=2))


def write_change(proj: Path, name: str, proposal: str, design: str, delta: str, tasks: str) -> Path:
    d = proj / ".tracespec" / "changes" / name
    w(d / "proposal.md", proposal)
    w(d / "design.md", design)
    w(d / "specs" / "checkout" / "spec.md", delta)
    w(d / "tasks.md", tasks)
    return d


# ---- change 1: add-cart ------------------------------------------------------------------------------------

PROPOSAL_1 = """# Proposal: Add a cart
Version: 1.0
Status: Draft, for approval
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
"""

DESIGN_1 = """# Design: Add a cart

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
"""

DELTA_1 = """# Delta: checkout

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
"""

TASKS_1 = """# Tasks: Add a cart

- [ ] T-1 The interfaces of design.md as stubs, coder only (serves D-1)
- [ ] T-2 Total and gift cards (serves FR-1, FR-2, AC-1, AC-2, needs T-1)
"""

OVERVIEW_1 = """# Add a cart

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
<!-- tracespec:facts:end -->
"""

TEST_1 = '''from shop.cart import accept_gift, total


def test_AC1_total_is_the_sum_of_item_prices():
    assert total([100, 250]) == 350


def test_AC2_a_gift_card_is_accepted():
    assert accept_gift("GC-1") is True
'''

# ---- change 2: add-discount --------------------------------------------------------------------------------

PROPOSAL_2 = """# Proposal: Add a discount
Version: 1.0
Status: Draft, for approval
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
"""

DESIGN_2 = """# Design: Add a discount

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
"""

DELTA_2 = """# Delta: checkout

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
"""

TASKS_2 = """# Tasks: Add a discount

- [ ] T-1 The float total and the discount (serves D-1, FR-1, FR-3, AC-1, AC-3)
- [ ] T-2 Remove gift card acceptance (serves FR-2, AC-2, needs T-1)
"""

OVERVIEW_2 = """# Add a discount

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
<!-- tracespec:facts:end -->
"""

TESTS_2 = '''from shop.cart import total


def test_AC1_total_is_a_float_before_any_discount():
    result = total([100, 250])
    assert result == 350.0
    assert isinstance(result, float)


def test_AC3_orders_over_the_threshold_get_ten_percent_off():
    assert total([15000]) == 13500.0
'''

README_EXAMPLE = """# Example project: shop

A tiny project that went through two TraceSpec changes, generated by `scripts/make_example.py` with the real tools. Look around:

| Where | What |
|---|---|
| `.tracespec.json` | State and layout (which paths are tests and code, the test command) |
| `.tracespec/specs/checkout/spec.md` | The living spec: rules, criteria, withdrawn rules |
| `.tracespec/specs/checkout/trace.db`, `history.jsonl` | The binary trace baseline and the hash-chained ledger |
| `.tracespec/changes/archive/` | The two archived changes: proposal, delta, design, tasks, review log |
| `docs/features/` | The one human-facing overview per change |

Try these from this folder (paths assume the repository layout; Python 3.10+ is enough, pytest is only needed to run the tests):

```bash
python ../../tools/check.py . --view                      # capabilities and drift
python ../../tools/check.py . --audit --no-run            # hash checks against the baseline
python ../../tools/check.py . --trace FR-1                # why a rule exists and what proves it
python ../../tools/check.py . --trace SHOP-31             # everything built for a ticket
python ../../tools/check.py . --trace shop/cart.py:6      # why does this line exist?
```

Then edit `shop/cart.py` and run `--audit --no-run` again: the audit names the rules and criteria that function serves.
"""


def build(out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp) / "shop"
        # the project before any change
        w(proj / "pyproject.toml", "[project]\nname = 'shop'\nversion = '0.0.0'\n")
        w(proj / "shop" / "__init__.py", "")
        w(proj / "shop" / "catalog.py", 'PRICES = {"apple": 120, "pear": 150}\n\n\ndef price_of(sku):\n    return PRICES[sku]\n')
        w(proj / "tests" / "test_catalog.py", 'from shop.catalog import price_of\n\n\ndef test_price_of_a_known_sku():\n    assert price_of("apple") == 120\n')
        w(proj / ".gitignore", ".pytest_cache/\n__pycache__/\n.tracespec-junit.xml\n.tracespec-check.json\n")
        detected = json.loads(subprocess.run([sys.executable, str(TOOLS / "check.py"), "--detect", str(proj)],
                                             capture_output=True, text=True, check=True).stdout)
        w(proj / ".tracespec.json", json.dumps({
            "process": "tracespec", "processVersion": "2.0", "activeChange": None, "changes": {},
            "layout": {"tests": detected["tests"], "code": ["shop/**"], "testCmd": detected["testCmd"], "junit": detected["junit"]}},
            indent=2))

        # ---- change 1
        d = write_change(proj, "add-cart", PROPOSAL_1, DESIGN_1, DELTA_1, TASKS_1)
        register(proj, "add-cart", "Add a cart")
        check(proj, "--baseline")
        check(proj, "--gate", "2")
        check(proj, "--approve", "change", "--by", "Example Developer", "--words", "Yes, approve")
        check(proj, "--task-start", "T-1")
        w(proj / "shop" / "cart.py", "def total(items):\n    raise NotImplementedError\n\n\ndef accept_gift(card):\n    raise NotImplementedError\n")
        check(proj, "--task-done", "T-1")
        w(proj / "tests" / "test_cart.py", TEST_1)                       # the tests exist and fail first
        check(proj, "--gate", "3")
        check(proj, "--task-start", "T-2")
        w(proj / "shop" / "cart.py", 'def total(items):\n    return sum(items)\n\n\ndef accept_gift(card):\n    return card.startswith("GC-")\n')
        check(proj, "--task-done", "T-2")
        check(proj, "--gate", "4")
        check(proj, "--overview")
        w(proj / "docs" / "features" / "add-cart.md", OVERVIEW_1)
        check(proj, "--overview")
        check(proj, "--archive", "--ir-open", "0")

        # ---- change 2
        write_change(proj, "add-discount", PROPOSAL_2, DESIGN_2, DELTA_2, TASKS_2)
        register(proj, "add-discount", "Add a discount")
        check(proj, "--baseline")
        check(proj, "--gate", "2")
        check(proj, "--approve", "change", "--by", "Example Developer", "--words", "Yes, approve")
        w(proj / "tests" / "test_cart.py", TESTS_2)                      # AC-1 updated, AC-3 added, AC-2's test deleted
        check(proj, "--gate", "3")
        check(proj, "--task-start", "T-1")
        w(proj / "shop" / "cart.py",
          'DISCOUNT_THRESHOLD = 10000\n\n\ndef total(items):\n    subtotal = float(sum(items))\n'
          '    return subtotal * 0.9 if subtotal > DISCOUNT_THRESHOLD else subtotal\n\n\n'
          'def accept_gift(card):\n    return card.startswith("GC-")\n')
        check(proj, "--task-done", "T-1")
        check(proj, "--task-start", "T-2")
        w(proj / "shop" / "cart.py",
          'DISCOUNT_THRESHOLD = 10000\n\n\ndef total(items):\n    subtotal = float(sum(items))\n'
          '    return subtotal * 0.9 if subtotal > DISCOUNT_THRESHOLD else subtotal\n')
        check(proj, "--task-done", "T-2")
        check(proj, "--gate", "4")
        check(proj, "--overview")
        w(proj / "docs" / "features" / "add-discount.md", OVERVIEW_2)
        check(proj, "--overview")
        check(proj, "--archive", "--ir-open", "0")
        check(proj, "--audit")                                          # a full audit, with a fresh test run
        w(proj / "README.md", README_EXAMPLE)

        if out.exists():
            shutil.rmtree(out)
        for src in sorted(proj.rglob("*")):
            rel = src.relative_to(proj)
            if (set(rel.parts) & TRANSIENT_DIRS or src.name in TRANSIENT_FILES
                    or rel.parts[:2] == (".tracespec", "cache")):
                continue
            if src.is_file():
                dst = out / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
    print(f"wrote {out.relative_to(ROOT).as_posix()}")


def verify(src: Path) -> int:
    """Audit a copy of the committed example: spec, ledger, trace baseline and every linked symbol, without running tests."""
    if not src.is_dir():
        print(f"{src} does not exist: run python scripts/make_example.py")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp) / "shop"
        shutil.copytree(src, proj)
        p = subprocess.run([sys.executable, str(TOOLS / "check.py"), str(proj), "--audit", "--no-run"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(p.stdout.strip())
        return p.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Build or check examples/shop.")
    ap.add_argument("--check", action="store_true", help="audit the committed example instead of rebuilding it")
    args = ap.parse_args()
    return verify(OUT) if args.check else (build(OUT) or 0)


if __name__ == "__main__":
    sys.exit(main())
