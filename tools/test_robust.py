"""Tests of how the tools behave when their input is wrong: bad state files, bad arguments, damaged caches and ledgers.
Run: python -m unittest test_robust   (from the tools folder)"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import common  # noqa: E402
import ledger  # noqa: E402
import results  # noqa: E402
import store  # noqa: E402

CHECK = HERE / "check.py"


def check(root: Path | str, *args: str):
    p = subprocess.run([sys.executable, str(CHECK), str(root), *args], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def project(tmp: str, state: str | None = None) -> Path:
    root = Path(tmp)
    (root / common.STATE).write_text(state if state is not None else json.dumps({"process": "tracespec", "changes": {}}))
    return root


class StateFileTests(unittest.TestCase):
    def test_a_corrupt_state_file_is_an_error_and_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, '{"process": "tracespec", "chan')
            for args in (("--list",), ("--gate", "2"), ("--baseline",)):
                rc, out = check(root, *args)
                self.assertEqual(rc, 2, out)
                self.assertIn("not valid JSON", out)
            self.assertEqual((root / common.STATE).read_text(), '{"process": "tracespec", "chan')

    def test_a_state_file_that_is_not_an_object_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = check(project(tmp, "[]"), "--list")
            self.assertEqual(rc, 2, out)
            self.assertIn("JSON object", out)
            self.assertNotIn("Traceback", out)

    def test_a_valid_state_file_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = check(project(tmp), "--list")
            self.assertEqual(rc, 0, out)
            self.assertIn("No changes", out)

    def test_atomic_write_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "x.json"
            common.write_atomic(target, '{"a": 1}\n')
            common.write_atomic(target, '{"a": 2}\n')
            self.assertEqual(json.loads(target.read_text()), {"a": 2})
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["x.json"])


class ArgumentTests(unittest.TestCase):
    def test_help_prints_the_usage_without_a_project(self):
        for flag in ("--help", "-h"):
            rc, out = check(".", flag)
            self.assertEqual(rc, 0, out)
            self.assertIn("Mechanical checks", out)

    def test_version_works_anywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = check(project(tmp), "--version")
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), (HERE.parent / "VERSION").read_text().strip())

    def test_an_unknown_flag_is_refused_not_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = check(project(tmp), "--audt")
            self.assertEqual(rc, 2, out)
            self.assertIn("unknown option --audt", out)

    def test_a_bad_number_is_a_message_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            for args in (("--gate", "abc"), ("--gate",), ("--gate", "9"), ("--gate", "--run"), ("--trace", "x", "--depth", "x")):
                rc, out = check(root, *args)
                self.assertEqual(rc, 2, (args, out))
                self.assertNotIn("Traceback", out)
                self.assertIn("needs a whole number", out)

    def test_the_project_folder_must_come_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run([sys.executable, str(CHECK), "--gate", "4", tmp], capture_output=True, text=True)
            self.assertEqual(p.returncode, 2)
            self.assertIn("project folder comes first", p.stdout)

    def test_every_flag_the_tool_reads_is_known(self):
        import re
        source = (HERE / "check.py").read_text(encoding="utf-8")
        used = set(re.findall(r'(?:"|\()(--[a-z][a-z-]+)"', source)) - {"--junitfile", "--logger"}
        import check as check_module
        self.assertEqual(sorted(used - check_module.KNOWN_FLAGS), [])


class DamagedFileTests(unittest.TestCase):
    def test_a_damaged_cache_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = store.cache_path(root)
            path.parent.mkdir(parents=True)
            path.write_text("this is not a database")
            with store.cache(root) as conn:
                conn.execute("SELECT count(*) FROM filecache").fetchone()
            self.assertGreater(path.stat().st_size, 0)

    def test_a_ledger_that_is_not_what_it_should_be_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cap = ledger.cap_path(root, "checkout")
            cap.mkdir(parents=True)
            for content in (b"5\n", b"\xff\xfe\n", b"[1]\n"):
                (cap / "history.jsonl").write_bytes(content)
                problems = ledger.verify_ledger(root, "checkout", "x")
                self.assertEqual(len(problems), 1, content)


class CoverageTests(unittest.TestCase):
    def test_one_failing_test_uncovers_a_criterion_that_another_test_passes(self):
        cases = [{"name": "a::test_AC1_ok", "status": "pass", "ids": ["AC-1"]},
                 {"name": "a::test_AC1_bad", "status": "fail", "ids": ["AC-1"]},
                 {"name": "a::test_AC2", "status": "pass", "ids": ["AC-2"]}]
        self.assertEqual(ledger.passing_ids({}, cases), {"AC-2"})

    def test_a_known_failing_test_does_not_uncover(self):
        cases = [{"name": "a::test_AC1_ok", "status": "pass", "ids": ["AC-1"]},
                 {"name": "a::test_AC1_old", "status": "fail", "ids": ["AC-1"]}]
        self.assertEqual(ledger.passing_ids({"knownFailing": ["a::test_AC1_old"]}, cases), {"AC-1"})


class TestRunnerTests(unittest.TestCase):
    def test_the_error_output_of_a_broken_test_command_is_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = common.layout_of(None)[0]
            layout["testCmd"] = [sys.executable, "-c", "import sys; sys.stderr.write('A' + 'BC')"]
            cases, err = results.run_tests(Path(tmp), layout, verbose=True)
            self.assertEqual(cases, [])
            self.assertIn("ABC", err)
            _, quiet = results.run_tests(Path(tmp), layout)           # the build agents never get it: it can hold test text
            self.assertNotIn("ABC", quiet)

    def test_the_junit_report_is_removed_after_it_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = common.layout_of(None)[0]
            xml = ('<testsuite><testcase classname="t" name="test_AC1_x"><failure message="m">E assert secret</failure>'
                   '</testcase></testsuite>')
            layout["testCmd"] = [sys.executable, "-c", f"open({layout['junit']!r}, 'w').write({xml!r})"]
            cases, err = results.run_tests(Path(tmp), layout)
            self.assertIsNone(err)
            self.assertEqual(len(cases), 1)
            self.assertFalse((Path(tmp) / layout["junit"]).exists())


class GuardTests(unittest.TestCase):
    def test_shell_detours_and_unprefixed_layouts_are_caught(self):
        from test_basics import guard, make_project
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, layout={"tests": ["tests/**"], "code": ["src/**"]})
            for cmd in ("cat TESTS/test_cart.py", "cat <tests/test_cart.py", "cat tests|head", "cat src/../tests/t.py"):
                self.assertEqual(guard(root, "coder", "Bash", command=cmd), "deny", cmd)
            self.assertEqual(guard(root, "coder", "Bash", command="cat src/a.py"), "allow")
        with tempfile.TemporaryDirectory() as tmp:                 # no folder prefix in the layout: the name check sees nothing
            root = make_project(tmp, layout={"tests": ["**/test_*.py"], "code": ["src/**"]})
            self.assertEqual(guard(root, "coder", "Bash", command="cat shop/test_cart.py"), "deny")
            self.assertEqual(guard(root, "coder", "Bash", command="cat shop/cart.py"), "allow")

    def test_git_commands_that_print_contents_are_refused(self):
        from test_basics import guard, make_project
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, layout={"tests": ["tests/**"], "code": ["src/**"]})
            for cmd in ("git diff", "git grep AC1", "git log -p -1", "git show HEAD", "git stash", "git checkout -- ."):
                self.assertEqual(guard(root, "coder", "Bash", command=cmd), "deny", cmd)
                self.assertEqual(guard(root, "tester", "Bash", command=cmd), "deny", cmd)
            for cmd in ("git status -s", "git log --oneline -3", "git add src/a.py"):
                self.assertEqual(guard(root, "coder", "Bash", command=cmd), "allow", cmd)

    def test_search_patterns_cannot_climb_out(self):
        from test_basics import guard, make_project
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, layout={"tests": ["tests/**"], "code": ["src/**"]})
            self.assertEqual(guard(root, "coder", "Glob", pattern="../tests/*.py", path=str(root / "docs")), "deny")
            self.assertEqual(guard(root, "coder", "Glob", pattern="/etc/*", path=str(root / "docs")), "deny")
            self.assertEqual(guard(root, "coder", "Grep", pattern="a..b", path=str(root / "docs")), "allow")   # text, not a path

    def test_a_malformed_event_is_refused_not_waved_through(self):
        for stdin in ("not json", '{"tool_name": "Bash", "tool_input": ["x"]}', "[1]"):
            p = subprocess.run([sys.executable, str(HERE / "guard.py"), "coder"], input=stdin, capture_output=True, text=True)
            self.assertIn('"deny"', p.stdout, stdin)


class StoreTests(unittest.TestCase):
    def test_a_baseline_under_a_path_with_special_characters_is_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "c#proj 100%"
            root.mkdir()
            store.write_baseline(root, "cap", {"FR-1": ("rule", "x", "h")}, set(), {"changes": []})
            self.assertIn("FR-1", store.read_baseline(root, "cap")["nodes"])

    def test_a_locked_cache_is_not_deleted(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with store.cache(root):
                pass
            path = store.cache_path(root)
            holder = sqlite3.connect(path)
            holder.execute("BEGIN EXCLUSIVE")
            store.CACHE_TIMEOUT = 0.2
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    with store.cache(root):
                        pass
                self.assertTrue(path.exists())
            finally:
                store.CACHE_TIMEOUT = 30
                holder.close()


class GitPathTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_changed_files_are_relative_to_the_project_and_skip_outside_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "-C", tmp, "init", "-q"], check=True, capture_output=True)
            (repo / "sub" / "shop").mkdir(parents=True)
            (repo / "other").mkdir()
            (repo / "sub" / "shop" / "new.py").write_text("x = 1\n")
            (repo / "sub" / "shop" / "café.py").write_text("y = 1\n")
            (repo / "other" / "f.txt").write_text("z\n")
            self.assertEqual(sorted(ledger.changed_files(repo / "sub")), ["shop/café.py", "shop/new.py"])

    def test_code_in_a_folder_named_bin_below_the_root_is_seen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bin").mkdir()
            (root / "bin" / "build.py").write_text("x = 1\n")
            (root / "src" / "bin").mkdir(parents=True)
            (root / "src" / "bin" / "main.py").write_text("x = 1\n")
            self.assertEqual(sorted(common.walk_files(root)), ["src/bin/main.py"])


if __name__ == "__main__":
    unittest.main()
