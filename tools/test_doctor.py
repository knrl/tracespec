"""Tests of `check.py --init` and `check.py --doctor`. Run: python -m unittest test_doctor   (from the tools folder)"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import common  # noqa: E402
import doctor  # noqa: E402

CHECK = HERE / "check.py"
INSTALL = HERE.parent / "install.py"


def check(*args: str, cwd=None):
    p = subprocess.run([sys.executable, str(CHECK), *args], capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def levels(checks):
    return [level for level, _ in checks]


def messages(checks, level):
    return [m for lv, m in checks if lv == level]


def make_project(tmp: str, test_cmd=None) -> Path:
    root = Path(tmp) / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "src").mkdir()
    state = {"process": "tracespec", "changes": {}, "layout": {
        "tests": ["tests/**"], "code": ["src/**"], "testCmd": test_cmd or [sys.executable, "-c", "pass"]}}
    (root / common.STATE).write_text(json.dumps(state))
    return root


def install_agents(tmp: str) -> Path:
    agents = Path(tmp) / "agents"
    p = subprocess.run([sys.executable, str(INSTALL), "--skills-dir", str(Path(tmp) / "skills"), "--agents-dir", str(agents)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return agents


class InitTests(unittest.TestCase):
    def test_init_writes_the_layout_it_detects(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pyproject.toml").write_text("[project]\nname='x'\n")
            rc, out = check(tmp, "--init")
            self.assertEqual(rc, 0, out)
            state = json.loads((Path(tmp) / common.STATE).read_text())
            self.assertEqual(state["changes"], {})
            self.assertIn("**/*.py", state["layout"]["code"])
            self.assertEqual(state["layout"]["testCmd"][:3], ["python", "-m", "pytest"])
            layout, problems = common.layout_of(Path(tmp))
            self.assertEqual(problems, [])

    def test_init_never_overwrites_and_refuses_inside_a_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp)
            before = (root / common.STATE).read_text()
            for folder in (root, root / "src"):
                rc, out = check(str(folder), "--init")
                self.assertEqual(rc, 2, out)
                self.assertIn("already exists", out)
            self.assertEqual((root / common.STATE).read_text(), before)

    def test_init_on_an_unknown_stack_says_what_to_fill_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = check(tmp, "--init")
            self.assertEqual(rc, 0, out)
            self.assertIn("not recognised", out)
            self.assertTrue((Path(tmp) / common.STATE).is_file())

    def test_init_needs_a_folder(self):
        rc, out = check(str(Path(tempfile.gettempdir()) / "no-such-folder-for-tracespec"), "--init")
        self.assertEqual(rc, 2)
        self.assertIn("not a folder", out)


class DoctorTests(unittest.TestCase):
    def test_a_ready_machine_and_project_have_no_problems(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, agents = make_project(tmp), install_agents(tmp)
            checks = doctor.doctor(root, agents, run=False)
            self.assertNotIn("FAIL", levels(checks), checks)
            self.assertTrue(any("guard hook starts" in m for m in messages(checks, "ok")))      # the real hook was asked, and denied
            code, text = doctor.report(checks)
            self.assertEqual(code, 0)
            self.assertIn("Ready.", text)

    def test_missing_agents_are_a_problem_with_the_fix_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            checks = doctor.doctor(make_project(tmp), Path(tmp) / "none", run=False)
            fails = messages(checks, "FAIL")
            self.assertEqual(len(fails), 2)
            self.assertIn("python install.py", fails[0])

    def test_a_hook_whose_python_is_gone_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, agents = make_project(tmp), install_agents(tmp)
            for f in agents.glob("*.md"):
                f.write_text(f.read_text().replace(Path(sys.executable).as_posix(), "C:/no/such/python.exe"))
            fails = messages(doctor.doctor(root, agents, run=False), "FAIL")
            self.assertEqual(len(fails), 2)
            self.assertIn("does not exist", fails[0])

    def test_a_hook_that_lets_a_hidden_read_through_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, agents = make_project(tmp), install_agents(tmp)
            real = (Path(tmp) / "skills" / "tracespec").resolve().as_posix() + "/tools/guard.py"
            lax = Path(tmp) / "lax" / "guard.py"                     # a hook that starts but allows everything
            lax.parent.mkdir()
            lax.write_text("import sys\nsys.exit(0)\n")
            for f in agents.glob("*.md"):
                f.write_text(f.read_text().replace(real, lax.resolve().as_posix()))
            fails = messages(doctor.doctor(root, agents, run=False), "FAIL")
            self.assertTrue(any("let a read" in m for m in fails), fails)

    def test_a_test_command_that_is_not_installed_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, test_cmd=["no-such-test-runner-xyz", "run"])
            fails = messages(doctor.project_checks(root, run=False), "FAIL")
            self.assertTrue(any("not found on PATH" in m for m in fails), fails)

    def test_a_test_command_that_does_not_write_junit_is_a_problem_and_shows_why(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, test_cmd=[sys.executable, "-c", "import sys; sys.stderr.write('boom ' + 'here')"])
            fails = messages(doctor.project_checks(root, run=True), "FAIL")
            self.assertTrue(any("boom here" in m for m in fails), fails)

    def test_a_working_test_command_is_reported_with_its_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml = '<testsuite><testcase classname="t" name="test_AC1_a"/><testcase classname="t" name="test_AC2_b"/></testsuite>'
            root = make_project(tmp, test_cmd=[sys.executable, "-c", f"open('.tracespec-junit.xml','w').write({xml!r})"])
            ok = messages(doctor.project_checks(root, run=True), "ok")
            self.assertTrue(any("2 tests, all passing" in m for m in ok), ok)

    def test_a_corrupt_state_file_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp)
            (root / common.STATE).write_text("{not json")
            checks = doctor.doctor(root, Path(tmp) / "none", run=False)
            self.assertTrue(any("not valid JSON" in m for m in messages(checks, "FAIL")))

    def test_no_project_is_a_warning_that_points_at_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            checks = doctor.doctor(None, install_agents(tmp), run=False)
            self.assertNotIn("FAIL", levels(checks), checks)
            self.assertTrue(any("--init" in m for m in messages(checks, "warn")))

    def test_the_command_line_exit_code_follows_the_problems(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, test_cmd=["no-such-test-runner-xyz"])
            rc, out = check(str(root), "--doctor", "--no-run")
            self.assertEqual(rc, 1, out)
            self.assertIn("FAIL", out)
            self.assertIn("problem(s)", out)


if __name__ == "__main__":
    unittest.main()
