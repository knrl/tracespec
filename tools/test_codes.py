"""One trigger test and one clean-case check for finding codes that had no test of their own.
Run: python -m unittest test_codes   (from the tools folder)"""
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import common  # noqa: E402
import living  # noqa: E402
from test_flow import DELTA_1, DESIGN, PROPOSAL, TASKS_OPEN, Env  # noqa: E402


class CodeCase(unittest.TestCase):
    """add_change builds a valid change; each test breaks one thing and expects exactly the code it names."""

    def good(self, env, gate):
        env.add_change("add-cart", DELTA_1, TASKS_OPEN)
        return env.codes(gate)

    def broken(self, gate, code, *, delta=DELTA_1, tasks=TASKS_OPEN, extra="", design=DESIGN, proposal=None, after=None):
        """The codes of a project where one thing is wrong, and of the same project without that mistake."""
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            clean = self.good(env, gate)
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            d = env.add_change("add-cart", delta, tasks, proposal_extra=extra, design=design)
            if proposal is not None:
                (d / "proposal.md").write_text(proposal)
            if after:
                after(env, d)
            found = env.codes(gate)
        self.assertNotIn(code, clean, f"{code} fires on a valid change")
        self.assertIn(code, found, f"{code} did not fire")
        return found


class ProposalCodes(CodeCase):
    def test_clr001_no_recorded_question(self):
        self.broken(1, "CLR001", proposal=PROPOSAL.format(name="add-cart").replace("| Q-1 | How should it work? | As described |\n", ""))

    def test_spec000_no_proposal(self):
        self.broken(1, "SPEC000", after=lambda env, d: (d / "proposal.md").unlink())

    def test_spec002_an_id_defined_nowhere(self):
        self.broken(2, "SPEC002", extra="\nSee FR-9 for the details.\n")

    def test_spec003_an_id_defined_twice(self):
        self.broken(2, "SPEC003", extra="\n## More\n| ID | Question | Answer |\n|---|---|---|\n| Q-1 | Again | yes |\n")

    def test_spec006_no_version_line(self):
        self.broken(2, "SPEC006", proposal=PROPOSAL.format(name="add-cart").replace("Version: 1.0\n", ""))

    def test_spec009_a_placeholder_is_left(self):
        self.broken(2, "SPEC009", extra="\nTBD later\n")

    def test_spec011_says_approved_but_is_not(self):
        self.broken(2, "SPEC011", proposal=PROPOSAL.format(name="add-cart").replace("Status: Draft, for approval", "Status: Approved"))

    def test_gate001_tests_before_the_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertIn("GATE001", env.codes(3))
            self.assertEqual(env.approve()[0], 0)
            self.assertNotIn("GATE001", env.codes(3))

    def test_state001_a_bad_layout_entry(self):
        def corrupt(env, d):
            env.reload()
            env.state["layout"]["tests"] = 5
            env.save()
        self.broken(2, "STATE001", after=corrupt)

    def test_state002_no_active_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            self.assertIn("STATE002", env.codes(2))
            self.assertNotIn("STATE002", self.good(Env(tempfile.mkdtemp()), 2))


class DeltaCodes(CodeCase):
    def test_delta006_rows_outside_a_capability(self):
        stray = "\n## ADDED\n### Rules\n| ID | Rule | Source |\n|---|---|---|\n| FR-7 | Stray rule | Q-1 |\n"
        self.broken(2, "DELTA006", extra=stray)

    def test_delta011_an_id_in_two_capabilities(self):
        def second_capability(env, d):
            (d / "specs" / "other").mkdir()
            (d / "specs" / "other" / "spec.md").write_text(textwrap.dedent("""\
                # Delta: other
                Purpose: Another capability that also claims FR-1 by mistake.
                ## ADDED
                ### Rules
                | ID | Rule | Source |
                |---|---|---|
                | FR-1 | Same ID again | Q-1 |
                """))
        self.broken(2, "DELTA011", after=second_capability)

    def test_delta012_no_delta_rows(self):
        self.broken(2, "DELTA012", delta="# Delta: checkout\nPurpose: Totals and discounts for the checkout of a cart.\n")

    def test_delta008_too_few_columns_and_delta011_duplicate_in_one_delta(self):
        _, problems, _ = living.merge(None, [{"cap": "c", "op": "ADDED", "id": "FR-1", "cells": ["FR-1"]}], "c1",
                                      "Totals and discounts for the checkout.")
        self.assertIn("DELTA008", [c for c, _ in problems])
        row = {"cap": "c", "op": "ADDED", "id": "FR-1", "cells": ["FR-1", "rule", "Q-1"]}
        _, problems, _ = living.merge(None, [row, dict(row)], "c1", "Totals and discounts for the checkout.")
        self.assertIn("DELTA011", [c for c, _ in problems])
        _, problems, _ = living.merge(None, [row], "c1", "Totals and discounts for the checkout.")      # clean case
        self.assertEqual([c for c, _ in problems], [])


class LivingStateCodes(unittest.TestCase):
    def test_spec004_a_criterion_that_covers_nothing_and_spec005_a_rule_with_no_source(self):
        cap = living.empty_cap()
        cap["rules"]["FR-1"] = ["FR-1", "A rule", "Q-1"]
        cap["criteria"]["AC-1"] = ["AC-1", "FR-1", "when x then y", "Q-1"]
        self.assertEqual(living.validate_state(cap), [])                                                   # clean case
        cap["criteria"]["AC-1"] = ["AC-1", "nothing", "when x then y", "Q-1"]
        self.assertIn("SPEC004", [c for c, _ in living.validate_state(cap)])
        cap["criteria"]["AC-1"] = ["AC-1", "FR-1", "when x then y", "Q-1"]
        cap["rules"]["FR-1"] = ["FR-1", "A rule", ""]
        self.assertIn("SPEC005", [c for c, _ in living.validate_state(cap)])


class TaskCodes(CodeCase):
    def test_task000_no_task_list(self):
        self.broken(3, "TASK000", tasks=None)

    def test_task001_a_criterion_in_no_task(self):
        self.broken(3, "TASK001", tasks="- [ ] T-1 Skeleton (serves D-1)\n- [ ] T-2 Total (serves FR-1, FR-2, AC-1, needs T-1)\n")

    def test_task002_a_decision_in_no_task(self):
        self.broken(3, "TASK002", tasks="- [ ] T-2 Total (serves FR-1, FR-2, AC-1, AC-2)\n")

    def test_task003_a_task_serves_something_undefined(self):
        self.broken(3, "TASK003", tasks=TASKS_OPEN.replace("serves FR-1,", "serves FR-1, FR-9,"))

    def test_test008_no_baseline_is_a_warning_until_one_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertEqual(env.codes(3).get("TEST008"), "warning")
            self.assertEqual(env.run("--baseline")[0], 0)
            self.assertNotIn("TEST008", env.codes(3))


class FixedGapTests(unittest.TestCase):
    def test_a_result_with_no_baseline_goes_stale_when_any_code_changes(self):
        import current
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            layout = common.layout_of(env.root)[0]
            current.sync(env.root, layout)
            cases = [{"name": "t::test_AC99_x", "status": "pass", "ids": ["AC-99"]}]
            current.record_run(env.root, cases, {})                      # AC-99 is in no baseline: a change in flight
            self.assertFalse(current.run_state(env.root)["AC-99"]["stale"])
            (env.root / "shop" / "cart.py").write_text("def total(items):\n    return sum(items) + 1\n")
            current.sync(env.root, layout)
            self.assertTrue(current.run_state(env.root)["AC-99"]["stale"])

    def test_a_deleted_capability_folder_is_found_by_the_audit(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            self.assertEqual(env.finish_change_1()[0], 0)
            rc, out = env.run("--audit", "--no-run")
            self.assertEqual(rc, 0, out)
            self.assertIn("checkout", (env.root / ".tracespec" / "specs" / "index.json").read_text())
            shutil.rmtree(env.root / ".tracespec" / "specs" / "checkout")
            rc, out = env.run("--audit", "--no-run")
            self.assertEqual(rc, 1, out)
            self.assertIn("folder was deleted", out)

    def test_a_binary_file_gets_no_symbols(self):
        import current
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            (env.root / "shop" / "blob.bin").write_bytes(b"@\x00\x01\x02 def not_code():\n    pass\n")
            layout = common.layout_of(env.root)[0]
            current.sync(env.root, layout)
            ids = set(current.current_symbols(env.root))
            self.assertTrue(any(i.startswith("shop/cart.py::") for i in ids))
            self.assertEqual([i for i in ids if i.startswith("shop/blob.bin")], [])
            self.assertIn("shop/blob.bin", current.current_files(env.root))      # still tracked as a file

    def test_list_marks_an_archived_change_as_finished(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            self.assertEqual(env.finish_change_1()[0], 0)
            rc, out = env.run("--list")
            self.assertIn("finished", out)
            self.assertNotIn("no tasks", out)


class StateFileCodes(unittest.TestCase):
    def test_the_state_file_name_is_what_the_tests_assume(self):
        self.assertEqual(common.STATE, ".tracespec.json")


if __name__ == "__main__":
    unittest.main()
