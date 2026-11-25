"""Tests of the glob helpers, the guard and the safe test runner.
Run all tool tests: python -m unittest discover -s . -p "test_*.py"   (from the tools folder)"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402


def make_project(tmp: str, layout: dict | None = None) -> Path:
    root = Path(tmp)
    state = {"process": "tracespec", "activeChange": "x", "changes": {"x": {"phase": "propose"}}, "layout": layout or {}}
    (root / common.STATE).write_text(json.dumps(state), encoding="utf-8")
    (root / "src").mkdir(exist_ok=True)
    (root / "tests").mkdir(exist_ok=True)
    return root


class GlobTests(unittest.TestCase):
    def test_dir_and_file_patterns(self):
        self.assertTrue(common.matches("tests/a/b.py", ["tests"]))
        self.assertTrue(common.matches("tests", ["tests/**"]))
        self.assertFalse(common.matches("tests_old/a.py", ["tests"]))
        self.assertTrue(common.matches("a/b/test_x.py", ["**/test_*.py"]))
        self.assertTrue(common.matches("test_x.py", ["**/test_*.py"]))
        self.assertFalse(common.matches("a/b/x.py", ["**/test_*.py"]))

    def test_prefix(self):
        self.assertEqual(common.literal_prefix("src/**"), "src")
        self.assertEqual(common.literal_prefix("**/*.py"), "")
        self.assertEqual(common.literal_prefix("src/main/**"), "src/main")

    def test_classify_test_beats_code(self):
        lay = {"tests": ["**/*.test.ts"], "code": ["src/**"], "protected": [".tracespec/**", "docs/features/**", ".tracespec.json"]}
        self.assertEqual(common.classify("src/a.test.ts", lay), "test")
        self.assertEqual(common.classify("src/a.ts", lay), "code")
        self.assertEqual(common.classify(".tracespec/specs/x/spec.md", lay), "protected")
        self.assertEqual(common.classify(".tracespec/changes/add/proposal.md", lay), "protected")
        self.assertEqual(common.classify("docs/features/add.md", lay), "protected")
        self.assertEqual(common.classify(".tracespec.json", lay), "protected")      # a leading dot must not be stripped
        self.assertEqual(common.classify("README.md", lay), "other")

    def test_ids(self):
        self.assertEqual(common.test_ids("test_AC3_and_ac_4 AC_5 FR-2 AC-3"), ["AC-3", "AC-5", "FR-2"])
        self.assertEqual(common.test_ids("test_package_3"), [])


def guard(root: Path, role: str, tool: str, **tool_input):
    ev = {"cwd": str(root), "tool_name": tool, "tool_input": tool_input}
    p = subprocess.run([sys.executable, str(HERE / "guard.py"), role], input=json.dumps(ev),
                       capture_output=True, text=True)
    return "deny" if '"deny"' in p.stdout else "allow"


class GuardTests(unittest.TestCase):
    def test_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, layout={"tests": ["tests/**"], "code": ["src/**"]})
            r = lambda *p: str(root.joinpath(*p))  # noqa: E731
            self.assertEqual(guard(root, "coder", "Read", file_path=r("tests", "t.py")), "deny")
            self.assertEqual(guard(root, "coder", "Read", file_path=r("src", "a.py")), "allow")
            self.assertEqual(guard(root, "coder", "Write", file_path=r("src", "a.py")), "allow")
            for protected in ((".tracespec", "specs", "cap", "spec.md"), (".tracespec", "changes", "add", "proposal.md"),
                              (".tracespec", "specs", "cap", "trace.json"), ("docs", "features", "add.md")):
                self.assertEqual(guard(root, "coder", "Write", file_path=r(*protected)), "deny")
                self.assertEqual(guard(root, "coder", "Read", file_path=r(*protected)), "allow")
            self.assertEqual(guard(root, "tester", "Read", file_path=r("src", "a.py")), "deny")
            self.assertEqual(guard(root, "tester", "Write", file_path=r("tests", "t.py")), "allow")
            self.assertEqual(guard(root, "tester", "Write", file_path=r(".tracespec", "changes", "add", "tasks.md")), "deny")
            self.assertEqual(guard(root, "tester", "Write", file_path=r("README.md")), "deny")
            self.assertEqual(guard(root, "tester", "Read", file_path=r("README.md")), "allow")

    def test_search_and_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, layout={"tests": ["tests/**"], "code": ["src/**"]})
            self.assertEqual(guard(root, "coder", "Grep", pattern="x"), "deny")
            self.assertEqual(guard(root, "coder", "Grep", pattern="x", path=str(root / "src")), "allow")
            self.assertEqual(guard(root, "coder", "Grep", pattern="x", path=str(root / "tests")), "deny")
            self.assertEqual(guard(root, "tester", "Glob", pattern="*.py", path=str(root / "docs")), "allow")
            self.assertEqual(guard(root, "coder", "Bash", command="python -m pytest -q"), "deny")
            self.assertEqual(guard(root, "coder", "Bash", command="npm test"), "deny")
            self.assertEqual(guard(root, "coder", "Bash", command="cat tests/t.py"), "deny")
            self.assertEqual(guard(root, "coder", "Bash", command="grep -r foo ."), "deny")
            self.assertEqual(guard(root, "coder", "Bash", command=f'python "{HERE}/results.py" "{root}"'), "allow")

    def test_colocated_tests_disable_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, layout={"tests": ["**/*.test.ts"], "code": ["src/**"]})
            self.assertEqual(guard(root, "coder", "Grep", pattern="x", path=str(root / "src")), "deny")
            self.assertEqual(guard(root, "coder", "Read", file_path=str(root / "src" / "a.test.ts")), "deny")
            self.assertEqual(guard(root, "coder", "Read", file_path=str(root / "src" / "a.ts")), "allow")
            self.assertEqual(guard(root, "tester", "Write", file_path=str(root / "src" / "a.test.ts")), "allow")
            self.assertEqual(guard(root, "tester", "Write", file_path=str(root / "src" / "a.ts")), "deny")


class ResultsTests(unittest.TestCase):
    def test_results_output_and_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml = ('<testsuites><testsuite>'
                   '<testcase classname="t.test_cart" name="test_AC1_ok"/>'
                   '<testcase classname="t.test_cart" name="test_AC2_bad"><failure message="assert 1 == 2\nline2">tb</failure></testcase>'
                   '<testcase classname="t.test_cart" name="test_plain"/>'
                   '</testsuite></testsuites>')
            writer = f"open('.tracespec-junit.xml','w').write({xml!r})"
            root = make_project(tmp, layout={"testCmd": [sys.executable, "-c", writer]})
            run = lambda *a: subprocess.run([sys.executable, str(HERE / "results.py"), str(root), *a],  # noqa: E731
                                            capture_output=True, text=True)
            p = run()
            self.assertEqual(p.returncode, 1)
            self.assertIn("PASS  [AC-1] test_cart::test_AC1_ok", p.stdout)
            self.assertIn("FAIL  [AC-2] test_cart::test_AC2_bad -- assert 1 == 2", p.stdout)
            self.assertNotIn("tb", p.stdout.replace("test_AC2_bad", ""))
            self.assertEqual(run("AC-1").returncode, 0)
            p = run("AC-9")
            self.assertEqual(p.returncode, 1)
            self.assertIn("NO TEST for AC-9", p.stdout)

    def test_cannot_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, layout={"testCmd": []})
            p = subprocess.run([sys.executable, str(HERE / "results.py"), str(root)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 2)
            self.assertIn("CANNOT RUN", p.stdout)


class DetectTests(unittest.TestCase):
    def test_detect_python(self):
        import check
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pyproject.toml").write_text("[project]\nname='x'\n")
            d = check.detect(Path(tmp))
            self.assertEqual(d["stack"], "python")
            self.assertIn("--junitxml=.tracespec-junit.xml", d["testCmd"])


if __name__ == "__main__":
    unittest.main()
