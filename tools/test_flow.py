"""Tests of the change / living spec flow: deltas, approval, amendments, archive, lock, audit, reconfirm, impact.
Run: python -m unittest test_flow   (from the tools folder)"""
import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check  # noqa: E402
import common  # noqa: E402
import living  # noqa: E402
import store  # noqa: E402


# ---- fixtures ----------------------------------------------------------------------------------------------

def junit_cmd(cases):
    """A test command that writes a fixed JUnit file: cases = [(name, status)]."""
    body = "".join(
        f'<testcase classname="t.test_cart" name="{n}">' +
        {"pass": "", "fail": '<failure message="assert 1 == 2"/>', "skip": '<skipped message="s"/>'}[s] + "</testcase>"
        for n, s in cases)
    xml = f"<testsuites><testsuite>{body}</testsuite></testsuites>"
    return [sys.executable, "-c", f"open('.tracespec-junit.xml','w').write({xml!r})"]


PROPOSAL = textwrap.dedent("""\
    # Proposal: {name}
    Version: 1.0
    Status: Draft, for approval
    Change: {name}

    ## Request
    > {name} in the developer's words

    ## Goal
    | ID | Goal | Source |
    |---|---|---|
    | G-1 | The goal | Q-1 |

    ## Questions
    | ID | Question | Answer |
    |---|---|---|
    | Q-1 | How should it work? | As described |

    ## Assumptions
    | ID | Item | Status | Source |
    |---|---|---|---|
    | ASM-1 | Integers only | confirmed | Q-1 |
    """)

DESIGN = textwrap.dedent("""\
    # Design
    ## Existing code facts
    - tests use plain functions
    ## Design decisions
    | ID | Decision | Why | Source |
    |---|---|---|---|
    | D-1 | Pure function | style | Q-1 |
    ## Interfaces the tests call
    total(items)
    ## Affected areas
    | Path | New or changed | What |
    |---|---|---|
    | shop/cart.py | changed | total |
    """)

# change 1: a new capability with two rules
DELTA_1 = textwrap.dedent("""\
    # Delta: checkout
    Purpose: Totals and discounts for the checkout of a cart.
    ## ADDED
    ### Rules
    | ID | Rule | Source |
    |---|---|---|
    | FR-1 | Total is the sum of items | Q-1 |
    | FR-2 | Gift cards are accepted | Q-1 |
    ### Criteria
    | ID | Covers | Given / When / Then | Source |
    |---|---|---|---|
    | AC-1 | FR-1 | total([1,2]) is 3 | Q-1 |
    | AC-2 | FR-2 | a gift card pays | Q-1 |
    """)

TASKS_OPEN = "- [ ] T-1 Skeleton (serves D-1)\n- [ ] T-2 Total (serves FR-1, FR-2, AC-1, AC-2, needs T-1)\n"
TASKS_DONE_1 = ("- [x] T-1 Skeleton (serves D-1)\n"
                "- [x] T-2 Total (serves FR-1, FR-2, AC-1, AC-2, needs T-1) files: shop/cart.py\n")

# change 2: modifies FR-1 and AC-1, removes FR-2 and AC-2, adds FR-3 and AC-3
DELTA_2 = textwrap.dedent("""\
    # Delta: checkout
    ## ADDED
    ### Rules
    | ID | Rule | Source |
    |---|---|---|
    | FR-3 | Orders over 100 get 10% off | Q-1 |
    ### Criteria
    | ID | Covers | Given / When / Then | Source |
    |---|---|---|---|
    | AC-3 | FR-3 | total([150]) is 135 | Q-1 |
    ## MODIFIED
    ### Rules
    | ID | Rule | Source |
    |---|---|---|
    | FR-1 | Total is the sum of items, before any discount | Q-1 |
    ### Criteria
    | ID | Covers | Given / When / Then | Source |
    |---|---|---|---|
    | AC-1 | FR-1 | total([1,2]) is 3 with no discount | Q-1 |
    ## REMOVED
    | ID | Reason | Migration |
    |---|---|---|
    | FR-2 | Gift cards are dropped | none |
    | AC-2 | Gift cards are dropped | none |
    """)
TASKS_2 = ("- [ ] T-1 Skeleton (serves D-1)\n"
           "- [ ] T-2 Discount (serves FR-1, FR-3, AC-1, AC-3, FR-2, AC-2, needs T-1)\n")


OVERVIEW = textwrap.dedent("""\
    # {name}
    ## Purpose
    This change adds totals and discounts to checkout so that carts are priced correctly for customers.
    ## How it fits into the codebase
    It extends the existing cart module and is called by the checkout screen; nothing else is touched.
    ## Architecture
    A single pure function computes the total from the list of item prices.
    ## Key components
    | Component | Path | Responsibility |
    |---|---|---|
    | Cart totals | `shop/cart.py` | Computes the total of a cart |
    ## Data flow
    1. The checkout passes the item prices. 2. The function sums them. 3. The total is returned.
    ## Facts (generated)
    <!-- tracespec:facts:begin -->
    <!-- tracespec:facts:end -->
    """)


class Env:
    """A throwaway project with a state file, a fake test command and the sources the changes touch."""

    def __init__(self, tmp: str, cases=None):
        self.root = Path(tmp)
        (self.root / "tests").mkdir()
        (self.root / "shop").mkdir()
        (self.root / "shop" / "cart.py").write_text("def total(items):\n    return sum(items)\n")
        (self.root / "tests" / "test_cart.py").write_text("def test_AC1_a(): pass\ndef test_AC2_b(): pass\n")
        self.state = {"process": "tracespec", "processVersion": "2.0", "activeChange": None, "changes": {},
                      "layout": {"tests": ["tests/**"], "code": ["shop/**"], "junit": ".tracespec-junit.xml",
                                 "testCmd": junit_cmd(cases or [("test_AC1_a", "pass"), ("test_AC2_b", "pass")])}}
        self.save()

    def save(self):
        (self.root / common.STATE).write_text(json.dumps(self.state), encoding="utf-8")

    def reload(self):
        self.state = json.loads((self.root / common.STATE).read_text())

    def set_cases(self, cases):
        self.reload()
        self.state["layout"]["testCmd"] = junit_cmd(cases)
        self.save()

    def add_change(self, name, delta, tasks, tier=None, cap="checkout", design=DESIGN, proposal_extra=""):
        d = self.root / ".tracespec" / "changes" / name
        (d / "specs" / cap).mkdir(parents=True)
        (d / "proposal.md").write_text(PROPOSAL.format(name=name) + proposal_extra)
        (d / "design.md").write_text(design)
        (d / "specs" / cap / "spec.md").write_text(delta)
        if tasks is not None:
            (d / "tasks.md").write_text(tasks)
        self.reload()
        self.state["changes"][name] = {"title": name, "tier": tier or "standard", "phase": "propose", "spec": {"status": "draft"}}
        self.state["activeChange"] = name
        self.save()
        self.write_overview(name)
        return d

    def overview_path(self, name):
        return self.root / "docs" / "features" / f"{name}.md"

    def write_overview(self, name, text=None):
        p = self.overview_path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if text is not None else OVERVIEW.format(name=name))

    def run(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = check.main([str(self.root), *args])
        return rc, out.getvalue()

    def codes(self, gate, change=None):
        extra = ["--change", change] if change else []
        rc, out = self.run("--gate", str(gate), *extra)
        return {m.group(1): m.group(2) for m in re.finditer(r"^(\w+) (error|warning) ", out, re.M)}

    def approve(self, change=None):
        extra = ["--change", change] if change else []
        return self.run("--approve", "change", "--by", "Dev", "--words", "yes, approved", *extra)

    def tasks_file(self, name):
        return self.root / ".tracespec" / "changes" / name / "tasks.md"

    def finish_change_1(self):
        """Approve and archive change 1 (add-cart); returns the archive result."""
        self.add_change("add-cart", DELTA_1, TASKS_OPEN)
        rc, out = self.approve("add-cart")
        assert rc == 0, out
        self.tasks_file("add-cart").write_text(TASKS_DONE_1)
        return self.run("--archive", "--ir-open", "0", "--change", "add-cart")

    def spec_path(self, cap="checkout"):
        return self.root / ".tracespec" / "specs" / cap / "spec.md"

    def trace(self, cap="checkout"):
        return json.loads((self.root / ".tracespec" / "specs" / cap / "trace.json").read_text())

    def feat(self, name):
        self.reload()
        return self.state["changes"][name]


# ---- living spec: parse and merge --------------------------------------------------------------------------

class MergeTests(unittest.TestCase):
    def test_parse_and_merge_add_modify_remove(self):
        rows, purposes = living.parse_deltas(DELTA_1, "checkout")
        self.assertEqual({r["id"] for r in rows}, {"FR-1", "FR-2", "AC-1", "AC-2"})
        cap, problems, ops = living.merge(None, rows, "add-cart", purposes["checkout"])
        self.assertEqual(problems, [])
        self.assertEqual(living.validate_state(cap), [])
        self.assertIn("Q-1 (add-cart)", cap["rules"]["FR-1"][2])
        rows2, _ = living.parse_deltas(DELTA_2, "checkout")
        cap2, problems, ops = living.merge(cap, rows2, "add-discount", None)
        self.assertEqual(problems, [])
        self.assertEqual(ops["FR-2"], "REMOVED")
        self.assertIn("FR-2", cap2["withdrawn"])
        self.assertNotIn("FR-2", cap2["rules"])
        self.assertIn("before any discount", cap2["rules"]["FR-1"][1])
        self.assertEqual(living.validate_state(cap2), [])
        # round trip through the rendered file
        self.assertEqual(living.parse_living(living.render_living("checkout", cap2)), cap2)

    def test_merge_problems(self):
        rows, p = living.parse_deltas(DELTA_1, "checkout")
        cap, _, _ = living.merge(None, rows, "c1", p["checkout"])
        bad = [{"cap": "checkout", "op": "ADDED", "id": "FR-1", "cells": ["FR-1", "again", "Q-1"]},
               {"cap": "checkout", "op": "MODIFIED", "id": "FR-9", "cells": ["FR-9", "x", "Q-1"]},
               {"cap": "checkout", "op": "REMOVED", "id": "AC-9", "cells": ["AC-9", "gone", "none"]}]
        _, problems, _ = living.merge(cap, bad, "c2", None)
        self.assertEqual(sorted(c for c, _ in problems), ["DELTA001", "DELTA002", "DELTA002"])
        _, problems, _ = living.merge(None, rows, "c1", None)
        self.assertIn("DELTA009", [c for c, _ in problems])

    def test_orphans_after_merge(self):
        rows, p = living.parse_deltas(DELTA_1, "checkout")
        cap, _, _ = living.merge(None, rows, "c1", p["checkout"])
        remove_rule = [{"cap": "checkout", "op": "REMOVED", "id": "FR-2", "cells": ["FR-2", "gone", "none"]}]
        new, problems, _ = living.merge(cap, remove_rule, "c2", None)
        self.assertEqual(problems, [])
        self.assertIn("SPEC014", [c for c, _ in living.validate_state(new)])      # AC-2 covers a rule that is gone


# ---- the proposal checks and the approval ------------------------------------------------------------------

class ProposalTests(unittest.TestCase):
    def test_good_change_passes_gate_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertEqual({k for k, v in env.codes(2).items() if v == "error"}, set())

    def test_delta_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.finish_change_1()
            # ADDED an existing ID, MODIFIED an unknown one
            bad = DELTA_2.replace("| FR-3 | Orders over 100", "| FR-1 | Orders over 100").replace(
                "| FR-1 | Total is the sum of items, before", "| FR-9 | Total is the sum of items, before")
            env.add_change("add-discount", bad, TASKS_2)
            c = env.codes(2)
            self.assertIn("DELTA001", c)
            self.assertIn("DELTA002", c)

    def test_removed_rule_leaves_orphan_criterion(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.finish_change_1()
            only_rule = textwrap.dedent("""\
                # Delta: checkout
                ## REMOVED
                | ID | Reason | Migration |
                |---|---|---|
                | FR-2 | dropped | none |
                """)
            env.add_change("drop-gift", only_rule, "- [ ] T-1 Remove (serves FR-2, D-1)\n")
            self.assertIn("SPEC014", env.codes(2))

    def test_id_collision_between_active_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.add_change("one", DELTA_1, TASKS_OPEN)
            env.add_change("two", DELTA_1, TASKS_OPEN)
            self.assertIn("DELTA005", env.codes(2, "two"))

    def test_open_assumption_and_missing_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            d = env.add_change("add-cart", DELTA_1, TASKS_OPEN, design=DESIGN.replace("## Affected areas", "## Other"))
            p = d / "proposal.md"
            p.write_text(p.read_text().replace("| confirmed |", "| open |"))
            c = env.codes(2)
            self.assertIn("SPEC007", c)
            self.assertIn("SPEC008", c)
            self.assertIn("SPEC013", c)

    def test_approve_records_everything_and_refuses_with_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            d = env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            rc, _ = env.run("--approve", "change")
            self.assertEqual(rc, 2)                                  # needs --by and --words
            rc, out = env.approve()
            self.assertEqual(rc, 0, out)
            f = env.feat("add-cart")
            self.assertEqual(f["spec"]["status"], "approved")
            self.assertEqual(f["phase"], "apply")
            self.assertIn("ADDED:FR-1", f["spec"]["rows"])
            self.assertIn("Status: Approved", (d / "proposal.md").read_text())
            self.assertIn("| Proposal | 1.0 | yes, approved | Dev |", (d / "review_log.md").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.add_change("add-cart", DELTA_1.replace("| AC-2 | FR-2 | a gift card pays | Q-1 |\n", ""), TASKS_OPEN)
            rc, out = env.approve()
            self.assertEqual(rc, 1)
            self.assertIn("SPEC001", out)
            self.assertNotEqual(env.feat("add-cart")["spec"]["status"], "approved")

    def test_amendment_versus_delta_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            d = env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertEqual(env.approve()[0], 0)
            (d / "design.md").write_text((d / "design.md").read_text().replace("tests use plain functions", "tests use plain functions only"))
            c = env.codes(3)
            self.assertEqual(c.get("SPEC012"), "warning")
            self.assertNotIn("SPEC010", c)
            self.assertEqual(env.codes(5).get("SPEC012"), "error")
            rc, out = env.run("--amend", "--note", "clarified the code facts")
            self.assertEqual(rc, 0, out)
            self.assertEqual(len(env.feat("add-cart")["amendments"]), 1)
            self.assertNotIn("SPEC012", env.codes(3))
            # a delta row changes: not an amendment
            s = d / "specs" / "checkout" / "spec.md"
            s.write_text(s.read_text().replace("total([1,2]) is 3", "total([1,2]) is three"))
            self.assertIn("SPEC010", env.codes(3))
            rc, out = env.run("--amend", "--note", "x")
            self.assertEqual(rc, 1)
            self.assertIn("NOT AN AMENDMENT", out)
            p = d / "proposal.md"
            p.write_text(p.read_text().replace("Version: 1.0", "Version: 1.1"))
            self.assertEqual(env.approve()[0], 0)
            self.assertEqual(env.feat("add-cart")["spec"]["version"], "1.1")


# ---- tests and coverage ------------------------------------------------------------------------------------

class CoverageTests(unittest.TestCase):
    def ready(self, tmp, cases):
        env = Env(tmp, cases)
        env.add_change("add-cart", DELTA_1, TASKS_OPEN)
        self.assertEqual(env.approve()[0], 0)
        return env

    def test_every_ac_needs_a_test_in_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.ready(tmp, [("test_AC1_a", "fail")])
            self.assertIn("TEST001", env.codes(3))                    # AC-2 has none
        with tempfile.TemporaryDirectory() as tmp:
            env = self.ready(tmp, [("test_AC1_a", "fail"), ("test_AC2_b", "fail")])
            self.assertNotIn("TEST001", env.codes(3))

    def test_mention_in_a_file_or_a_skipped_test_is_no_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.ready(tmp, [("test_AC1_a", "fail"), ("test_AC2_b", "skip")])
            self.assertIn("TEST001", env.codes(3))                    # the test file names AC-2, the run skips it

    def test_unknown_ac_and_new_test_without_ac(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.ready(tmp, [("test_AC1_a", "fail"), ("test_AC2_b", "fail"), ("test_AC9_z", "fail"), ("test_new", "pass")])
            st = json.loads((env.root / common.STATE).read_text())
            st["changes"]["add-cart"]["baselineTests"] = ["test_cart::test_old"]
            (env.root / common.STATE).write_text(json.dumps(st))
            c = env.codes(3)
            self.assertIn("TEST002", c)
            self.assertIn("TEST005", c)

    def test_passing_new_test_warns_and_gate_4_needs_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.ready(tmp, [("test_AC1_a", "pass"), ("test_AC2_b", "fail")])
            self.assertEqual(env.codes(3).get("TEST006"), "warning")
            c = env.codes(4)
            self.assertIn("TEST004", c)                               # AC-2 fails
            self.assertIn("TEST003", c)
            self.assertIn("TASK004", c)                               # tasks not ticked

    def test_modified_criterion_needs_a_failing_test_and_removed_one_loses_its_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            self.assertEqual(env.finish_change_1()[0], 0)
            env.add_change("add-discount", DELTA_2, TASKS_2)
            self.assertEqual(env.approve()[0], 0)
            env.set_cases([("test_AC1_a", "pass"), ("test_AC2_b", "pass"), ("test_AC3_c", "fail")])
            c = env.codes(3)
            self.assertEqual(c.get("TEST007"), "error")               # AC-1 was modified, its test still passes
            rc, out = env.run("--gate", "3")
            self.assertIn("AC-2, which this change removes", out)
            env.set_cases([("test_AC1_a", "fail"), ("test_AC3_c", "fail")])
            c = env.codes(3)
            self.assertNotIn("TEST007", c)
            self.assertNotIn("TEST002", c)

    def test_matrix_is_printed_on_request_and_never_written_as_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.ready(tmp, [("test_AC1_a", "fail"), ("test_AC2_b", "fail")])
            env.codes(3)
            self.assertEqual(list(env.root.rglob("traceability.md")), [])
            rc, m1 = env.run("--matrix")
            rc, m2 = env.run("--matrix")
            self.assertEqual(m1, m2)                                                    # deterministic
            self.assertIn("| FR-1 | ADDED | Total is the sum of items | AC-1 | test_cart::test_AC1_a | FAIL |", m1)
            self.assertIn("| test_cart::test_AC1_a | AC-1 | AC-1: total([1,2]) is 3 | FAIL |", m1)
            self.assertIn("| D-1 | Pure function | Q-1 | T-1 |", m1)
            out = env.root / "matrix.md"
            rc, _ = env.run("--export", str(out))
            self.assertEqual(rc, 0)
            self.assertIn("| FR-1 | ADDED |", out.read_text())
            self.assertEqual(list(env.root.rglob("traceability.md")), [])


# ---- archive, lock, audit ----------------------------------------------------------------------------------

class ArchiveTests(unittest.TestCase):
    def test_archive_creates_living_spec_baseline_and_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            rc, out = env.finish_change_1()
            self.assertEqual(rc, 0, out)
            text = env.spec_path().read_text()
            self.assertIn("| FR-1 | Total is the sum of items | Q-1 (add-cart) |", text)
            base = store.read_baseline(env.root, "checkout")
            self.assertEqual(base["nodes"]["tests/test_cart.py::test_AC1_a"][0], "test")
            self.assertIn(("tests/test_cart.py::test_AC1_a", "AC-1", "verifies"), base["edges"])
            self.assertIn(("AC-1", "FR-1", "covers"), base["edges"])
            self.assertIn(("shop/cart.py", "add-cart/T-2", "built_by"), base["edges"])       # a task with files only: a file link
            self.assertEqual(base["nodes"]["add-cart/Q-1"][0], "question")
            ledger_lines = (env.root / ".tracespec/specs/checkout/history.jsonl").read_text().strip().splitlines()
            self.assertEqual(len(ledger_lines), 1)
            self.assertEqual(json.loads(ledger_lines[0])["traceHash"], base["hash"])
            self.assertFalse((env.root / ".tracespec/specs/checkout/trace.json").exists())    # the store is binary now
            self.assertFalse((env.root / ".tracespec/specs/traceability.md").exists())        # and no matrix file is written
            self.assertEqual(list((env.root / ".tracespec/changes/archive").rglob("traceability.md")), [])
            self.assertFalse((env.root / ".tracespec/changes/add-cart").exists())
            self.assertEqual(len(list((env.root / ".tracespec/changes/archive").glob("*-add-cart"))), 1)
            self.assertEqual(env.feat("add-cart")["phase"], "archived")
            self.assertIsNone(env.state["activeChange"])

    def test_archive_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertEqual(env.approve()[0], 0)
            self.assertEqual(env.run("--archive")[0], 2)                                  # needs --ir-open
            rc, out = env.run("--archive", "--ir-open", "0")
            self.assertEqual(rc, 1)
            self.assertIn("TASK004", out)                                                 # tasks not ticked
            env.tasks_file("add-cart").write_text(TASKS_DONE_1)
            rc, out = env.run("--archive", "--ir-open", "2")
            self.assertEqual(rc, 1)
            self.assertIn("still open", out)
            env.set_cases([("test_AC1_a", "pass"), ("test_AC2_b", "fail")])
            rc, out = env.run("--archive", "--ir-open", "0")
            self.assertEqual(rc, 1)
            self.assertIn("TEST004", out)
            self.assertFalse(env.spec_path().exists())                                    # nothing was written

    def test_second_change_modifies_and_withdraws(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            self.assertEqual(env.finish_change_1()[0], 0)
            env.add_change("add-discount", DELTA_2, TASKS_2)
            self.assertEqual(env.approve()[0], 0)
            env.tasks_file("add-discount").write_text(TASKS_2.replace("[ ]", "[x]") .replace("needs T-1)", "needs T-1) files: shop/cart.py"))
            (env.root / "tests" / "test_cart.py").write_text("def test_AC1_a(): pass\ndef test_AC3_c(): pass\n")
            env.set_cases([("test_AC1_a", "pass"), ("test_AC3_c", "pass")])
            rc, out = env.run("--archive", "--ir-open", "0")
            self.assertEqual(rc, 0, out)
            cap = living.parse_living(env.spec_path().read_text())
            self.assertEqual(sorted(cap["rules"]), ["FR-1", "FR-3"])
            self.assertEqual(sorted(cap["withdrawn"]), ["AC-2", "FR-2"])
            self.assertIn("before any discount", cap["rules"]["FR-1"][1])
            self.assertEqual(len((env.root / ".tracespec/specs/checkout/history.jsonl").read_text().strip().splitlines()), 2)
            self.assertEqual(env.run("--audit", "--no-run")[0], 0)

    def test_stale_base_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            self.assertEqual(env.finish_change_1()[0], 0)
            other = textwrap.dedent("""\
                # Delta: checkout
                ## MODIFIED
                ### Rules
                | ID | Rule | Source |
                |---|---|---|
                | FR-1 | Total is the sum of item prices | Q-1 |
                """)
            env.add_change("other", other, "- [ ] T-1 Skeleton (serves D-1)\n- [ ] T-2 Reword (serves FR-1, AC-1)\n")
            self.assertEqual(env.approve("other")[0], 0)
            env.add_change("add-discount", DELTA_2, TASKS_2)
            self.assertEqual(env.approve("add-discount")[0], 0)
            env.tasks_file("add-discount").write_text(TASKS_2.replace("[ ]", "[x]"))
            (env.root / "tests" / "test_cart.py").write_text("def test_AC1_a(): pass\ndef test_AC3_c(): pass\n")
            env.set_cases([("test_AC1_a", "pass"), ("test_AC3_c", "pass")])
            self.assertEqual(env.run("--archive", "--ir-open", "0", "--change", "add-discount")[0], 0)
            self.assertIn("DELTA010", env.codes(3, "other"))


class AuditTests(unittest.TestCase):
    def archived(self, tmp):
        env = Env(tmp)
        rc, out = env.finish_change_1()
        self.assertEqual(rc, 0, out)
        return env

    def test_clean_after_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.archived(tmp)
            rc, out = env.run("--audit")
            self.assertEqual(rc, 0, out)
            self.assertIn("0 error(s)", out)

    def test_code_drift_names_the_requirements_and_reconfirm_clears_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.archived(tmp)
            (env.root / "shop" / "cart.py").write_text("def total(items):\n    return sum(items) + 0\n")
            rc, out = env.run("--audit", "--no-run")
            self.assertEqual(rc, 1)
            self.assertIn("DRIFT-CODE", out)
            self.assertIn("shop/cart.py", out)
            self.assertIn("FR-1", out)
            self.assertIn("AC-1", out)
            rc, out = env.run("--reconfirm", "checkout", "--note", "refactor, same behaviour")
            self.assertEqual(rc, 0, out)
            self.assertEqual(env.run("--audit", "--no-run")[0], 0)
            lines = (env.root / ".tracespec/specs/checkout/history.jsonl").read_text().strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[1])["event"], "reconfirm")

    def test_test_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.archived(tmp)
            (env.root / "tests" / "test_cart.py").write_text("def test_AC1_a(): assert True\ndef test_AC2_b(): pass\n")
            rc, out = env.run("--audit", "--no-run")
            self.assertEqual(rc, 1)
            self.assertIn("DRIFT-TEST", out)

    def test_hand_edited_spec_is_caught_and_cannot_be_reconfirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.archived(tmp)
            p = env.spec_path()
            p.write_text(p.read_text().replace("sum of items", "sum of all items"))
            rc, out = env.run("--audit", "--no-run")
            self.assertEqual(rc, 1)
            self.assertIn("DRIFT-SPEC", out)
            self.assertIn("FR-1", out)
            rc, out = env.run("--reconfirm", "checkout", "--note", "no")
            self.assertEqual(rc, 1)
            self.assertIn("propose a change", out)

    def test_ledger_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.archived(tmp)
            self.assertEqual(env.run("--reconfirm", "checkout", "--note", "again")[0], 0)
            h = env.root / ".tracespec/specs/checkout/history.jsonl"
            lines = h.read_text().strip().splitlines()
            entry = json.loads(lines[0])
            entry["change"] = "forged"
            h.write_text(json.dumps(entry, sort_keys=True) + "\n" + lines[1] + "\n")
            rc, out = env.run("--audit", "--no-run")
            self.assertEqual(rc, 1)
            self.assertIn("does not continue the chain", out)

    def test_uncovered_criterion_in_a_fresh_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.archived(tmp)
            env.set_cases([("test_AC1_a", "pass")])
            rc, out = env.run("--audit")
            self.assertEqual(rc, 1)
            self.assertIn("UNCOVERED", out)
            self.assertIn("AC-2", out)

    def test_other_capability_is_refreshed_when_its_tests_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.archived(tmp)
            # a second capability linked to the same code file, archived by an unrelated change
            billing = textwrap.dedent("""\
                # Delta: billing
                Purpose: Invoices are built from the checkout total.
                ## ADDED
                ### Rules
                | ID | Rule | Source |
                |---|---|---|
                | FR-10 | An invoice shows the total | Q-1 |
                ### Criteria
                | ID | Covers | Given / When / Then | Source |
                |---|---|---|---|
                | AC-10 | FR-10 | invoice([1]) shows 1 | Q-1 |
                """)
            env.add_change("add-invoice", billing, "- [ ] T-1 Skeleton (serves D-1)\n- [ ] T-2 Invoice (serves FR-10, AC-10, needs T-1)\n", cap="billing")
            self.assertEqual(env.approve()[0], 0)
            env.tasks_file("add-invoice").write_text(
                "- [x] T-1 Skeleton (serves D-1)\n- [x] T-2 Invoice (serves FR-10, AC-10, needs T-1) files: shop/cart.py\n")
            (env.root / "tests" / "test_invoice.py").write_text("def test_AC10_i(): pass\n")
            env.set_cases([("test_AC1_a", "pass"), ("test_AC2_b", "pass"), ("test_AC10_i", "pass")])
            (env.root / "shop" / "cart.py").write_text("def total(items):\n    return sum(items)\n# touched by the invoice change\n")
            rc, out = env.run("--archive", "--ir-open", "0")
            self.assertEqual(rc, 0, out)
            self.assertIn("checkout: reconfirmed", out)                # its shared file changed, its tests pass
            self.assertEqual(env.run("--audit", "--no-run")[0], 0)


class ReadingTests(unittest.TestCase):
    def test_trace_list_show_view_next_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertEqual(env.approve()[0], 0)
            rc, out = env.run("--list")
            self.assertRegex(out, r"add-cart\s+apply\s+approved\s+0/2 tasks")
            rc, out = env.run("--show", "add-cart")
            self.assertIn("ADDED    FR-1", out)
            rc, out = env.run("--next-id", "FR")
            self.assertEqual(out.strip(), "FR-3")
            env.tasks_file("add-cart").write_text(TASKS_DONE_1)
            self.assertEqual(env.run("--archive", "--ir-open", "0")[0], 0)
            rc, out = env.run("--impact", "FR-1")
            self.assertIn("criterion AC-1", out)
            self.assertIn("test tests/test_cart.py::test_AC1_a", out)
            self.assertIn("shop/cart.py", out)
            rc, out = env.run("--impact", "shop/cart.py")
            self.assertIn("rule FR-1", out)
            self.assertIn("==> built by  file shop/cart.py", out)
            rc, out = env.run("--view")
            self.assertIn("checkout", out)
            self.assertIn("2 rules, 2 criteria", out)
            self.assertIn("ok", out)
            self.assertIn("Test results: 2 criteria recorded, 0 stale", out)
            rc, out = env.run("--next-id", "AC")
            self.assertEqual(out.strip(), "AC-3")

    def test_show_diff_for_modified_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            self.assertEqual(env.finish_change_1()[0], 0)
            env.add_change("add-discount", DELTA_2, TASKS_2)
            rc, out = env.run("--show", "add-discount", "--diff")
            self.assertIn("- Total is the sum of items", out)
            self.assertIn("+ Total is the sum of items, before any discount", out)


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class GitTests(unittest.TestCase):
    def test_task_done_records_files_and_needs_passing_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp, [("test_AC1_a", "pass")])
            subprocess.run(["git", "-C", tmp, "init", "-q"], capture_output=True, check=True)
            env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertEqual(env.approve()[0], 0)
            self.assertEqual(env.run("--task-start", "T-2")[0], 0)
            (env.root / "shop" / "cart.py").write_text("def total(items):\n    return sum(items) * 1\n")
            rc, out = env.run("--task-done", "T-2")
            self.assertEqual(rc, 1)                                  # AC-2 has no passing test
            self.assertIn("AC-2", out)
            env.set_cases([("test_AC1_a", "pass"), ("test_AC2_b", "pass")])
            rc, out = env.run("--task-done", "T-2")
            self.assertEqual(rc, 0, out)
            line = [l for l in env.tasks_file("add-cart").read_text().splitlines() if "T-2" in l][0]
            self.assertTrue(line.startswith("- [x]"))
            self.assertIn("files: shop/cart.py", line)

    def test_scope_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            (env.root / "other.py").write_text("y = 1\n")
            subprocess.run(["git", "-C", tmp, "init", "-q"], capture_output=True, check=True)
            env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertEqual(env.run("--baseline")[0], 0)            # other.py is dirty before the change
            self.assertEqual(env.approve()[0], 0)
            env.tasks_file("add-cart").write_text(TASKS_DONE_1)
            (env.root / "stray.py").write_text("z = 1\n")
            rc, out = env.run("--archive", "--ir-open", "0")
            self.assertEqual(rc, 1)
            self.assertIn("CHG001", out)
            self.assertIn("stray.py", out)
            self.assertNotIn("other.py", out)
            (env.root / "stray.py").unlink()
            self.assertEqual(env.run("--archive", "--ir-open", "0")[0], 0)

    def test_the_state_file_does_not_grow_with_tests_or_finished_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertEqual(env.run("--baseline")[0], 0)
            feat = env.feat("add-cart")
            self.assertNotIn("baselineTests", feat)                 # the test names live in the change folder
            self.assertNotIn("baselineDirty", feat)
            baseline = env.root / ".tracespec/changes/add-cart/baseline.json"
            self.assertIn("tests", json.loads(baseline.read_text()))
            self.assertEqual(env.approve()[0], 0)
            env.tasks_file("add-cart").write_text(TASKS_DONE_1)
            self.assertEqual(env.run("--archive", "--ir-open", "0")[0], 0)
            self.assertEqual(list((env.root / ".tracespec/changes/archive").rglob("baseline.json")), [])
            stub = env.feat("add-cart")                              # what is left of a finished change is a small stub
            self.assertEqual(stub["phase"], "archived")
            self.assertIn("archivedAs", stub)
            for gone in ("spec", "gates", "baselineTests", "amendments"):
                self.assertNotIn(gone, stub)
            self.assertIn("approved", env.run("--list")[1])         # and list still reads it


class OverviewTests(unittest.TestCase):
    def ready(self, tmp):
        env = Env(tmp)
        env.add_change("add-cart", DELTA_1, TASKS_OPEN)
        self.assertEqual(env.approve()[0], 0)
        env.tasks_file("add-cart").write_text(TASKS_DONE_1)
        return env

    def test_agent_files_live_in_the_internal_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.ready(tmp)
            self.assertTrue((env.root / ".tracespec" / "changes" / "add-cart" / "proposal.md").is_file())
            self.assertFalse((env.root / "docs" / "changes").exists())
            self.assertFalse((env.root / "docs" / "specs").exists())
            self.assertEqual(env.run("--archive", "--ir-open", "0")[0], 0)
            self.assertTrue((env.root / ".tracespec" / "specs" / "checkout" / "spec.md").is_file())
            self.assertTrue((env.root / "docs" / "features" / "add-cart.md").is_file())     # the one human file
            md = sorted(p.relative_to(env.root).as_posix() for p in (env.root / "docs").rglob("*.md"))
            self.assertEqual(md, ["docs/features/add-cart.md"])

    def test_missing_overview_blocks_the_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.ready(tmp)
            env.overview_path("add-cart").unlink()
            self.assertEqual(env.codes(5).get("OVERVIEW001"), "error")
            self.assertNotIn("OVERVIEW001", env.codes(4))                       # only the close needs it
            rc, out = env.run("--archive", "--ir-open", "0")
            self.assertEqual(rc, 1)
            self.assertIn("OVERVIEW001", out)
            self.assertFalse(env.spec_path().exists())

    def test_overview_command_creates_a_skeleton_with_generated_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.ready(tmp)
            env.overview_path("add-cart").unlink()
            rc, out = env.run("--overview")
            self.assertEqual(rc, 0, out)
            self.assertIn("created", out)
            text = env.overview_path("add-cart").read_text()
            self.assertIn("tracespec:facts:begin", text)
            self.assertIn("### Behavior at a glance", text)
            self.assertIn("| FR-1 | added | Total is the sum of items |", text)
            self.assertIn("`shop/cart.py`", text)                              # from the files recorded on the tasks
            self.assertIn("`tests/test_cart.py`", text)
            self.assertEqual(env.codes(5).get("OVERVIEW005"), "error")          # the narrative is still placeholders
            before = env.overview_path("add-cart").read_text()
            env.run("--overview")
            self.assertEqual(before, env.overview_path("add-cart").read_text())   # refreshing is idempotent

    def test_narrative_is_checked_for_being_there_and_honest(self):
        base = OVERVIEW.format(name="add-cart")
        arch = "## Architecture\nA single pure function computes the total from the list of item prices.\n"
        cases = {
            "OVERVIEW004": base.replace(arch, ""),
            "OVERVIEW007": base.replace("This change adds totals and discounts to checkout so that carts are priced correctly for customers.", "x"),
            "OVERVIEW003": base.replace("`shop/cart.py`", "`shop/missing.py`"),
            "OVERVIEW006": base.replace("<!-- tracespec:facts:begin -->\n", "").replace("<!-- tracespec:facts:end -->\n", ""),
            "OVERVIEW002": base + "\n" * 130,
        }
        for code, text in cases.items():
            with tempfile.TemporaryDirectory() as tmp:
                env = self.ready(tmp)
                env.write_overview("add-cart", text)
                got = env.codes(5)
                self.assertIn(code, got, code)
                self.assertEqual(got[code], "warning" if code == "OVERVIEW002" else "error", code)
        with tempfile.TemporaryDirectory() as tmp:
            env = self.ready(tmp)
            self.assertNotIn("OVERVIEW003", env.codes(5))
            self.assertEqual({k for k, v in env.codes(5).items() if v == "error"}, set())

    def test_facts_are_refreshed_at_archive_and_the_narrative_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.ready(tmp)
            narrative = env.overview_path("add-cart").read_text().split("## Facts (generated)")[0]
            self.assertEqual(env.run("--archive", "--ir-open", "0")[0], 0)
            text = env.overview_path("add-cart").read_text()
            self.assertTrue(text.startswith(narrative))
            self.assertIn("**Status:** archived", text)
            self.assertIn(".tracespec/changes/archive/", text)
            self.assertIn("| FR-1 | added |", text)
            self.assertIn("2 of 2 rules and 2 of 2 criteria pass", text)


class RegressionTests(unittest.TestCase):
    def test_task_done_does_not_need_a_test_for_a_removed_criterion(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            self.assertEqual(env.finish_change_1()[0], 0)
            env.add_change("add-discount", DELTA_2, TASKS_2)
            self.assertEqual(env.approve()[0], 0)
            env.set_cases([("test_AC1_a", "pass"), ("test_AC3_c", "pass")])     # AC-2 is removed: it has no test
            rc, out = env.run("--task-done", "T-2")
            self.assertEqual(rc, 0, out)
            self.assertIn("warning: no --task-start", out)

    def test_missing_code_links_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertEqual(env.approve()[0], 0)
            env.tasks_file("add-cart").write_text(TASKS_DONE_1.replace(" files: shop/cart.py", ""))
            c = env.codes(4)
            self.assertEqual(c.get("LINK001"), "warning")
            self.assertEqual(env.run("--archive", "--ir-open", "0")[0], 0)      # a warning does not block


# ---- the small tier ----------------------------------------------------------------------------------------

SMALL = PROPOSAL.format(name="small-one") + textwrap.dedent("""\

    ## Capability: checkout
    Purpose: Totals and discounts for the checkout of a cart.
    ### ADDED
    #### Rules
    | ID | Rule | Source |
    |---|---|---|
    | FR-1 | Total is the sum of items | Q-1 |
    #### Criteria
    | ID | Covers | Given / When / Then | Source |
    |---|---|---|---|
    | AC-1 | FR-1 | total([1,2]) is 3 | Q-1 |

    ## Existing code facts
    - plain functions
    ## Design decisions
    | ID | Decision | Why | Source |
    |---|---|---|---|
    | D-1 | Pure function | style | Q-1 |
    ## Interfaces the tests call
    total(items)
    ## Affected areas
    | Path | New or changed | What |
    |---|---|---|
    | shop/cart.py | changed | total |
    ## Tasks
    - [ ] T-1 Skeleton (serves D-1)
    - [ ] T-2 Total (serves FR-1, AC-1, needs T-1)
    """)


class SmallTierTests(unittest.TestCase):
    def test_one_document_goes_all_the_way(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp, [("test_AC1_a", "pass")])
            d = env.root / ".tracespec" / "changes" / "small-one"
            d.mkdir(parents=True)
            (d / "proposal.md").write_text(SMALL)
            env.reload()
            env.state["changes"]["small-one"] = {"tier": "small", "phase": "propose", "spec": {"status": "draft"}}
            env.state["activeChange"] = "small-one"
            env.save()
            env.write_overview("small-one")
            self.assertEqual({k for k, v in env.codes(2).items() if v == "error"}, set())
            rc, out = env.approve()
            self.assertEqual(rc, 0, out)
            p = d / "proposal.md"
            p.write_text(p.read_text().replace("- [ ] T-1", "- [x] T-1").replace("- [ ] T-2", "- [x] T-2"))
            rc, out = env.run("--archive", "--ir-open", "0")
            self.assertEqual(rc, 0, out)
            self.assertIn("FR-1", env.spec_path().read_text())

    def test_small_tier_warns_when_it_outgrows(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            d = env.root / ".tracespec" / "changes" / "small-one"
            d.mkdir(parents=True)
            extra_rules = "".join(f"| FR-{n} | rule {n} | Q-1 |\n" for n in (2, 3, 4))
            extra_acs = "".join(f"| AC-{n} | FR-{n} | x | Q-1 |\n" for n in (2, 3, 4))
            text = SMALL.replace("| FR-1 | Total is the sum of items | Q-1 |\n", "| FR-1 | Total is the sum of items | Q-1 |\n" + extra_rules)
            text = text.replace("| AC-1 | FR-1 | total([1,2]) is 3 | Q-1 |\n", "| AC-1 | FR-1 | total([1,2]) is 3 | Q-1 |\n" + extra_acs)
            (d / "proposal.md").write_text(text)
            env.reload()
            env.state["changes"]["small-one"] = {"tier": "small", "phase": "propose", "spec": {"status": "draft"}}
            env.state["activeChange"] = "small-one"
            env.save()
            self.assertEqual(env.codes(2).get("TIER001"), "warning")


if __name__ == "__main__":
    unittest.main()
