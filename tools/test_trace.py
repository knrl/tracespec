"""Tests of the symbol-level links, the live layer, optional external references, and the trace query.
Run: python -m unittest test_trace   (from the tools folder)"""
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
import current  # noqa: E402
import store  # noqa: E402
import symbols  # noqa: E402
from test_flow import DELTA_1, DELTA_2, OVERVIEW, TASKS_OPEN, Env  # noqa: E402

CART = "def total(items):\n    return sum(items)\n\n\ndef tax(v):\n    return v\n"
LAYOUT = {"tests": ["tests/**"], "code": ["shop/**"], "protected": []}
SYMBOL_TASKS = ("- [x] T-1 Skeleton (serves D-1)\n"
                "- [x] T-2 Total (serves FR-1, FR-2, AC-1, AC-2, needs T-1) files: shop/cart.py symbols: shop/cart.py::total\n")


def archived(tmp, refs=None):
    env = Env(tmp)
    (env.root / "shop" / "cart.py").write_text(CART)
    env.add_change("add-cart", DELTA_1, TASKS_OPEN)
    if refs:
        p = env.root / ".tracespec/changes/add-cart/proposal.md"
        p.write_text(p.read_text().replace("Change: add-cart\n", f"Change: add-cart\nRef: {refs}\n"))
    assert env.approve()[0] == 0
    env.tasks_file("add-cart").write_text(SYMBOL_TASKS)
    rc, out = env.run("--archive", "--ir-open", "0")
    assert rc == 0, out
    return env


# ---- symbols -----------------------------------------------------------------------------------------------

class SymbolTests(unittest.TestCase):
    def test_python_symbols_are_exact(self):
        src = '"""doc"""\nX = 1\n\n\ndef total(items):\n    return sum(items)\n\n\nclass Cart:\n    def add(self, x):\n        return x\n\n' \
              '    @staticmethod\n    def make():\n        return Cart()\n'
        r = symbols.resolve(Path("."), "shop/cart.py", src)
        self.assertEqual(r["resolver"], "ast")
        ids = {s["id"]: s for s in r["symbols"]}
        self.assertEqual(set(ids), {"shop/cart.py::total", "shop/cart.py::Cart", "shop/cart.py::Cart.add",
                                    "shop/cart.py::Cart.make", "shop/cart.py::<module>"})
        self.assertEqual((ids["shop/cart.py::total"]["start"], ids["shop/cart.py::total"]["end"]), (5, 6))
        self.assertEqual(ids["shop/cart.py::Cart.make"]["start"], 13)          # the decorator belongs to the method

    def test_hash_ignores_line_endings_and_trailing_blanks_but_not_content(self):
        a = symbols.text_hash("def f():\n    return 1\n")
        self.assertEqual(a, symbols.text_hash("def f():  \r\n    return 1\r\n\r\n"))
        self.assertNotEqual(a, symbols.text_hash("def f():\n    return 2\n"))

    def test_edit_in_one_function_changes_only_its_hash(self):
        a = {s["id"]: s["hash"] for s in symbols.resolve(Path("."), "x.py", CART)["symbols"]}
        b = {s["id"]: s["hash"] for s in symbols.resolve(Path("."), "x.py", CART.replace("return v", "return v * 2"))["symbols"]}
        self.assertEqual([i for i in a if a[i] != b[i]], ["x.py::tax"])

    def test_syntax_error_falls_back_to_regions(self):
        r = symbols.resolve(Path("."), "x.py", "def broken(:\n    pass\n")
        self.assertEqual(r["resolver"], "regions")

    def test_regions_for_other_languages(self):
        js = "function total(items) {\n  return items.reduce((a, b) => a + b, 0);\n}\n\nfunction tax(v) {\n  return v * 0.2;\n}\n"
        r = symbols.resolve(Path("."), "shop/cart.js", js)
        self.assertEqual([s["name"] for s in r["symbols"]], ["@function total(items) {", "@function tax(v) {"])
        self.assertEqual((r["symbols"][0]["start"], r["symbols"][0]["end"]), (1, 3))      # the closing brace stays in its block

    def test_ctags_json_is_parsed(self):
        out = "\n".join(json.dumps(t) for t in (
            {"_type": "tag", "name": "total", "kind": "function", "line": 1, "end": 3},
            {"_type": "tag", "name": "add", "kind": "method", "line": 6, "end": 8, "scope": "class:Cart"},
            {"_type": "tag", "name": "X", "kind": "variable", "line": 1, "end": 1}))
        syms = symbols.parse_ctags_json(out, "a.js", "\n".join(["l"] * 10))
        self.assertEqual([s["id"] for s in syms], ["a.js::total", "a.js::Cart.add"])
        self.assertIsNone(symbols.parse_ctags_json(json.dumps({"_type": "tag", "name": "f", "kind": "function", "line": 1}), "a.js", "x"))

    def test_duplicate_names_get_unique_ids(self):
        r = symbols.region_symbols("a.txt", "dup\n  x\ndup\n  y\n")
        self.assertEqual([s["id"] for s in r], ["a.txt::@dup", "a.txt::@dup#2"])


# ---- the store and the live layer --------------------------------------------------------------------------

class StoreTests(unittest.TestCase):
    def test_baseline_round_trip_and_canonical_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            nodes = {"FR-1": ("rule", "total", "h1"), "AC-1": ("criterion", "t", "h2")}
            edges = {("AC-1", "FR-1", "covers")}
            h = store.write_baseline(p, "checkout", nodes, edges, {"capability": "checkout"})
            b = store.read_baseline(p, "checkout")
            self.assertEqual((b["nodes"], b["edges"], b["hash"]), (nodes, edges, h))
            self.assertEqual(h, store.canonical_hash(dict(reversed(list(nodes.items()))), set(edges), {"capability": "checkout"}))
            self.assertIsNone(store.read_baseline(p, "nothing"))

    def test_cache_folder_is_kept_out_of_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            with store.cache(Path(tmp)):
                pass
            self.assertEqual((Path(tmp) / ".tracespec" / ".gitignore").read_text().strip(), "cache/")

    def test_sync_is_incremental(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "shop").mkdir()
            (p / "tests").mkdir()
            (p / "shop" / "cart.py").write_text(CART)
            (p / "tests" / "test_cart.py").write_text("def test_AC1_a():\n    pass\n")
            self.assertEqual(current.sync(p, LAYOUT)["reparsed"], 2)
            self.assertEqual(current.sync(p, LAYOUT), {"files": 2, "rehashed": 0, "reparsed": 0, "gone": 0})
            time.sleep(0.02)
            (p / "shop" / "cart.py").write_text(CART.replace("return v", "return v + 1"))
            s = current.sync(p, LAYOUT)
            self.assertEqual((s["reparsed"], s["files"]), (1, 2))
            (p / "shop" / "cart.py").unlink()
            self.assertEqual(current.sync(p, LAYOUT)["gone"], 1)


# ---- tasks record symbols ----------------------------------------------------------------------------------

class TaskSymbolTests(unittest.TestCase):
    def test_task_done_records_only_the_touched_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            (env.root / "shop" / "cart.py").write_text(CART)
            env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertEqual(env.approve()[0], 0)
            rc, out = env.run("--task-start", "T-2")
            self.assertEqual(rc, 0, out)
            time.sleep(0.02)
            (env.root / "shop" / "cart.py").write_text(CART.replace("sum(items)", "float(sum(items))"))
            rc, out = env.run("--task-done", "T-2")
            self.assertEqual(rc, 0, out)
            line = [l for l in env.tasks_file("add-cart").read_text().splitlines() if "T-2" in l][0]
            self.assertIn("symbols: shop/cart.py::total", line)
            self.assertNotIn("tax", line)                                # an untouched function in the same file
            self.assertIn("files: shop/cart.py", line)
            self.assertIn("1 symbol(s) in 1 file(s)", out)

    def test_task_done_without_a_start_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertEqual(env.approve()[0], 0)
            rc, out = env.run("--task-done", "T-1")
            self.assertEqual(rc, 0, out)
            self.assertIn("warning: no --task-start", out)


# ---- the audit at symbol level -----------------------------------------------------------------------------

class SymbolAuditTests(unittest.TestCase):
    def test_edit_elsewhere_in_the_file_is_not_drift_but_an_edit_of_the_linked_symbol_is(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = archived(tmp)
            self.assertEqual(env.run("--audit", "--no-run")[0], 0)
            (env.root / "shop" / "cart.py").write_text(CART.replace("return v", "return v * 2"))     # tax only
            rc, out = env.run("--audit", "--no-run")
            self.assertEqual(rc, 0, out)
            (env.root / "shop" / "cart.py").write_text(CART.replace("sum(items)", "sum(items) + 0"))  # total
            rc, out = env.run("--audit", "--no-run")
            self.assertEqual(rc, 1)
            self.assertIn("DRIFT-CODE", out)
            self.assertIn("shop/cart.py::total", out)
            self.assertIn("FR-1", out)
            self.assertIn("AC-2", out)

    def test_a_moved_symbol_is_recognised_and_reconfirm_follows_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = archived(tmp)
            (env.root / "shop" / "cart.py").write_text("def tax(v):\n    return v\n")
            (env.root / "shop" / "pricing.py").write_text("def total(items):\n    return sum(items)\n")
            rc, out = env.run("--audit", "--no-run")
            self.assertEqual(rc, 1)
            self.assertIn("same text is now at shop/pricing.py::total", out)
            rc, out = env.run("--reconfirm", "checkout", "--note", "moved the function")
            self.assertEqual(rc, 0, out)
            self.assertIn("shop/cart.py::total -> shop/pricing.py::total", out)
            self.assertEqual(env.run("--audit", "--no-run")[0], 0)

    def test_a_deleted_symbol_is_drift_and_is_unlinked_on_reconfirm(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = archived(tmp)
            (env.root / "shop" / "cart.py").write_text("def tax(v):\n    return v\n")
            rc, out = env.run("--audit", "--no-run")
            self.assertIn("was deleted or renamed", out)
            rc, out = env.run("--reconfirm", "checkout", "--note", "removed it")
            self.assertEqual(rc, 0, out)
            self.assertIn("UNLINKED (gone): shop/cart.py::total", out)

    def test_a_forged_baseline_is_caught_by_the_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = archived(tmp)
            db = env.root / ".tracespec/specs/checkout/trace.db"
            import sqlite3
            conn = sqlite3.connect(db)
            conn.execute("DELETE FROM edge WHERE kind='built_by'")
            conn.commit()
            conn.close()
            rc, out = env.run("--audit", "--no-run")
            self.assertEqual(rc, 1)
            self.assertIn("trace.db differs from the hash in the last ledger line", out)


# ---- stale results -----------------------------------------------------------------------------------------

class StaleTests(unittest.TestCase):
    def test_a_result_goes_stale_when_a_linked_symbol_changes_and_fresh_after_a_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = archived(tmp)
            rc, out = env.run("--trace", "AC-1")
            self.assertIn("run: PASS (fresh)", out)
            time.sleep(0.02)
            (env.root / "shop" / "cart.py").write_text(CART.replace("sum(items)", "sum(items) + 0"))
            rc, out = env.run("--trace", "AC-1")
            self.assertIn("run: PASS (stale", out)
            env.run("--audit")                                          # a new run is recorded against the new code
            rc, out = env.run("--trace", "AC-1")
            self.assertIn("run: PASS (fresh)", out)


# ---- optional external references --------------------------------------------------------------------------

class RefTests(unittest.TestCase):
    def test_change_level_ref_links_every_rule_and_is_queryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = archived(tmp, refs="JIRA-482")
            rc, out = env.run("--trace", "JIRA-482")
            self.assertEqual(rc, 0, out)
            for needle in ("rule FR-1", "rule FR-2", "criterion AC-1", "test tests/test_cart.py::test_AC1_a", "code shop/cart.py::total"):
                self.assertIn(needle, out)
            rc, out = env.run("--trace", "FR-1", "--up")
            self.assertIn("ref JIRA-482", out)

    def test_goal_ref_reaches_the_rules_that_cite_the_goal(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            d = env.add_change("add-cart", DELTA_1.replace("| FR-2 | Gift cards are accepted | Q-1 |", "| FR-2 | Gift cards are accepted | G-1 |"), TASKS_OPEN)
            p = d / "proposal.md"
            p.write_text(p.read_text().replace("| ID | Goal | Source |\n|---|---|---|\n| G-1 | The goal | Q-1 |",
                                               "| ID | Goal | Source | Ref |\n|---|---|---|---|\n| G-1 | The goal | Q-1 | GH#45, JIRA-7 |"))
            self.assertEqual(env.approve()[0], 0)
            env.tasks_file("add-cart").write_text(SYMBOL_TASKS)
            self.assertEqual(env.run("--archive", "--ir-open", "0")[0], 0)
            rc, out = env.run("--trace", "GH#45")
            self.assertIn("rule FR-2", out)
            self.assertNotIn("rule FR-1", out)                          # FR-1 cites only the question
            self.assertIn("rule FR-2", env.run("--trace", "JIRA-7")[1])

    def test_refs_are_optional_by_default_and_checked_when_asked(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            env.add_change("add-cart", DELTA_1, TASKS_OPEN)
            self.assertNotIn("REF001", env.codes(2))                    # nobody is made to use a tracker
            env.reload()
            env.state["layout"]["refRequired"] = True
            env.state["layout"]["refPattern"] = r"[A-Z]+-\d+"
            env.save()
            self.assertEqual(env.codes(2).get("REF001"), "error")
            d = env.root / ".tracespec/changes/add-cart/proposal.md"
            d.write_text(d.read_text().replace("| ID | Goal | Source |\n|---|---|---|\n| G-1 | The goal | Q-1 |",
                                               "| ID | Goal | Source | Ref |\n|---|---|---|---|\n| G-1 | The goal | Q-1 | bad ref |"))
            c = env.codes(2)
            self.assertNotIn("REF001", c)
            self.assertEqual(c.get("REF002"), "error")
            d.write_text(d.read_text().replace("bad ref", "JIRA-482"))
            self.assertNotIn("REF002", env.codes(2))


# ---- the query ---------------------------------------------------------------------------------------------

class TraceTests(unittest.TestCase):
    def test_targets_and_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = archived(tmp, refs="JIRA-482")
            rc, out = env.run("--trace", "test_AC1_a")                  # a test: the whole story of its rule, the test marked
            self.assertIn("==> verifies  test tests/test_cart.py::test_AC1_a", out)
            self.assertIn("rule FR-1", out)
            self.assertIn("ref JIRA-482", out)
            rc, out = env.run("--trace", "shop/cart.py:2")              # a line: the symbol that covers it
            self.assertIn("==> built by  code shop/cart.py::total", out)
            rc, out = env.run("--trace", "checkout")                    # a capability: its rules
            self.assertIn("rule FR-1", out)
            self.assertIn("rule FR-2", out)
            rc, out = env.run("--trace", "AC-1", "--down")
            self.assertNotIn("rule FR-1", out)
            self.assertIn("test tests/test_cart.py::test_AC1_a", out)
            rc, out = env.run("--trace", "AC-1", "--up")
            self.assertIn("^ covers  rule FR-1", out)
            self.assertNotIn("test tests/", out)
            rc, out = env.run("--trace", "T-2")                         # a bare task id resolves when it is unique
            self.assertIn("task add-cart/T-2", out)

    def test_json_mermaid_and_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = archived(tmp)
            rc, out = env.run("--trace", "AC-1", "--json")
            data = json.loads(out)
            self.assertEqual(data["targets"], ["AC-1"])
            self.assertIn({"from": "AC-1", "to": "FR-1", "kind": "covers"}, data["edges"])
            self.assertTrue(any(n["id"] == "AC-1" and "PASS" in n["state"] for n in data["nodes"]))
            rc, out = env.run("--trace", "AC-1", "--mermaid")
            self.assertTrue(out.startswith("flowchart TD"))
            rc, out = env.run("--trace", "does-not-exist")
            self.assertEqual(rc, 1)
            self.assertIn("nothing found", out)
            self.assertEqual(env.run("--trace")[0], 2)

    def test_limit_truncates_with_a_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = archived(tmp)
            rc, out = env.run("--trace", "checkout", "--limit", "3")
            self.assertEqual(len(out.strip().splitlines()), 4)
            self.assertIn("more line(s)", out)

    def test_a_change_in_flight_is_in_the_graph_before_it_is_archived(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = archived(tmp)
            env.add_change("add-discount", DELTA_2, "- [ ] T-1 Discount (serves D-1, FR-1, FR-3, AC-1, AC-3, FR-2, AC-2)\n")
            rc, out = env.run("--trace", "FR-3")
            self.assertEqual(rc, 0, out)
            self.assertIn("in flight: added", out)
            rc, out = env.run("--trace", "FR-1", "--down")
            self.assertIn("in flight: modified", out)
            self.assertIn("Total is the sum of items, before any discount", out)      # the new text, not the archived one


# ---- hooks -------------------------------------------------------------------------------------------------

@unittest.skipUnless(shutil.which("git"), "git is not installed")
class HookTests(unittest.TestCase):
    def test_install_is_idempotent_and_never_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            subprocess.run(["git", "-C", tmp, "init", "-q"], capture_output=True, check=True)
            rc, out = env.run("--install-hooks")
            self.assertEqual(rc, 0, out)
            self.assertIn("PostToolUse", out)                           # the optional Claude Code snippet is printed, not written
            env.run("--install-hooks")
            for name in ("post-commit", "post-merge", "post-checkout"):
                text = (Path(tmp) / ".git" / "hooks" / name).read_text()
                self.assertEqual(text.count("# tracespec:begin"), 1)
                self.assertIn("--sync --quiet", text)
                self.assertTrue(text.rstrip().endswith("# tracespec:end"))
                self.assertIn("|| true", text)

    def test_no_git_no_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            rc, out = env.run("--install-hooks")
            self.assertEqual(rc, 2)

    def test_sync_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp)
            rc, out = env.run("--sync")
            self.assertEqual(rc, 0)
            self.assertIn("synced:", out)
            self.assertEqual(env.run("--sync", "--quiet")[1], "")


if __name__ == "__main__":
    unittest.main()
