"""Tests of install.py. Run: python -m unittest test_install   (from the tools folder)"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def run(script: Path, *args: str):
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)


class InstallTests(unittest.TestCase):
    def test_copy_install_renders_the_agents_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills, agents = Path(tmp) / "skills", Path(tmp) / "agents"
            for _ in range(2):                                         # a second run must work and change nothing
                p = run(REPO / "install.py", "--skills-dir", str(skills), "--agents-dir", str(agents))
                self.assertEqual(p.returncode, 0, p.stderr)
            target = skills / "tracespec"
            for name in ("SKILL.md", "process.md", "workflows/apply.md", "templates/proposal.md", "tools/check.py"):
                self.assertTrue((target / name).is_file(), name)
            self.assertFalse((target / "install.py").exists())
            for name in ("tracespec-coder.md", "tracespec-test-writer.md"):
                text = (agents / name).read_text(encoding="utf-8")
                self.assertNotIn("{skill_dir}", text)
                self.assertIn(target.resolve().as_posix() + "/tools/guard.py", text)
                self.assertNotIn("{python}", text)
                if "guard.py" in text:                         # the hook command is a YAML string, so its quotes are escaped
                    self.assertIn('\\"' + Path(sys.executable).as_posix() + '\\" \\"' + target.resolve().as_posix()
                                  + '/tools/guard.py\\"', text)

    def test_an_update_removes_files_the_new_version_no_longer_has(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills, agents = Path(tmp) / "skills", Path(tmp) / "agents"
            run(REPO / "install.py", "--skills-dir", str(skills), "--agents-dir", str(agents))
            stale = skills / "tracespec" / "workflows" / "old-workflow.md"
            stale.write_text("gone in the next version")
            run(REPO / "install.py", "--skills-dir", str(skills), "--agents-dir", str(agents))
            self.assertFalse(stale.exists())

    def test_in_place_install_only_writes_the_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "skills" / "tracespec"
            shutil.copytree(REPO, clone, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
            agents = Path(tmp) / "agents"
            p = run(clone / "install.py", "--skills-dir", str(clone.parent), "--agents-dir", str(agents))
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("already in place", p.stdout)
            self.assertIn(clone.resolve().as_posix(), (agents / "tracespec-coder.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
